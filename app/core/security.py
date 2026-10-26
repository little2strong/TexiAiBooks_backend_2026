from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
import hashlib
import hmac

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()
# Spend the same password verification work when an email does not exist.
DUMMY_HASH = password_hash.hash("dummy-password-for-constant-work")


def create_access_token(user_id: UUID, settings: Settings, session_id: UUID | None = None) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "sid": str(session_id or uuid4()),
            "jti": str(uuid4()),
            "type": "access",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str, settings: Settings) -> dict:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        options={"require": ["exp", "iat", "sub", "sid", "jti", "type", "iss", "aud"]},
    )
    if payload["type"] != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    for claim in ("sub", "sid", "jti"):
        if not isinstance(payload[claim], str):
            raise jwt.InvalidTokenError("Invalid identifier type")
        UUID(payload[claim])
    return payload


def decode_subject(token: str, settings: Settings) -> UUID:
    payload = decode_access_token(token, settings)
    return UUID(payload["sub"])


def hash_secret(value: str, settings: Settings) -> str:
    """Keyed hashes also protect low-entropy OTPs and email/IP rate-limit keys."""
    return hmac.new(settings.jwt_secret_key.get_secret_value().encode(), value.encode(), hashlib.sha256).hexdigest()

