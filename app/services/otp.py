from datetime import timedelta
import hmac
import secrets
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update

from app.core.security import hash_secret
from app.models import AuthChallenge
from app.models.common import utc_now
from app.services.auth_security import audit
from app.services.sessions import lock_user

OTP_ATTEMPT_LIMIT = 5


def send_otp(db, auth, phone, settings, delivery):
    lock_user(db, auth.user.id)
    db.execute(update(AuthChallenge).where(AuthChallenge.user_id == auth.user.id,
        AuthChallenge.kind == "phone_verification", AuthChallenge.used_at.is_(None)).values(used_at=utc_now()))
    code = f"{secrets.randbelow(1_000_000):06d}"
    challenge_id = uuid4()
    challenge = AuthChallenge(id=challenge_id, kind="phone_verification", user_id=auth.user.id, session_id=auth.device.id,
        target_hash=hash_secret("phone:" + phone, settings), token_hash=hash_secret(f"otp:{challenge_id}:{code}", settings),
        expires_at=utc_now() + timedelta(minutes=5))
    db.add(challenge)
    db.flush()
    try:
        delivery.send_code(phone, code)
    except Exception:
        db.rollback()
        audit(db, "otp_delivery_failed", auth.user.id, auth.device.id)
        db.commit()
        raise HTTPException(503, "Delivery temporarily unavailable") from None
    audit(db, "otp_sent", auth.user.id, auth.device.id)
    db.commit()
    return {"challenge_id": challenge.id, "expires_in": 300}


def verify_otp(db, auth, challenge_id, code, settings):
    lock_user(db, auth.user.id)
    challenge = db.scalar(select(AuthChallenge).where(AuthChallenge.id == challenge_id,
        AuthChallenge.user_id == auth.user.id, AuthChallenge.session_id == auth.device.id,
        AuthChallenge.kind == "phone_verification").with_for_update())
    if challenge is None:
        audit(db, "otp_rejected", auth.user.id, auth.device.id)
        db.commit()
        raise HTTPException(400, "Invalid or expired code")
    if challenge.used_at is not None or challenge.expires_at <= utc_now() or challenge.attempts >= OTP_ATTEMPT_LIMIT:
        audit(db, "otp_rejected", auth.user.id, auth.device.id)
        db.commit()
        raise HTTPException(400, "Invalid or expired code")
    challenge.attempts += 1
    valid = hmac.compare_digest(challenge.token_hash, hash_secret(f"otp:{challenge.id}:{code}", settings))
    if valid:
        challenge.used_at = utc_now()
    audit(db, "otp_verified" if valid else "otp_rejected", auth.user.id, auth.device.id)
    db.commit()
    if not valid:
        raise HTTPException(400, "Invalid or expired code")
    # This proves delivery only; it never creates a login session or replaces a password.
    return {"verified": True}
