from datetime import timedelta
import secrets

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import hash_secret, password_hash
from app.models import AuthChallenge, User
from app.models.common import utc_now
from app.services.auth_security import audit
from app.services.delivery import ResetDelivery
from app.services.sessions import invalid_credentials, lock_user, revoke_all


def check_password(db: Session, user: User, password: str):
    if not password_hash.verify(password, user.password_hash):
        audit(db, "reauthentication_failed", user.id)
        db.commit()
        raise invalid_credentials()


def invalidate_resets(db: Session, user_id):
    db.execute(update(AuthChallenge).where(AuthChallenge.user_id == user_id,
               AuthChallenge.kind == "password_reset", AuthChallenge.used_at.is_(None)).values(used_at=utc_now()))


def change_password(db: Session, user_id, current_password: str, new_password: str):
    user = lock_user(db, user_id)
    check_password(db, user, current_password)
    if current_password == new_password:
        raise HTTPException(422, "New password must be different")
    user.password_hash = password_hash.hash(new_password)
    revoke_all(db, user.id)
    invalidate_resets(db, user.id)
    audit(db, "password_changed", user.id)
    db.commit()


def request_reset(db: Session, email: str, settings: Settings, delivery: ResetDelivery):
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        audit(db, "password_reset_requested")
        db.commit()
        return
    user = lock_user(db, user.id)
    invalidate_resets(db, user.id)
    raw = secrets.token_urlsafe(48)
    db.add(AuthChallenge(kind="password_reset", user_id=user.id,
                         token_hash=hash_secret("reset:" + raw, settings),
                         expires_at=utc_now() + timedelta(minutes=settings.reset_token_expire_minutes)))
    try:
        delivery.send_reset(user.email, raw)
    except Exception:
        db.rollback()
        # Preserve a uniform public response even if delivery fails for a real account.
        audit(db, "password_reset_delivery_failed", user.id)
        db.commit()
        return
    audit(db, "password_reset_requested", user.id)
    db.commit()


def reset_password(db: Session, raw: str, new_password: str, settings: Settings):
    invalid = HTTPException(400, "Invalid or expired recovery token")
    challenge = db.scalar(select(AuthChallenge).where(AuthChallenge.kind == "password_reset",
        AuthChallenge.token_hash == hash_secret("reset:" + raw, settings)))
    if challenge is None:
        audit(db, "password_reset_rejected")
        db.commit()
        raise invalid
    user = lock_user(db, challenge.user_id)
    db.refresh(challenge)
    if challenge.used_at is not None or challenge.expires_at <= utc_now():
        audit(db, "password_reset_rejected", user.id)
        db.commit()
        raise invalid
    user.password_hash = password_hash.hash(new_password)
    invalidate_resets(db, user.id)
    revoke_all(db, user.id)
    audit(db, "password_reset_completed", user.id)
    db.commit()
