"""Staff authorization, TOTP and projections over the existing books."""
import base64
import hashlib
import hmac
import struct
import time
from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select

from app.api.deps import SessionDep, SettingsDep
from app.core.security import ALGORITHM
from app.models import DeviceSession, User
from app.models.books import Profile
from app.models.common import utc_now
from app.models.staff import DriverAssignment, StaffAccount, StaffAudit
from app.services.books import profile, wire
from app.services.sessions import lock_user

IDLE_SECONDS = 900
staff_bearer = HTTPBearer(auto_error=False, scheme_name="StaffBearer")


def totp(secret: str, counter: int) -> str:
    raw = hmac.new(base64.b32decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = raw[-1] & 15
    return f"{(int.from_bytes(raw[offset:offset + 4], 'big') & 0x7fffffff) % 1000000:06d}"


def verified_counter(secret: str, code: str, previous: int) -> int | None:
    current = int(time.time()) // 30
    for counter in (current, current - 1, current + 1):
        if counter > previous and hmac.compare_digest(totp(secret, counter), code):
            return counter
    return None


def identity(db, staff):
    return {"id": staff.id, "name": staff.name, "role": staff.role, "team_id": staff.team_id,
            "email": db.get(User, staff.id).email}


def add_audit(db, staff, action, driver_id=None, resource_id=None, before=None, after=None):
    db.add(StaffAudit(actor_id=staff.id, driver_id=driver_id, action=action,
                      resource_id=resource_id, before=jsonable_encoder(before), after=jsonable_encoder(after)))


def staff_token(staff, device, settings):
    now = utc_now()
    return jwt.encode({"sub": str(staff.id), "sid": str(device.id), "jti": str(uuid4()),
        "type": "staff_access", "iss": settings.jwt_issuer, "aud": settings.jwt_audience + ":staff",
        "iat": now, "exp": now + timedelta(minutes=settings.access_token_expire_minutes)},
        settings.jwt_secret_key.get_secret_value(), algorithm=ALGORITHM)


def current_staff(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(staff_bearer)],
                  db: SessionDep, settings: SettingsDep, request: Request):
    invalid = HTTPException(401, "Staff session expired; sign in again")
    if credentials is None:
        raise invalid
    try:
        claims = jwt.decode(credentials.credentials, settings.jwt_secret_key.get_secret_value(), algorithms=[ALGORITHM],
            issuer=settings.jwt_issuer, audience=settings.jwt_audience + ":staff",
            options={"require": ["sub", "sid", "exp", "iat", "jti", "type"]})
        if claims["type"] != "staff_access":
            raise ValueError()
        subject, device_id = UUID(claims["sub"]), UUID(claims["sid"])
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise invalid from None
    lock_user(db, subject)
    staff = db.get(StaffAccount, subject, populate_existing=True)
    device = db.get(DeviceSession, device_id, populate_existing=True)
    if not staff or not staff.active or not device or device.user_id != subject or device.revoked_at or device.expires_at <= utc_now():
        raise invalid
    if (utc_now() - device.last_used_at).total_seconds() >= IDLE_SECONDS:
        device.revoked_at = utc_now()
        db.commit()
        raise invalid
    device.last_used_at = utc_now()
    db.commit()
    request.state.device_id = device.id
    # Owner writes recheck this real staff device; no driver token is minted.
    return staff, device


StaffAuth = Annotated[tuple, Depends(current_staff)]


def driver_scope(staff):
    base = select(User.id).where(~User.id.in_(select(StaffAccount.id)))
    if staff.role == "accountant":
        base = base.where(User.id.in_(select(DriverAssignment.driver_id).where(DriverAssignment.accountant_id == staff.id)))
    elif staff.role == "senior_accountant":
        base = base.where(User.id.in_(select(DriverAssignment.driver_id).join(StaffAccount,
            DriverAssignment.accountant_id == StaffAccount.id).where(StaffAccount.team_id == staff.team_id,
                StaffAccount.team_id.is_not(None))))
    return base


def require_driver(db, staff, driver_id, write=False):
    if write and staff.role == "support":
        raise HTTPException(403, "Support has read-only financial access")
    user = db.scalar(select(User).where(User.id == driver_id, User.id.in_(driver_scope(staff))))
    if not user:
        raise HTTPException(404, "Driver not found or outside your assignment")
    return user


def driver_name(db, user):
    me = profile(db, user.id, "me")
    names = me.data if me else {}
    return " ".join(x for x in (names.get("first_name"), names.get("last_name")) if x) or user.display_name or "Name not provided"


def driver_summary(db, user):
    assignment = db.get(DriverAssignment, user.id)
    accountant = db.get(StaffAccount, assignment.accountant_id) if assignment else None
    return {"id": user.id, "name": driver_name(db, user), "email": user.email,
        "accountant_id": accountant.id if accountant else None,
        "accountant_name": accountant.name if accountant else None, "created_at": user.created_at}


def driver_search(db, staff, search):
    query = select(User).where(User.id.in_(driver_scope(staff)))
    search = search.strip()
    if not search:
        return query
    if search.isdigit():
        if len(search) != 10:
            raise HTTPException(422, "UTR search requires all ten digits")
        # A keyed search index is not present in the driver model. Decrypt only
        # already-scoped, suffix-matching candidates and compare exact values.
        return query.where(User.id.in_(select(Profile.owner_id).where(Profile.kind == "tax",
            Profile.data["utr_masked"].astext == "******" + search[-4:])))
    term = "%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    names = select(Profile.owner_id).where(Profile.kind == "me",
        func.concat(Profile.data["first_name"].astext, " ", Profile.data["last_name"].astext).ilike(term, escape="\\"))
    return query.where(or_(User.email.ilike(term, escape="\\"), User.display_name.ilike(term, escape="\\"), User.id.in_(names)))


def paginate(db, query, model, data, columns, serializer=wire):
    if data.sort not in columns:
        raise HTTPException(422, "Unsupported sort field")
    column = columns[data.sort]
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    order = column.desc() if data.order == "desc" else column.asc()
    items = list(db.scalars(query.order_by(order, model.id.asc()).offset((data.page - 1) * data.page_size).limit(data.page_size)))
    return {"items": [serializer(row) for row in items], "total": total, "page": data.page, "page_size": data.page_size}


def query_filters(data, allowed):
    if set(data.filters) - set(allowed):
        raise HTTPException(422, "Unsupported filter field")
