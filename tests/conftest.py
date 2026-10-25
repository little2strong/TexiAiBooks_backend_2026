"""PostgreSQL integration tests own a disposable container, never the dev database."""

from contextlib import suppress
import json
import os
import secrets
import subprocess
import time
from uuid import uuid4

# Allow test collection without a local .env. These values affect this process only.
os.environ.setdefault("POSTGRES_PASSWORD", "test-process-password-not-used-for-development")
os.environ.setdefault("JWT_SECRET_KEY", "test-process-signing-key-at-least-32-characters")

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.config import ROOT, Settings
from app.main import create_app


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        postgres_password="isolated-test-password-123456789",
        jwt_secret_key="isolated-test-signing-key-1234567890123456789012345678901234567890",
    )


def docker(*args: str, timeout: int = 30, env=None) -> str:
    try:
        result = subprocess.run(
            ["docker", *args], capture_output=True, text=True, timeout=timeout, env=env
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.fail("Docker unavailable or timed out. Start Docker Desktop's Linux engine.")
    if result.returncode:
        # Do not include CLI output, which might contain environment or credentials.
        pytest.fail("Docker command failed. Check docker info and availability of postgres:16.")
    return result.stdout.strip()


@pytest.fixture(scope="session")
def postgres_engine():
    docker("info", "--format", "{{.ServerVersion}}", timeout=15)
    name = f"texi-test-{uuid4().hex}"
    database = f"texi_test_{uuid4().hex}"
    password = secrets.token_urlsafe(32)
    env = dict(os.environ, POSTGRES_PASSWORD=password)
    container_id = None
    engine = None
    try:
        # tmpfs and no named volume: test data lives only in this owned container.
        container_id = docker(
            "run", "--detach", "--rm", "--name", name,
            "--publish", "127.0.0.1::5432",
            "--tmpfs", "/var/lib/postgresql/data",
            "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=test_user",
            "--env", f"POSTGRES_DB={database}", "postgres:16", timeout=180, env=env,
        )
        ports = json.loads(docker("inspect", "--format", "{{json .NetworkSettings.Ports}}", container_id))
        port = int(ports["5432/tcp"][0]["HostPort"])
        config = Settings(
            _env_file=None, postgres_db=database, postgres_user="test_user",
            postgres_password=password, postgres_port=port,
            jwt_secret_key="isolated-test-signing-key-1234567890123456789012345678901234567890",
        )
        engine = create_engine(
            config.database_url, hide_parameters=True, connect_args={"connect_timeout": 1}
        )
        deadline = time.monotonic() + 60
        while True:
            try:
                with engine.connect() as connection:
                    assert connection.scalar(text("SELECT current_database()")) == database
                break
            except OperationalError:
                if time.monotonic() >= deadline:
                    pytest.fail("Isolated PostgreSQL did not become ready within 60 seconds.")
                time.sleep(0.5)

        migration_config = Config(str(ROOT / "alembic.ini"))
        with engine.begin() as connection:
            migration_config.attributes["connection"] = connection
            command.upgrade(migration_config, "head")
            assert MigrationContext.configure(connection).get_current_revision() == (
                ScriptDirectory.from_config(migration_config).get_current_head()
            )
            command.check(migration_config)
        yield engine
    finally:
        if engine is not None:
            engine.dispose()
        if container_id:
            # Exact ID returned by our docker run; no development resources touched.
            with suppress(subprocess.TimeoutExpired):
                subprocess.run(
                    ["docker", "rm", "--force", container_id],
                    capture_output=True, timeout=30,
                )


@pytest.fixture
def session_factory(postgres_engine):
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        factory = sessionmaker(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        yield factory
        transaction.rollback()


@pytest.fixture
def db_session(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def client(settings, session_factory):
    with TestClient(create_app(settings, session_factory)) as client:
        yield client


@pytest.fixture
def account(client):
    credentials = {"email": "driver@example.com", "password": "safe-password-123"}
    response = client.post("/api/v1/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    login = client.post(
        "/api/v1/auth/login",
        data={"username": credentials["email"], "password": credentials["password"]},
    )
    assert login.status_code == 200, login.text
    return response.json(), {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
def expense_data():
    return {"amount_pence": 1250, "category": "fuel", "expense_date": "2026-10-25", "note": "Fuel stop"}
