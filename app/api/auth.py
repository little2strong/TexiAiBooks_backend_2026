from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select

from app.api.deps import CurrentAuth, SessionDep, SettingsDep
from app.models import DeviceSession
from app.models.common import utc_now
from app.schemas.auth import (ChangePassword, ForgotPassword, OTPSend, OTPVerify, ProviderChallenge,
                              ProviderLogin, Reauthenticate, RefreshRequest, ResetPassword, SessionRead)
from app.schemas.user import Token, UserCreate, UserRead, normalize_email
from app.services.auth import authenticate_user, register_user
from app.services.auth_security import audit, rate_limit
from app.services.delivery import require_delivery
from app.services.identity import create_identity_challenge, provider_login
from app.services.otp import send_otp, verify_otp
from app.services.passwords import change_password, check_password, request_reset, reset_password
from app.services.sessions import lock_user, new_session, revoke_all, rotate_refresh

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=201)
def register(data: UserCreate, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "register", str(data.email), target_limit=5, ip_limit=20)
    return register_user(session, data)


@router.post("/login", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], session: SessionDep,
          settings: SettingsDep, request: Request,
          device_name: Annotated[str, Form(min_length=1, max_length=100)] = "Mobile device"):
    """Form data: username=<email>&password=<password>; optional device_name."""
    try:
        target = normalize_email(form.username)
    except ValueError:
        # Invalid addresses still consume attempts without changing the generic 401.
        target = form.username.strip().lower()
    rate_limit(session, settings, request, "login", target)
    user = authenticate_user(session, form.username, form.password)
    audit(session, "login_succeeded", user.id)
    return new_session(session, user, settings, device_name)


@router.post("/refresh", response_model=Token)
def refresh(data: RefreshRequest, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "refresh", ip_limit=120)
    return rotate_refresh(session, data.refresh_token.get_secret_value(), settings)


@router.post("/logout", status_code=204)
def logout(auth: CurrentAuth, session: SessionDep):
    lock_user(session, auth.user.id)
    device = session.get(DeviceSession, auth.device.id, populate_existing=True)
    device.revoked_at = utc_now()
    audit(session, "logout", auth.user.id, device.id)
    session.commit()


@router.post("/logout-all", status_code=204)
def logout_all(auth: CurrentAuth, session: SessionDep):
    lock_user(session, auth.user.id)
    revoke_all(session, auth.user.id)
    audit(session, "all_sessions_revoked", auth.user.id)
    session.commit()


@router.get("/sessions", response_model=list[SessionRead])
def sessions(auth: CurrentAuth, session: SessionDep,
             limit: Annotated[int, Query(ge=1, le=100)] = 20,
             offset: Annotated[int, Query(ge=0, le=100000)] = 0):
    return session.scalars(select(DeviceSession).where(DeviceSession.user_id == auth.user.id)
                           .order_by(DeviceSession.created_at.desc(), DeviceSession.id.desc()).limit(limit).offset(offset)).all()


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(session_id: UUID, auth: CurrentAuth, session: SessionDep):
    lock_user(session, auth.user.id)
    device = session.scalar(select(DeviceSession).where(DeviceSession.id == session_id,
        DeviceSession.user_id == auth.user.id).with_for_update().execution_options(populate_existing=True))
    if device is None:
        raise HTTPException(404, "Session not found")
    device.revoked_at = utc_now()
    audit(session, "session_revoked", auth.user.id, device.id)
    session.commit()


@router.post("/change-password", status_code=204)
def password_change(data: ChangePassword, auth: CurrentAuth, session: SessionDep,
                    settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "password_change", str(auth.user.id), target_limit=5)
    change_password(session, auth.user.id, data.current_password.get_secret_value(), data.new_password.get_secret_value())


@router.post("/reauthenticate")
def reauthenticate(data: Reauthenticate, auth: CurrentAuth, session: SessionDep,
                   settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "reauthenticate", str(auth.user.id), target_limit=5)
    user = lock_user(session, auth.user.id)
    check_password(session, user, data.password.get_secret_value())
    device = session.get(DeviceSession, auth.device.id, populate_existing=True)
    if device.revoked_at is not None or device.expires_at <= utc_now():
        raise HTTPException(401, "Session is no longer active")
    device.reauthenticated_at = utc_now()
    audit(session, "reauthenticated", user.id, device.id)
    session.commit()
    return {"reauthenticated": True, "expires_in": 300}


@router.post("/forgot-password")
def forgot(data: ForgotPassword, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "forgot_password", data.email, target_limit=3, ip_limit=20)
    delivery = request.app.state.reset_delivery
    require_delivery(delivery)
    request_reset(session, data.email, settings, delivery)
    return {"message": "If the account exists, recovery instructions will be sent"}


@router.post("/reset-password", status_code=204)
def reset(data: ResetPassword, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "reset_password", ip_limit=20)
    reset_password(session, data.token.get_secret_value(), data.new_password.get_secret_value(), settings)


@router.post("/provider-challenge")
def provider_challenge(data: ProviderChallenge, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "provider_challenge", ip_limit=30)
    request.app.state.identity_verifier.require_configured(data.provider)
    return create_identity_challenge(session, data.provider, settings)


@router.post("/providers/{provider}", response_model=Token)
def identity_login(provider: Literal["google", "apple"], data: ProviderLogin,
                   session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "provider_login", ip_limit=30)
    try:
        return provider_login(session, provider, data, settings, request.app.state.identity_verifier)
    except HTTPException:
        audit(session, "identity_login_rejected")
        session.commit()
        raise


@router.post("/otp/send")
def otp_send(data: OTPSend, auth: CurrentAuth, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "otp_send", str(auth.user.id), target_limit=3, ip_limit=10)
    delivery = request.app.state.sms_delivery
    require_delivery(delivery)
    return send_otp(session, auth, data.phone, settings, delivery)


@router.post("/otp/verify")
def otp_verify(data: OTPVerify, auth: CurrentAuth, session: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(session, settings, request, "otp_verify", str(auth.user.id), target_limit=10, ip_limit=30)
    return verify_otp(session, auth, data.challenge_id, data.code.get_secret_value(), settings)
