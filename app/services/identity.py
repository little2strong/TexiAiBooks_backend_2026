"""OIDC ID-token verification. Production paths always verify provider signatures."""

from datetime import timedelta
import hashlib
import hmac
import secrets

from fastapi import HTTPException
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError, PyJWKClientError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_secret, password_hash
from app.models import AuthChallenge, ExternalIdentity, User
from app.models.common import utc_now
from app.schemas.user import normalize_email
from app.services.auth_security import audit
from app.services.sessions import lock_user, new_session

PROVIDERS = {
    "google": ("https://www.googleapis.com/oauth2/v3/certs", ["https://accounts.google.com", "accounts.google.com"]),
    "apple": ("https://appleid.apple.com/auth/keys", ["https://appleid.apple.com"]),
}


class IdentityVerifier:
    def __init__(self, settings):
        self.settings = settings
        self.clients = {name: PyJWKClient(url, timeout=5, lifespan=300) for name, (url, _) in PROVIDERS.items()}

    def require_configured(self, provider):
        ids = getattr(self.settings, f"{provider}_client_ids")
        if not ids:
            raise HTTPException(503, "Identity provider is not configured")
        return ids

    def verify(self, provider, token):
        audiences = self.require_configured(provider)
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise jwt.InvalidTokenError()
            key = self.clients[provider].get_signing_key_from_jwt(token).key
            claims = jwt.decode(token, key, algorithms=["RS256"], audience=audiences,
                issuer=PROVIDERS[provider][1],
                options={"require": ["iss", "aud", "exp", "iat", "sub", "nonce"]})
            if not claims["sub"] or len(claims["sub"]) > 255 or not isinstance(claims["nonce"], str):
                raise jwt.InvalidTokenError()
            # Strictly bind multi-audience tokens to an authorized presenter.
            if "azp" in claims and claims["azp"] not in audiences:
                raise jwt.InvalidTokenError()
            if isinstance(claims["aud"], list) and len(claims["aud"]) > 1 and claims.get("azp") not in audiences:
                raise jwt.InvalidTokenError()
            return claims
        except PyJWKClientConnectionError:
            raise HTTPException(503, "Identity verification temporarily unavailable") from None
        except (jwt.InvalidTokenError, PyJWKClientError, ValueError, TypeError):
            raise HTTPException(401, "Invalid identity token") from None


def create_identity_challenge(db, provider, settings):
    # Return a raw nonce for Google, SHA256(raw) for native Apple nonce requests.
    raw = secrets.token_urlsafe(32)
    nonce = hashlib.sha256(raw.encode()).hexdigest() if provider == "apple" else raw
    challenge = AuthChallenge(kind="oidc_" + provider, token_hash=hash_secret("nonce:" + nonce, settings),
                              expires_at=utc_now() + timedelta(minutes=5))
    db.add(challenge)
    db.commit()
    return {"challenge_id": challenge.id, "nonce": nonce, "expires_in": 300}


def provider_login(db, provider, data, settings, verifier):
    claims = verifier.verify(provider, data.id_token.get_secret_value())
    challenge = db.scalar(select(AuthChallenge).where(AuthChallenge.id == data.challenge_id,
        AuthChallenge.kind == "oidc_" + provider).with_for_update())
    if challenge is None or challenge.used_at is not None or challenge.expires_at <= utc_now() or not hmac.compare_digest(
            challenge.token_hash, hash_secret("nonce:" + claims["nonce"], settings)):
        audit(db, "identity_nonce_rejected")
        db.commit()
        raise HTTPException(401, "Invalid identity challenge")
    challenge.used_at = utc_now()
    # Consume before locking a user to keep the global user->challenge lock order.
    db.commit()
    identity = db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider == provider,
                                                        ExternalIdentity.subject == claims["sub"]))
    if identity:
        user = lock_user(db, identity.user_id)
    else:
        # Never link an existing account solely because an email claim matches.
        verified = claims.get("email_verified")
        if not (verified is True or verified == "true"):
            raise HTTPException(401, "Verified provider email is required for registration")
        try:
            email = normalize_email(claims.get("email", ""))
        except ValueError:
            raise HTTPException(401, "Verified provider email is required for registration") from None
        if db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(409, "Use the existing account sign-in method; automatic linking is disabled")
        user = User(email=email, password_hash=password_hash.hash(secrets.token_urlsafe(64)))
        db.add(user)
        try:
            db.flush()
            db.add(ExternalIdentity(user_id=user.id, provider=provider, subject=claims["sub"]))
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Identity registration conflict; start sign-in again") from None
    audit(db, "identity_login", user.id)
    return new_session(db, user, settings, data.device_name)
