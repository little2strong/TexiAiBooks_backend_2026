from typing import Annotated
from uuid import UUID
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import decode_access_token
from app.db import get_session
from app.models import User, DeviceSession
from app.models.common import utc_now

SessionDep = Annotated[Session, Depends(get_session)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def request_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(request_settings)]


@dataclass
class AuthContext:
    user: User
    device: DeviceSession


def current_auth(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep, settings: SettingsDep, request: Request
) -> AuthContext:
    invalid = HTTPException(
        status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        claims = decode_access_token(token, settings)
        subject = UUID(claims["sub"])
        session_id = UUID(claims["sid"])
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        raise invalid from None
    user = session.get(User, subject)
    if user is None:
        raise invalid
    device = session.get(DeviceSession, session_id)
    if device is None or device.user_id != user.id or device.revoked_at is not None or device.expires_at <= utc_now():
        raise invalid
    request.state.device_id = device.id
    return AuthContext(user, device)


CurrentAuth = Annotated[AuthContext, Depends(current_auth)]


def current_user(auth: CurrentAuth) -> User:
    return auth.user


CurrentUser = Annotated[User, Depends(current_user)]

