from datetime import timedelta
import secrets
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import create_access_token, hash_secret
from app.models import DeviceSession, RefreshCredential, User
from app.models.common import utc_now
from app.schemas.user import Token
from app.services.auth_security import audit


def invalid_credentials():
    return HTTPException(401, "Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})


def lock_user(db: Session, user_id: UUID) -> User:
    # All credential/session mutations lock user first, then session/challenge.
    return db.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))


def token_pair(db: Session, device: DeviceSession, settings: Settings) -> Token:
    raw = secrets.token_urlsafe(48)
    db.add(RefreshCredential(session_id=device.id, token_hash=hash_secret("refresh:" + raw, settings)))
    device.last_used_at = utc_now()
    return Token(access_token=create_access_token(device.user_id, settings, device.id),
                 expires_in=settings.access_token_expire_minutes * 60, refresh_token=raw,
                 refresh_expires_in=max(0, int((device.expires_at - utc_now()).total_seconds())), session_id=device.id)


def new_session(db: Session, user: User, settings: Settings, device_name: str = "Mobile device") -> Token:
    now = utc_now()
    device = DeviceSession(user_id=user.id, device_name=device_name, last_used_at=now,
                           expires_at=now + timedelta(days=settings.refresh_token_expire_days))
    db.add(device)
    db.flush()
    result = token_pair(db, device, settings)
    audit(db, "session_created", user.id, device.id)
    db.commit()
    return result


def rotate_refresh(db: Session, raw: str, settings: Settings) -> Token:
    credential = db.scalar(select(RefreshCredential).where(
        RefreshCredential.token_hash == hash_secret("refresh:" + raw, settings)))
    if credential is None:
        audit(db, "refresh_rejected")
        db.commit()
        raise invalid_credentials()
    device = db.get(DeviceSession, credential.session_id)
    lock_user(db, device.user_id)
    device = db.scalar(select(DeviceSession).where(DeviceSession.id == device.id).with_for_update()
                       .execution_options(populate_existing=True))
    db.refresh(credential)
    if credential.consumed_at is not None:
        device.revoked_at = utc_now()
        audit(db, "refresh_replay", device.user_id, device.id)
        db.commit()
        raise invalid_credentials()
    if device.revoked_at is not None or device.expires_at <= utc_now():
        audit(db, "refresh_rejected", device.user_id, device.id)
        db.commit()
        raise invalid_credentials()
    credential.consumed_at = utc_now()
    result = token_pair(db, device, settings)
    audit(db, "refresh_rotated", device.user_id, device.id)
    db.commit()
    return result


def revoke_all(db: Session, user_id: UUID):
    db.execute(update(DeviceSession).where(DeviceSession.user_id == user_id,
               DeviceSession.revoked_at.is_(None)).values(revoked_at=utc_now()))
