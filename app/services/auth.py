from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, password_hash
from app.models import User
from app.schemas.user import UserCreate, normalize_email
from app.services.auth_security import audit


def register_user(session: Session, data: UserCreate) -> User:
    duplicate = HTTPException(status_code=409, detail="Email already registered")
    if session.scalar(select(User.id).where(User.email == data.email)) is not None:
        raise duplicate
    user = User(email=str(data.email), password_hash=password_hash.hash(data.password.get_secret_value()))
    session.add(user)
    try:
        session.flush()
        audit(session, "registered", user.id)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        # The constraint also protects concurrent registrations of the same email.
        if getattr(getattr(exc.orig, "diag", None), "constraint_name", None) == "uq_users_email":
            raise duplicate from None
        raise
    session.refresh(user)
    return user


def authenticate_user(session: Session, email: str, password: str) -> User:
    invalid = HTTPException(
        status_code=401, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        normalized = normalize_email(email)
    except ValueError:
        normalized = None
    user = session.scalar(select(User).where(User.email == normalized).with_for_update()
                          .execution_options(populate_existing=True)) if normalized else None
    # Avoid expensive Argon2 work on unbounded input; passwords use 8-128 characters.
    if not 8 <= len(password) <= 128:
        audit(session, "login_failed")
        session.commit()
        raise invalid
    valid = password_hash.verify(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        audit(session, "login_failed", user.id if user else None)
        session.commit()
        raise invalid
    return user

