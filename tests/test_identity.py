"""Real local RSA signatures + stub JWKS transport. No live provider login claims."""

import json
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import jwt
import pytest
from sqlalchemy import select

from app.models import AuthChallenge, ExternalIdentity
from app.models.common import utc_now
from app.services.identity import IdentityVerifier

BASE = "/api/v1/auth"
PASSWORD = "safe-password-123"


@pytest.fixture(scope="session")
def rsa_keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="test-key", alg="RS256", use="sig")
    return private, jwk


@pytest.fixture
def verifier(settings, rsa_keys, monkeypatch):
    settings.google_client_ids = ["test-google-client"]
    settings.apple_client_ids = ["test-apple-client"]
    verifier = IdentityVerifier(settings)
    for client in verifier.clients.values():
        monkeypatch.setattr(client, "fetch_data", lambda: {"keys": [rsa_keys[1]]})
    return verifier


def signed_token(rsa_keys, provider, nonce="test-nonce", **overrides):
    now = int(utc_now().timestamp())
    claims = {"iss": "https://accounts.google.com" if provider == "google" else "https://appleid.apple.com",
        "aud": f"test-{provider}-client", "sub": f"{provider}-stable-subject", "iat": now, "exp": now + 300,
        "nonce": nonce, "email": f"{provider}-user@example.com", "email_verified": True}
    claims.update(overrides)
    return jwt.encode(claims, rsa_keys[0], algorithm="RS256", headers={"kid": "test-key"})


@pytest.mark.parametrize("provider", ["google", "apple"])
def test_real_signed_id_tokens_are_validated(verifier, rsa_keys, provider):
    token = signed_token(rsa_keys, provider)
    assert verifier.verify(provider, token)["sub"] == f"{provider}-stable-subject"


@pytest.mark.parametrize("provider", ["google", "apple"])
@pytest.mark.parametrize("kind", ["audience", "issuer", "expired", "future", "signature", "algorithm", "unknown_kid",
                                  "missing_nonce", "subject_type", "empty_subject", "azp", "multiple_audiences"])
def test_identity_token_claim_and_signature_rejections(verifier, rsa_keys, provider, kind):
    kwargs = {}
    if kind == "audience":
        kwargs["aud"] = "attacker-client"
    elif kind == "issuer":
        kwargs["iss"] = "https://attacker.example"
    elif kind == "expired":
        kwargs["exp"] = int(utc_now().timestamp()) - 1
    elif kind == "future":
        kwargs["iat"] = int(utc_now().timestamp()) + 1000
    elif kind == "subject_type":
        kwargs["sub"] = 123
    elif kind == "empty_subject":
        kwargs["sub"] = ""
    elif kind == "azp":
        kwargs["azp"] = "attacker"
    elif kind == "multiple_audiences":
        kwargs["aud"] = [f"test-{provider}-client", "attacker"]
    token = signed_token(rsa_keys, provider, **kwargs)
    if kind in ("signature", "algorithm", "unknown_kid", "missing_nonce"):
        claims = jwt.decode(token, options={"verify_signature": False})
        key = rsa_keys[0]
        algorithm = "RS256"
        kid = "test-key"
        if kind == "signature":
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        elif kind == "algorithm":
            key, algorithm = "attacker-secret-12345678901234567890", "HS256"
        elif kind == "unknown_kid":
            kid = "untrusted-key"
        else:
            del claims["nonce"]
        token = jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})
    with pytest.raises(HTTPException) as error:
        verifier.verify(provider, token)
    assert error.value.status_code == 401


def test_jwks_network_failure_is_controlled(verifier, rsa_keys, monkeypatch):
    from jwt.exceptions import PyJWKClientConnectionError

    def broken(token):
        raise PyJWKClientConnectionError("private-network-detail")
    monkeypatch.setattr(verifier.clients["google"], "get_signing_key_from_jwt", broken)
    with pytest.raises(HTTPException) as error:
        verifier.verify("google", signed_token(rsa_keys, "google"))
    assert error.value.status_code == 503 and "private" not in error.value.detail


@pytest.mark.postgres
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_provider_api_new_and_returning_login_with_single_use_nonce(client, verifier, rsa_keys, provider, db_session):
    client.app.state.identity_verifier = verifier
    challenge = client.post(BASE + "/provider-challenge", json={"provider": provider}).json()
    token = signed_token(rsa_keys, provider, nonce=challenge["nonce"])
    body = {"id_token": token, "challenge_id": challenge["challenge_id"]}
    first = client.post(BASE + "/providers/" + provider, json=body)
    assert first.status_code == 200, first.text
    assert client.post(BASE + "/providers/" + provider, json=body).status_code == 401
    auth = {"Authorization": "Bearer " + first.json()["access_token"]}
    user_id = client.get("/api/v1/users/me", headers=auth).json()["id"]
    challenge2 = client.post(BASE + "/provider-challenge", json={"provider": provider}).json()
    # Existing subject identifies the account even if provider email is subsequently absent.
    token2 = signed_token(rsa_keys, provider, nonce=challenge2["nonce"], email=None, email_verified=False)
    second = client.post(BASE + "/providers/" + provider, json={"id_token": token2, "challenge_id": challenge2["challenge_id"]})
    assert second.status_code == 200
    auth2 = {"Authorization": "Bearer " + second.json()["access_token"]}
    assert client.get("/api/v1/users/me", headers=auth2).json()["id"] == user_id
    assert len(db_session.scalars(select(ExternalIdentity)).all()) == 1


@pytest.mark.postgres
@pytest.mark.parametrize("kind", ["wrong_nonce", "wrong_provider", "expired_challenge", "wrong_challenge", "unverified_email", "missing_email", "numeric_verified", "existing_email"])
def test_provider_api_does_not_bypass_challenge_or_link_accounts(client, verifier, rsa_keys, db_session, kind):
    client.app.state.identity_verifier = verifier
    challenge = client.post(BASE + "/provider-challenge", json={"provider": "google"}).json()
    overrides = {}
    challenge_id = challenge["challenge_id"]
    nonce = challenge["nonce"]
    if kind == "wrong_nonce":
        nonce = "other-nonce"
    elif kind == "wrong_provider":
        db_session.get(AuthChallenge, UUID(challenge_id)).kind = "oidc_apple"
        db_session.commit()
    elif kind == "expired_challenge":
        from datetime import timedelta
        db_session.get(AuthChallenge, UUID(challenge_id)).expires_at = utc_now() - timedelta(seconds=1)
        db_session.commit()
    elif kind == "wrong_challenge":
        from uuid import uuid4
        challenge_id = str(uuid4())
    elif kind == "unverified_email":
        overrides["email_verified"] = False
    elif kind == "numeric_verified":
        overrides["email_verified"] = 1
    elif kind == "missing_email":
        overrides["email"] = None
    else:
        client.post(BASE + "/register", json={"email": "google-user@example.com", "password": PASSWORD})
    token = signed_token(rsa_keys, "google", nonce=nonce, **overrides)
    response = client.post(BASE + "/providers/google", json={"id_token": token, "challenge_id": challenge_id})
    assert response.status_code == (409 if kind == "existing_email" else 401)
    assert db_session.scalar(select(ExternalIdentity.id)) is None
