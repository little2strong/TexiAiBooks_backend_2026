from contextlib import contextmanager
from io import StringIO
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import jwt
import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from app.core.config import ROOT, Settings
from app.core.security import create_access_token, decode_subject
from app.main import create_app
from app.schemas.expense import ExpenseCreate, ExpensePatch
from app.schemas.user import UserCreate, normalize_email


def test_database_url_escapes_credentials(settings):
    settings.postgres_password = settings.postgres_password.__class__("password@:/% +with-characters")
    url = settings.database_url
    assert make_url(url.render_as_string(hide_password=False)) == url
    assert url.drivername == "postgresql+psycopg"


def test_settings_reject_example_secrets(monkeypatch):
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=ROOT / ".env.example")


def test_email_normalization():
    assert normalize_email("  DRIVER@Example.COM  ") == "driver@example.com"


@pytest.mark.parametrize("password", ["short", "a" * 129])
def test_password_limits(password):
    with pytest.raises(ValidationError):
        UserCreate(email="driver@example.com", password=password)


@pytest.mark.parametrize("amount", [0, -1, 1.5, "100", True, 2_147_483_648, None])
def test_strict_amount_validation(amount, expense_data):
    with pytest.raises(ValidationError):
        ExpenseCreate(**(expense_data | {"amount_pence": amount}))


@pytest.mark.parametrize("patch", [{}, {"category": None}, {"expense_date": None}, {"amount_pence": None}, {"currency": None}, {"owner_id": str(uuid4())}])
def test_strict_patch_validation(patch):
    with pytest.raises(ValidationError):
        ExpensePatch(**patch)


def test_patch_can_clear_note():
    assert ExpensePatch(note=None).model_dump(exclude_unset=True) == {"note": None}


def test_token_round_trip(settings):
    subject = uuid4()
    token = create_access_token(subject, settings)
    assert decode_subject(token, settings) == subject
    claims = jwt.decode(token, settings.jwt_secret_key.get_secret_value(), algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 1800


def test_db_failure_is_controlled_and_liveness_independent(settings):
    class BrokenSession:
        def execute(self, statement):
            raise OperationalError("SELECT 1", {}, Exception("SECRET_CONNECTION_DETAILS"))

    @contextmanager
    def broken_factory():
        yield BrokenSession()

    with TestClient(create_app(settings, broken_factory)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/health/db")
        assert response.status_code == 503
        assert response.json() == {"detail": "Database unavailable"}
        assert "SECRET" not in response.text
        assert client.get("/health").status_code == 200


def test_openapi_and_validation_do_not_require_database(settings):
    def forbidden_factory():
        raise AssertionError("Database session should not be needed")

    with TestClient(create_app(settings, forbidden_factory)) as client:
        schema = client.get("/openapi.json").json()
        assert schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"] == "/api/v1/auth/login"
        assert client.get("/docs").status_code == 200
        assert client.get("/api/v1/users/me").status_code == 401


def test_offline_migration_sql_has_expected_tables():
    output = StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE users" in sql
    assert "CREATE TABLE expenses" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "uq_users_email" in sql
