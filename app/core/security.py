from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings

ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()
# Spend the same password verification work when an email does not exist.
DUMMY_HASH = password_hash.hash("dummy-password-for-constant-work")


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        },
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_subject(token: str, settings: Settings) -> UUID:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["exp", "iat", "sub"]},
    )
    # PyJWT validates sub's type; UUID validates its actual application meaning.
    return UUID(payload["sub"])

