from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from sqlalchemy import select

from app.core.security import hash_secret
from app.models import AuthChallenge, DeviceSession, RefreshCredential, SecurityEvent, User
from app.models.common import utc_now

pytestmark = pytest.mark.postgres
BASE = "/api/v1/auth"
PASSWORD = "safe-password-123"
NEW_PASSWORD = "new-safe-password-456"


def login(client, email="driver@example.com", password=PASSWORD, device_name="Test phone"):
    response = client.post(BASE + "/login", data={"username": email, "password": password, "device_name": device_name})
    assert response.status_code == 200, response.text
    return response.json()


def headers(pair):
    return {"Authorization": "Bearer " + pair["access_token"]}


class FakeResetDelivery:
    enabled = True

    def __init__(self):
        self.messages = []

    def send_reset(self, email, token):
        self.messages.append((email, token))


class FakeSMS:
    enabled = True

    def __init__(self):
        self.messages = []

    def send_code(self, phone, code):
        self.messages.append((phone, code))


@pytest.fixture
def reset_delivery(client):
    adapter = FakeResetDelivery()
    client.app.state.reset_delivery = adapter
    return adapter


@pytest.fixture
def sms_delivery(client):
    adapter = FakeSMS()
    client.app.state.sms_delivery = adapter
    return adapter


def test_rotation_stores_only_hashes_and_revokes_family_on_replay(client, account, db_session, settings):
    pair = login(client)
    raw = pair["refresh_token"]
    stored = db_session.scalar(select(RefreshCredential).where(
        RefreshCredential.session_id == UUID(pair["session_id"])))
    assert stored.token_hash == hash_secret("refresh:" + raw, settings)
    assert raw not in stored.token_hash
    rotated = client.post(BASE + "/refresh", json={"refresh_token": raw})
    assert rotated.status_code == 200
    new = rotated.json()
    assert new["refresh_token"] != raw and new["session_id"] == pair["session_id"]
    assert client.get("/api/v1/users/me", headers=headers(new)).status_code == 200
    assert client.post(BASE + "/refresh", json={"refresh_token": raw}).status_code == 401
    assert client.get("/api/v1/users/me", headers=headers(new)).status_code == 401
    assert client.post(BASE + "/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 401
    # Replay affects only the device family, not a separate login.
    assert client.get("/api/v1/users/me", headers=account[1]).status_code == 200
    assert "refresh_replay" in db_session.scalars(select(SecurityEvent.event)).all()


@pytest.mark.parametrize("action", ["/logout", "/logout-all"])
def test_logout_rejects_access_and_refresh(client, account, action):
    pair = login(client)
    assert client.post(BASE + action, headers=headers(pair)).status_code == 204
    assert client.get("/api/v1/users/me", headers=headers(pair)).status_code == 401
    assert client.post(BASE + "/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    expected = 401 if action == "/logout-all" else 200
    assert client.get("/api/v1/users/me", headers=account[1]).status_code == expected


def test_sessions_are_owner_scoped_and_individually_revocable(client, account):
    own_pair = login(client)
    client.post(BASE + "/register", json={"email": "bob@example.com", "password": PASSWORD})
    other_pair = login(client, "bob@example.com")
    listing = client.get(BASE + "/sessions", headers=account[1])
    assert listing.status_code == 200 and len(listing.json()) == 2
    assert all(row["id"] != other_pair["session_id"] for row in listing.json())
    assert "token_hash" not in listing.text and "refresh_token" not in listing.text
    path = BASE + "/sessions/" + other_pair["session_id"]
    assert client.delete(path, headers=account[1]).status_code == 404
    assert client.delete(BASE + "/sessions/" + str(uuid4()), headers=account[1]).status_code == 404
    assert client.delete(BASE + "/sessions/" + own_pair["session_id"], headers=account[1]).status_code == 204
    assert client.get("/api/v1/users/me", headers=headers(own_pair)).status_code == 401
    assert len(client.get(BASE + "/sessions?limit=1&offset=1", headers=account[1]).json()) == 1


@pytest.mark.parametrize("kind", ["expired_session", "revoked_session", "expired_jwt", "wrong_issuer", "wrong_audience",
                                  "wrong_type", "missing_sid", "foreign_sid", "unknown_sid", "numeric_sid", "future_iat", "invalid_jti"])
def test_access_claims_and_server_session_validation(client, account, settings, db_session, kind):
    pair = login(client)
    claims = jwt.decode(pair["access_token"], settings.jwt_secret_key.get_secret_value(),
                        algorithms=["HS256"], audience=settings.jwt_audience)
    if kind in ("expired_session", "revoked_session"):
        device = db_session.get(DeviceSession, UUID(pair["session_id"]))
        if kind == "expired_session":
            device.expires_at = utc_now() - timedelta(seconds=1)
        else:
            device.revoked_at = utc_now()
        db_session.commit()
    elif kind == "expired_jwt":
        claims["exp"] = int((utc_now() - timedelta(seconds=1)).timestamp())
    elif kind == "future_iat":
        claims["iat"] = int((utc_now() + timedelta(hours=1)).timestamp())
    elif kind == "wrong_issuer":
        claims["iss"] = "attacker"
    elif kind == "wrong_audience":
        claims["aud"] = "other-service"
    elif kind == "wrong_type":
        claims["type"] = "refresh"
    elif kind == "missing_sid":
        del claims["sid"]
    elif kind == "invalid_jti":
        claims["jti"] = "broken"
    elif kind == "unknown_sid":
        claims["sid"] = str(uuid4())
    elif kind == "numeric_sid":
        claims["sid"] = 123
    else:
        client.post(BASE + "/register", json={"email": "other@example.com", "password": PASSWORD})
        claims["sid"] = login(client, "other@example.com")["session_id"]
    encoded = jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm="HS256")
    assert client.get("/api/v1/users/me", headers={"Authorization": "Bearer " + encoded}).status_code == 401


def test_expired_refresh_and_random_refresh_rejected(client, account, db_session):
    pair = login(client)
    device = db_session.get(DeviceSession, UUID(pair["session_id"]))
    device.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    for raw in (pair["refresh_token"], "unknown-refresh-token-value-123456789012345"):
        assert client.post(BASE + "/refresh", json={"refresh_token": raw}).status_code == 401


def test_profile_patch_cannot_change_security_fields_and_survives_login(client, account):
    _, auth = account
    assert client.patch("/api/v1/users/me", headers=auth, json={"display_name": "Taxi driver"}).status_code == 200
    for field in ("id", "email", "password_hash", "user_id"):
        assert client.patch("/api/v1/users/me", headers=auth, json={"display_name": "Other", field: "forged"}).status_code == 422
    assert client.post(BASE + "/logout", headers=auth).status_code == 204
    assert client.get("/api/v1/users/me", headers=headers(login(client))).json()["display_name"] == "Taxi driver"


def test_change_password_requires_current_password_and_revokes_all(client, account, db_session):
    pair = login(client)
    body = {"current_password": "incorrect-password", "new_password": NEW_PASSWORD}
    assert client.post(BASE + "/change-password", headers=account[1], json=body).status_code == 401
    body["current_password"] = PASSWORD
    assert client.post(BASE + "/change-password", headers=account[1], json=body).status_code == 204
    assert client.get("/api/v1/users/me", headers=headers(pair)).status_code == 401
    assert client.post(BASE + "/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    assert client.post(BASE + "/login", data={"username": "driver@example.com", "password": PASSWORD}).status_code == 401
    assert login(client, password=NEW_PASSWORD)
    assert "password_changed" in db_session.scalars(select(SecurityEvent.event)).all()


def test_password_recovery_is_generic_hashed_single_use_and_revokes_all(client, account, reset_delivery, db_session, settings):
    known = client.post(BASE + "/forgot-password", json={"email": " DRIVER@EXAMPLE.COM "})
    unknown = client.post(BASE + "/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == 200 and known.json() == unknown.json()
    assert len(reset_delivery.messages) == 1
    raw = reset_delivery.messages[0][1]
    assert raw not in known.text
    challenge = db_session.scalar(select(AuthChallenge).where(AuthChallenge.kind == "password_reset"))
    assert challenge.token_hash == hash_secret("reset:" + raw, settings)
    body = {"token": raw, "new_password": NEW_PASSWORD}
    assert client.post(BASE + "/reset-password", json=body).status_code == 204
    assert client.post(BASE + "/reset-password", json=body).status_code == 400
    assert client.get("/api/v1/users/me", headers=account[1]).status_code == 401
    assert login(client, password=NEW_PASSWORD)


def test_resend_invalidates_old_recovery_token(client, account, reset_delivery):
    for _ in range(2):
        assert client.post(BASE + "/forgot-password", json={"email": "driver@example.com"}).status_code == 200
    old, new = [message[1] for message in reset_delivery.messages]
    assert client.post(BASE + "/reset-password", json={"token": old, "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post(BASE + "/reset-password", json={"token": new, "new_password": NEW_PASSWORD}).status_code == 204


def test_expired_recovery_is_rejected(client, account, reset_delivery, db_session):
    client.post(BASE + "/forgot-password", json={"email": "driver@example.com"})
    challenge = db_session.scalar(select(AuthChallenge).where(AuthChallenge.kind == "password_reset"))
    challenge.expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert client.post(BASE + "/reset-password", json={"token": reset_delivery.messages[0][1],
        "new_password": NEW_PASSWORD}).status_code == 400


def test_delivery_failure_leaves_no_usable_recovery_challenge(client, account, reset_delivery, db_session):
    def broken(*args):
        raise RuntimeError("SECRET-provider-error")
    reset_delivery.send_reset = broken
    response = client.post(BASE + "/forgot-password", json={"email": "driver@example.com"})
    assert response.status_code == 200 and "SECRET" not in response.text
    assert db_session.scalar(select(AuthChallenge.id).where(AuthChallenge.kind == "password_reset")) is None
    assert "password_reset_delivery_failed" in db_session.scalars(select(SecurityEvent.event)).all()


def test_unconfigured_delivery_and_identity_fail_closed(client, account):
    for email in ("driver@example.com", "missing@example.com"):
        assert client.post(BASE + "/forgot-password", json={"email": email}).status_code == 503
    assert client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"}).status_code == 503
    for provider in ("google", "apple"):
        assert client.post(BASE + "/provider-challenge", json={"provider": provider}).status_code == 503
        assert client.post(BASE + "/providers/" + provider, json={"challenge_id": str(uuid4()),
            "id_token": "invalid-token-1234567890"}).status_code == 503


def test_login_rate_limit_persists_and_does_not_trust_forwarded_headers(client, account, db_session):
    for index in range(9):  # account fixture already made one successful attempt for this email.
        response = client.post(BASE + "/login", data={"username": " DRIVER@EXAMPLE.COM ", "password": "incorrect-password"},
                               headers={"X-Forwarded-For": f"192.0.2.{index}"})
        assert response.status_code == 401
    limited = client.post(BASE + "/login", data={"username": "driver@example.com", "password": PASSWORD})
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    assert "rate_limit" in db_session.scalars(select(SecurityEvent.event)).all()


def test_otp_single_use_no_secret_disclosure_and_bound_to_session(client, account, sms_delivery, db_session, settings):
    response = client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"})
    assert response.status_code == 200
    phone, code = sms_delivery.messages[0]
    assert code not in response.text and phone not in response.text
    body = {"challenge_id": response.json()["challenge_id"], "code": code}
    challenge = db_session.get(AuthChallenge, UUID(body["challenge_id"]))
    assert challenge.token_hash == hash_secret(f"otp:{challenge.id}:{code}", settings)
    other_device = login(client)
    assert client.post(BASE + "/otp/verify", headers=headers(other_device), json=body).status_code == 400
    assert client.post(BASE + "/otp/verify", headers=account[1], json=body).json() == {"verified": True}
    assert client.post(BASE + "/otp/verify", headers=account[1], json=body).status_code == 400


def test_otp_attempts_and_rate_limits(client, account, sms_delivery, db_session):
    response = client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"})
    challenge_id = response.json()["challenge_id"]
    correct = sms_delivery.messages[-1][1]
    wrong = "000000" if correct != "000000" else "111111"
    for _ in range(5):
        assert client.post(BASE + "/otp/verify", headers=account[1], json={"challenge_id": challenge_id, "code": wrong}).status_code == 400
    assert client.post(BASE + "/otp/verify", headers=account[1], json={"challenge_id": challenge_id, "code": correct}).status_code == 400
    db_session.expire_all()
    assert db_session.get(AuthChallenge, UUID(challenge_id)).attempts == 5
    for _ in range(4):
        assert client.post(BASE + "/otp/verify", headers=account[1], json={"challenge_id": str(uuid4()), "code": wrong}).status_code == 400
    assert client.post(BASE + "/otp/verify", headers=account[1], json={"challenge_id": str(uuid4()), "code": wrong}).status_code == 429
    for _ in range(2):
        assert client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"}).status_code == 200
    assert client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"}).status_code == 429


def test_otp_expiry_resend_and_cross_user_rejection(client, account, sms_delivery, db_session):
    first = client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"}).json()
    old_code = sms_delivery.messages[-1][1]
    second = client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"}).json()
    assert client.post(BASE + "/otp/verify", headers=account[1], json={"challenge_id": first["challenge_id"], "code": old_code}).status_code == 400
    correct = sms_delivery.messages[-1][1]
    client.post(BASE + "/register", json={"email": "other@example.com", "password": PASSWORD})
    other = login(client, "other@example.com")
    body = {"challenge_id": second["challenge_id"], "code": correct}
    assert client.post(BASE + "/otp/verify", headers=headers(other), json=body).status_code == 400
    db_session.get(AuthChallenge, UUID(second["challenge_id"])).expires_at = utc_now() - timedelta(seconds=1)
    db_session.commit()
    assert client.post(BASE + "/otp/verify", headers=account[1], json=body).status_code == 400


def test_reauthentication_accepts_password_only_never_biometric_claims(client, account):
    assert client.post(BASE + "/reauthenticate", headers=account[1], json={"password": "incorrect-password"}).status_code == 401
    assert client.post(BASE + "/reauthenticate", headers=account[1], json={"password": PASSWORD, "biometric_verified": True}).status_code == 422
    response = client.post(BASE + "/reauthenticate", headers=account[1], json={"password": PASSWORD})
    assert response.json() == {"reauthenticated": True, "expires_in": 300}


@pytest.mark.parametrize("path,body", [
    ("/refresh", {"refresh_token": "short-secret"}),
    ("/reset-password", {"token": "short-secret", "new_password": "tiny"}),
    ("/change-password", {"current_password": "tiny", "new_password": "tiny"}),
    ("/otp/verify", {"challenge_id": str(uuid4()), "code": "12345"}),
])
def test_secret_validation_does_not_echo_inputs(client, account, path, body):
    response = client.post(BASE + path, headers=account[1], json=body)
    assert response.status_code == 422
    assert all(value not in response.text for key, value in body.items() if key != "challenge_id")


def test_audit_events_never_contain_credentials(client, account, reset_delivery, sms_delivery, db_session):
    pair = login(client)
    client.post(BASE + "/forgot-password", json={"email": "driver@example.com"})
    client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"})
    rows = db_session.scalars(select(SecurityEvent)).all()
    snapshot = str([{column.name: getattr(row, column.name) for column in SecurityEvent.__table__.columns} for row in rows])
    for value in (PASSWORD, pair["access_token"], pair["refresh_token"], reset_delivery.messages[-1][1],
                  sms_delivery.messages[-1][1], "driver@example.com", "+447700900123"):
        assert value not in snapshot


def test_security_headers_cover_failed_and_successful_auth(client, account):
    for response in (client.get("/api/v1/users/me", headers=account[1]), client.get("/api/v1/users/me")):
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize("method,path,body", [
    ("post", "/auth/logout", None), ("post", "/auth/logout-all", None),
    ("get", "/auth/sessions", None), ("delete", "/auth/sessions/" + str(uuid4()), None),
    ("post", "/auth/change-password", {"current_password": PASSWORD, "new_password": NEW_PASSWORD}),
    ("post", "/auth/reauthenticate", {"password": PASSWORD}),
    ("post", "/auth/otp/send", {"phone": "+447700900123"}),
    ("post", "/auth/otp/verify", {"challenge_id": str(uuid4()), "code": "123456"}),
    ("patch", "/users/me", {"display_name": "Driver"}),
])
def test_new_protected_routes_require_authentication(client, method, path, body):
    kwargs = {"json": body} if body is not None else {}
    assert getattr(client, method)("/api/v1" + path, **kwargs).status_code == 401


@pytest.mark.parametrize("code", ["abcdef", "１２３４５６", "12345 ", 123456, True])
def test_otp_rejects_non_ascii_or_non_string_codes(client, account, code):
    response = client.post(BASE + "/otp/verify", headers=account[1], json={"challenge_id": str(uuid4()), "code": code})
    assert response.status_code == 422


def test_otp_delivery_failure_rolls_back_without_exposing_details(client, account, sms_delivery, db_session):
    def broken(*args):
        raise RuntimeError("SECRET-SMS-provider-detail")
    sms_delivery.send_code = broken
    response = client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"})
    assert response.status_code == 503 and "SECRET" not in response.text
    assert db_session.scalar(select(AuthChallenge.id).where(AuthChallenge.kind == "phone_verification")) is None


def test_password_change_invalidates_pending_reset(client, account, reset_delivery):
    client.post(BASE + "/forgot-password", json={"email": "driver@example.com"})
    raw = reset_delivery.messages[-1][1]
    assert client.post(BASE + "/change-password", headers=account[1], json={"current_password": PASSWORD,
        "new_password": NEW_PASSWORD}).status_code == 204
    assert client.post(BASE + "/reset-password", json={"token": raw, "new_password": "another-password-789"}).status_code == 400


def test_recovery_and_reauthentication_limits(client, account, reset_delivery):
    for _ in range(3):
        assert client.post(BASE + "/forgot-password", json={"email": "driver@example.com"}).status_code == 200
    assert client.post(BASE + "/forgot-password", json={"email": "driver@example.com"}).status_code == 429
    for _ in range(5):
        assert client.post(BASE + "/reauthenticate", headers=account[1], json={"password": "wrong-password"}).status_code == 401
    assert client.post(BASE + "/reauthenticate", headers=account[1], json={"password": PASSWORD}).status_code == 429


def test_fixed_window_limit_resets_on_next_window(client, account, monkeypatch):
    from app.services import auth_security

    monkeypatch.setattr(auth_security.time, "time", lambda: 1_800_000_000)
    for _ in range(10):
        assert client.post(BASE + "/login", data={"username": "window@example.com", "password": PASSWORD}).status_code == 401
    assert client.post(BASE + "/login", data={"username": "window@example.com", "password": PASSWORD}).status_code == 429
    monkeypatch.setattr(auth_security.time, "time", lambda: 1_800_000_900)
    assert client.post(BASE + "/login", data={"username": "window@example.com", "password": PASSWORD}).status_code == 401


@pytest.mark.parametrize("canonical,alias", [
    ("driver@b\u00fccher.de", "driver@xn--bcher-kva.de"),
    ("dr\u00edver@example.com", "dri\u0301ver@example.com"),
])
def test_equivalent_email_spellings_share_login_rate_limit(client, canonical, alias):
    assert client.post(BASE + "/register", json={"email": canonical, "password": PASSWORD}).status_code == 201
    for index in range(10):
        response = client.post(BASE + "/login", data={"username": canonical if index % 2 else alias,
                                                      "password": "incorrect-password"})
        assert response.status_code == 401
    limited = client.post(BASE + "/login", data={"username": alias, "password": PASSWORD})
    assert limited.status_code == 429


def test_unknown_otp_challenge_is_audited_without_disclosing_code(client, account, db_session):
    response = client.post(BASE + "/otp/verify", headers=account[1],
                           json={"challenge_id": str(uuid4()), "code": "123456"})
    assert response.status_code == 400
    events = db_session.scalars(select(SecurityEvent).where(SecurityEvent.event == "otp_rejected")).all()
    assert len(events) == 1 and str(events[0].user_id) == account[0]["id"]


def test_failed_sms_delivery_is_audited_after_rollback(client, account, sms_delivery, db_session):
    def broken(*args):
        raise RuntimeError("private provider exception")
    sms_delivery.send_code = broken
    response = client.post(BASE + "/otp/send", headers=account[1], json={"phone": "+447700900123"})
    assert response.status_code == 503 and "private" not in response.text
    assert db_session.scalar(select(AuthChallenge.id).where(AuthChallenge.kind == "phone_verification")) is None
    events = db_session.scalars(select(SecurityEvent).where(SecurityEvent.event == "otp_delivery_failed")).all()
    assert len(events) == 1 and str(events[0].user_id) == account[0]["id"]
