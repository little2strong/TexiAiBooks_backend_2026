from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import decode_subject
from app.db import get_session
from app.models import User

SessionDep = Annotated[Session, Depends(get_session)]
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def request_settings(request: Request) -> Settings:
    return request.app.state.settings


SettingsDep = Annotated[Settings, Depends(request_settings)]


def current_user(
    token: Annotated[str, Depends(oauth2_scheme)], session: SessionDep, settings: SettingsDep
) -> User:
    invalid = HTTPException(
        status_code=401, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        subject: UUID = decode_subject(token, settings)
    except (InvalidTokenError, ValueError, TypeError, KeyError):
        raise invalid from None
    user = session.get(User, subject)
    if user is None:
        raise invalid
    return user


CurrentUser = Annotated[User, Depends(current_user)]

