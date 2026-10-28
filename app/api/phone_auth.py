from datetime import timedelta
import hmac
import secrets
import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, text, update

from app.api.deps import SessionDep, SettingsDep
from app.models import User
from app.models.books import PhoneChallenge, PhoneIdentity
from app.models.common import utc_now
from app.core.security import hash_secret, password_hash
from app.schemas.books import LoginChallengeInput, LoginCode
from app.services.auth_security import audit, rate_limit
from app.services.books import rows
from app.services.delivery import require_delivery
from app.services.sessions import new_session
from app.services.vault import decrypt, encrypt

router = APIRouter(prefix="/auth/challenges", tags=["phone authentication"])


def phone_lock(db, value):
    # Serialize the destination before an account exists; transaction-scoped lock.
    key = int(value[:15], 16)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


def send(db, phone, purpose, settings, delivery):
    require_delivery(delivery)
    if not settings.phone_identity_hmac_key:
        raise HTTPException(503,"Stable phone identity hashing key is not configured")
    hashed = hmac.new(settings.phone_identity_hmac_key.get_secret_value().encode(), phone.encode(), hashlib.sha256).hexdigest()
    phone_lock(db, hashed)
    db.execute(update(PhoneChallenge).where(PhoneChallenge.phone_hash == hashed,
        PhoneChallenge.used_at.is_(None)).values(used_at=utc_now()))
    code, id = f"{secrets.randbelow(1_000_000):06d}", uuid4()
    row = PhoneChallenge(id=id, phone_hash=hashed, destination=encrypt(settings,phone), purpose=purpose,
        code_hash=hash_secret(f"phone_login:{id}:{code}",settings), expires_at=utc_now()+timedelta(minutes=5),
        resend_at=utc_now()+timedelta(seconds=60))
    db.add(row)
    db.flush()
    try:
        delivery.send_code(phone,code)
    except Exception:
        db.rollback()
        raise HTTPException(503,"SMS delivery unavailable") from None
    audit(db,"phone_login_code_sent")
    db.commit()
    return {"challenge_id":id,"destination_masked":"*******"+phone[-4:],"expires_at":row.expires_at,"resend_after_seconds":60}


@router.post("",operation_id="A01",status_code=201)
def challenge(data: LoginChallengeInput, db: SessionDep, settings: SettingsDep, request: Request):
    rate_limit(db,settings,request,"phone_challenge",data.phone,target_limit=3,ip_limit=10)
    return send(db,data.phone,data.purpose,settings,request.app.state.sms_delivery)


@router.post("/{id}/resend",operation_id="A07",status_code=201)
def resend(id: UUID,db: SessionDep,settings: SettingsDep,request: Request):
    rate_limit(db,settings,request,"phone_resend",str(id),target_limit=3,ip_limit=10)
    row=db.get(PhoneChallenge,id)
    if not row: raise HTTPException(400,"Invalid or expired challenge")
    phone_lock(db,row.phone_hash)
    db.refresh(row)
    if row.used_at is not None or row.expires_at<=utc_now(): raise HTTPException(400,"Invalid or expired challenge")
    if row.resend_at>utc_now(): raise HTTPException(429,"Wait before resending",headers={"Retry-After":"60"})
    return send(db,decrypt(settings,row.destination),row.purpose,settings,request.app.state.sms_delivery)


@router.post("/{id}/verify",operation_id="A02")
def verify(id: UUID,data: LoginCode,db: SessionDep,settings: SettingsDep,request: Request):
    rate_limit(db,settings,request,"phone_verify",str(id),target_limit=10,ip_limit=30)
    row=db.get(PhoneChallenge,id)
    if not row: raise HTTPException(400,"Invalid or expired challenge")
    phone_lock(db,row.phone_hash)
    db.refresh(row)
    invalid=row.used_at is not None or row.expires_at<=utc_now() or row.attempts>=5
    if not invalid:
        row.attempts+=1
        invalid=not hmac.compare_digest(row.code_hash,hash_secret(f"phone_login:{id}:{data.code.get_secret_value()}",settings))
    if invalid:
        audit(db,"phone_code_rejected")
        db.commit()
        raise HTTPException(400,"Invalid or expired challenge")
    row.used_at=utc_now()
    identity=db.scalar(select(PhoneIdentity).where(PhoneIdentity.phone_hash==row.phone_hash))
    if identity is None:
        if row.purpose != "sign_up":
            db.commit()
            raise HTTPException(400,"Invalid or expired challenge")
        user=User(email=None,password_hash=password_hash.hash(secrets.token_urlsafe(48)))
        db.add(user)
        db.flush()
        db.add(PhoneIdentity(owner_id=user.id,phone_hash=row.phone_hash))
    else:
        user=db.get(User,identity.owner_id)
    return new_session(db,user,settings)
