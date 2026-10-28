"""Shared ownership, atomic writes, history and cursor primitives."""
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import hmac
import json
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select
from sqlalchemy.inspection import inspect
from pydantic import ValidationError

from app.models.books import Business, Idempotency, Mutation, Profile
from app.services.sessions import lock_user


def catalog_id(kind, code):
    return uuid5(NAMESPACE_URL, f"https://taxiaibooks/reference/{kind}/{code}")


SOURCE_CODES = {"uber": "platform", "bolt": "platform", "operator": "operator", "cash": "cash", "other": "other"}
CATEGORY_CODES = {
    "platform_fees": False, "parking": False, "tolls": False, "phone_data": False,
    "licensing": False, "fuel": True, "maintenance": True, "insurance": True,
    "cleaning": True, "vehicle_purchase": True, "fines": False, "meals": False, "other": False,
}
SOURCES = {catalog_id("source", code): {"id": catalog_id("source", code), "code": code,
    "name": code.replace("_", " ").title(), "kind": kind, "active": True} for code, kind in SOURCE_CODES.items()}
CATEGORIES = {catalog_id("category", code): {"id": catalog_id("category", code), "code": code,
    "label_key": f"category.{code}", "allowed_kinds": ["expense"], "requires_vehicle": vehicle,
    "eligibility_reason_codes": [], "default_business_use_percent": "100.00", "version": 1}
    for code, vehicle in CATEGORY_CODES.items()}


def check_version(row, expected):
    if expected != row.version:
        raise HTTPException(409, "Stale version; reload the resource")


def validate_input(model,values):
    try:
        return model(**values)
    except ValidationError as exc:
        errors=[{"loc":["body",*error["loc"]],"msg":error["msg"],"type":error["type"]} for error in exc.errors()]
        raise HTTPException(422,detail=errors) from None


def owned(db, model, owner, resource_id, lock=False):
    query = select(model).where(model.id == resource_id, model.owner_id == owner)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = db.scalar(query)
    if row is None:
        raise HTTPException(404, "Resource not found")
    return row


def rows(db, model, owner):
    return select(model).where(model.owner_id == owner)


def wire(row):
    result = {c.key: getattr(row, c.key) for c in inspect(type(row)).columns
              if c.key not in {"owner_id", "identifiers", "content", "destination", "code_hash", "phone_hash"}}
    # Decimal wire values are strings, money remains integers.
    return jsonable_encoder(result, custom_encoder={Decimal: lambda v: format(v, ".2f")})


def canonical(value):
    return json.dumps(jsonable_encoder(value, custom_encoder={Decimal: str}), sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write(db, user, request, key, payload, operation):
    """Serialize owner mutations and persist effects plus response in one transaction.

    A key is owner-global, so changing method/path/body also conflicts. Rollback
    on dependency cleanup undoes every effect if the operation raises.
    """
    lock_user(db, user.id)
    if getattr(request.state, "device_id", None):
        from app.models import DeviceSession
        from app.models.common import utc_now
        device = db.get(DeviceSession, request.state.device_id, populate_existing=True)
        if device is None or device.revoked_at is not None or device.expires_at <= utc_now():
            raise HTTPException(401, "Session is no longer active")
    fingerprint = digest([request.method, request.url.path, str(request.url.query), payload])
    previous = db.scalar(rows(db, Idempotency, user.id).where(Idempotency.request_key == key))
    if previous:
        if not hmac.compare_digest(previous.digest, fingerprint):
            raise HTTPException(409, "Idempotency key was used for a different request")
        return previous.response
    result = jsonable_encoder(operation(), custom_encoder={Decimal: lambda v: format(v, ".2f")})
    db.add(Idempotency(owner_id=user.id, request_key=key, digest=fingerprint, response=result))
    db.commit()
    return result


def history(db, row, action, before=None, reason=None):
    db.flush()
    mutation_id = uuid4()
    if hasattr(row, "mutation_id"):
        row.mutation_id = mutation_id
    db.flush()
    db.add(Mutation(id=mutation_id, owner_id=row.owner_id, resource_type=row.__tablename__,
                    resource_id=row.id, action=action, before=before, after=wire(row), reason=reason))
    db.flush()
    return mutation_id


def exact_mutation(db, row, data):
    check_version(row, data.expected_version)
    mutation = owned(db, Mutation, row.owner_id, data.mutation_id)
    if mutation.resource_type != row.__tablename__ or mutation.resource_id != row.id or mutation.reversed_by:
        raise HTTPException(409, "Mutation does not match this resource or was already reversed")
    if mutation.after.get("version") != row.version or (hasattr(row, "mutation_id") and row.mutation_id != mutation.id):
        raise HTTPException(409, "Later changes prevent reversing this action")
    return mutation


def restore(row, snapshot, fields):
    for field in fields:
        value = snapshot.get(field)
        column = inspect(type(row)).columns[field]
        if value is not None:
            if column.type.python_type is date:
                value = date.fromisoformat(value)
            elif column.type.python_type is UUID:
                value = UUID(value)
            elif column.type.python_type is Decimal:
                value = Decimal(value)
        setattr(row, field, value)


def primary_business(db, owner):
    business = db.scalar(rows(db, Business, owner).where(Business.kind == "self_employment"))
    if business is None:
        business = Business(owner_id=owner, kind="self_employment", name="Taxi business")
        db.add(business)
        db.flush()
    return business


def profile(db, owner, kind, scope="", default=None, create=False):
    item = db.scalar(rows(db, Profile, owner).where(Profile.kind == kind, Profile.scope == scope))
    if item is None and create:
        item = Profile(owner_id=owner, kind=kind, scope=scope, data=default or {})
        db.add(item)
        db.flush()
    return item


def tax_dates(year):
    try:
        start, end = year.split("-")
        start = int(start)
        if f"{(start + 1) % 100:02d}" != end or not 2000 <= start <= 2098:
            raise ValueError()
        return date(start, 4, 6), date(start + 1, 4, 5)
    except (AttributeError, TypeError, ValueError):
        raise HTTPException(422, "Tax year must be consecutive YYYY-YY") from None


def tax_year(day):
    start = day.year if (day.month, day.day) >= (4, 6) else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def pence(value):
    return int(Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def page(db, query, model, owner, settings, limit=50, cursor=None, date_column=None, filters=None, serializer=wire):
    column = date_column if date_column is not None else model.created_at
    binding = digest([str(owner), model.__tablename__, filters or {}])
    if cursor:
        try:
            token, signature = cursor.split(".")
            expected = hmac.new(settings.jwt_secret_key.get_secret_value().encode(), token.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                raise ValueError()
            data = json.loads(urlsafe_b64decode(token + "=" * (-len(token) % 4)))
            if data["binding"] != binding:
                raise ValueError()
            value = column.type.python_type.fromisoformat(data["date"])
            row_id = UUID(data["id"])
        except (ValueError, TypeError, KeyError, AttributeError, json.JSONDecodeError):
            raise HTTPException(422, "Invalid cursor for this query") from None
        query = query.where(or_(column < value, and_(column == value, model.id < row_id)))
    records = list(db.scalars(query.order_by(column.desc(), model.id.desc()).limit(limit + 1)))
    more = len(records) > limit
    records = records[:limit]
    next_cursor = None
    if more:
        last = records[-1]
        token = urlsafe_b64encode(canonical({"binding": binding, "date": getattr(last, column.key), "id": last.id}).encode()).decode().rstrip("=")
        signature = hmac.new(settings.jwt_secret_key.get_secret_value().encode(), token.encode(), hashlib.sha256).hexdigest()
        next_cursor = token + "." + signature
    return {"items": [serializer(r) for r in records], "next_cursor": next_cursor, "has_more": more}
