from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
import jwt
import pytest

from app.core.security import password_hash
from app.models import User
from app.schemas.user import UserCreate
from app.services.auth import register_user

pytestmark = pytest.mark.postgres


def test_registration_normalizes_and_hashes(client, db_session):
    response = client.post("/api/v1/auth/register", json={"email": " DRIVER@Example.COM ", "password": "safe-password-123"})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "driver@example.com"
    assert set(body) == {"id", "email", "created_at", "updated_at"}
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
    user = db_session.get(User, UUID(body["id"]))
    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != "safe-password-123"
    assert password_hash.verify("safe-password-123", user.password_hash)
    duplicate = client.post("/api/v1/auth/register", json={"email": "driver@example.com", "password": "another-password"})
    assert duplicate.status_code == 409


def test_database_duplicate_race_is_handled(db_session, monkeypatch):
    data = UserCreate(email="race@example.com", password="safe-password-123")
    register_user(db_session, data)
    # Simulate the pre-check missing a concurrent insert; real PostgreSQL rejects it.
    monkeypatch.setattr(db_session, "scalar", lambda statement: None)
    with pytest.raises(HTTPException) as error:
        register_user(db_session, data)
    assert error.value.status_code == 409


@pytest.mark.parametrize("body", [
    {"email": "bad-address", "password": "safe-password-123"},
    {"email": "driver@example.com", "password": "tiny7!"},
    {"email": "driver@example.com", "password": "x" * 129},
    {"email": "driver@example.com", "password": "safe-password-123", "password_hash": "forged"},
])
def test_invalid_registration(client, body):
    response = client.post("/api/v1/auth/register", json=body)
    assert response.status_code == 422
    assert body["password"] not in response.text


def test_login_and_current_user(client, account):
    user, headers = account
    response = client.post("/api/v1/auth/login", data={"username": " DRIVER@EXAMPLE.COM ", "password": "safe-password-123"})
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["expires_in"] == 900
    assert response.headers["cache-control"] == "no-store"
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json() == user | {"display_name": None}
    assert "password" not in me.text


@pytest.mark.parametrize("username,password", [
    ("driver@example.com", "wrong-password"), ("unknown@example.com", "wrong-password"),
    ("bad-email", "wrong-password"), ("driver@example.com", "x" * 129),
])
def test_invalid_credentials_are_generic(client, account, username, password):
    response = client.post("/api/v1/auth/login", data={"username": username, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid email or password"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_requires_form_data(client):
    assert client.post("/api/v1/auth/login", json={"username": "driver@example.com", "password": "safe-password-123"}).status_code == 422


@pytest.mark.parametrize("kind", ["missing", "invalid", "tampered", "expired", "wrong_algorithm", "bad_subject", "unknown_subject", "missing_exp", "missing_sub", "numeric_sub"])
def test_reject_bad_tokens(client, account, settings, kind):
    user, headers = account
    now = datetime.now(timezone.utc)
    payload = jwt.decode(headers["Authorization"].split()[1], settings.jwt_secret_key.get_secret_value(),
                         algorithms=["HS256"], audience=settings.jwt_audience)
    key = settings.jwt_secret_key.get_secret_value()
    if kind == "missing":
        headers = {}
    elif kind == "invalid":
        headers = {"Authorization": "Bearer not-a-jwt"}
    else:
        algorithm = "HS256"
        if kind == "tampered":
            key = "different-signing-key-long-enough-1234567890"
        elif kind == "expired":
            payload["exp"] = now - timedelta(seconds=1)
        elif kind == "wrong_algorithm":
            algorithm = "HS384"
        elif kind == "bad_subject":
            payload["sub"] = "not-a-uuid"
        elif kind == "numeric_sub":
            payload["sub"] = 123
        elif kind == "unknown_subject":
            payload["sub"] = str(uuid4())
        elif kind == "missing_exp":
            del payload["exp"]
        elif kind == "missing_sub":
            del payload["sub"]
        token = jwt.encode(payload, key, algorithm=algorithm)
        headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
