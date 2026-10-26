"""Real PostgreSQL locks/concurrent connections and additive migration compatibility."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi import HTTPException
import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.core.config import ROOT
from app.core.security import hash_secret, password_hash
from app.models import (AuthChallenge, DeviceSession, ExternalIdentity, RateLimitBucket, RefreshCredential,
                        SecurityEvent, User)
from app.models.common import utc_now
from app.schemas.user import UserCreate
from app.services.auth import register_user
from app.services.auth_security import rate_limit
from app.services.passwords import reset_password
from app.services.sessions import new_session, rotate_refresh

pytestmark = pytest.mark.postgres


@pytest.fixture
def committed_account(postgres_engine, settings):
    factory = sessionmaker(bind=postgres_engine, expire_on_commit=False)
    with factory() as db:
        user = register_user(db, UserCreate(email=f"race-{uuid4().hex}@example.com", password="safe-password-123"))
        pair = new_session(db, user, settings)
        user_id = user.id
    try:
        yield factory, user_id, pair
    finally:
        with factory() as db:
            ids = select(DeviceSession.id).where(DeviceSession.user_id == user_id)
            db.execute(delete(AuthChallenge).where(AuthChallenge.user_id == user_id))
            db.execute(delete(ExternalIdentity).where(ExternalIdentity.user_id == user_id))
            db.execute(delete(SecurityEvent).where(SecurityEvent.user_id == user_id))
            db.execute(delete(RefreshCredential).where(RefreshCredential.session_id.in_(ids)))
            db.execute(delete(DeviceSession).where(DeviceSession.user_id == user_id))
            db.execute(delete(User).where(User.id == user_id))
            db.commit()


def test_concurrent_refresh_can_only_consume_token_once(committed_account, settings):
    factory, user_id, pair = committed_account
    barrier = Barrier(2)

    def rotate():
        with factory() as db:
            barrier.wait(timeout=10)
            try:
                return 200, rotate_refresh(db, pair.refresh_token, settings)
            except HTTPException as error:
                return error.status_code, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(rotate) for _ in range(2)]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(status for status, _ in outcomes) == [200, 401]
    with factory() as db:
        device = db.get(DeviceSession, pair.session_id)
        assert device.revoked_at is not None
        assert len(db.scalars(select(RefreshCredential).where(RefreshCredential.session_id == pair.session_id)).all()) == 2
        winner = next(result for status, result in outcomes if status == 200)
        with pytest.raises(HTTPException) as error:
            rotate_refresh(db, winner.refresh_token, settings)
        assert error.value.status_code == 401


def test_concurrent_password_reset_is_single_use(committed_account, settings):
    factory, user_id, _ = committed_account
    raw = "single-use-recovery-token-" + uuid4().hex
    with factory() as db:
        db.add(AuthChallenge(user_id=user_id, kind="password_reset",
                             token_hash=hash_secret("reset:" + raw, settings),
                             expires_at=utc_now() + timedelta(minutes=10)))
        db.commit()
    barrier = Barrier(2)

    def reset(index):
        with factory() as db:
            barrier.wait(timeout=10)
            try:
                reset_password(db, raw, f"new-password-choice-{index}", settings)
                return 204, index
            except HTTPException as error:
                return error.status_code, index

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reset, index) for index in range(2)]
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(status for status, _ in outcomes) == [204, 400]
    winner = next(index for status, index in outcomes if status == 204)
    with factory() as db:
        assert password_hash.verify(f"new-password-choice-{winner}", db.get(User, user_id).password_hash)


def test_rate_limit_is_atomic_across_connections(postgres_engine, settings):
    action = "concurrent_" + uuid4().hex
    factory = sessionmaker(bind=postgres_engine)
    barrier = Barrier(6)

    def attempt():
        with factory() as db:
            request = Request({"type": "http", "client": ("192.0.2.1", 12345)})
            barrier.wait(timeout=10)
            try:
                rate_limit(db, settings, request, action, "same-account", target_limit=3, ip_limit=100)
                return 200
            except HTTPException as error:
                return error.status_code

    try:
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(attempt) for _ in range(6)]
            assert sorted(future.result(timeout=15) for future in futures) == [200, 200, 200, 429, 429, 429]
    finally:
        with factory() as db:
            keys = [hash_secret(f"rate:{action}:ip:192.0.2.1", settings),
                    hash_secret(f"rate:{action}:target:same-account", settings)]
            db.execute(delete(RateLimitBucket).where(RateLimitBucket.key.in_(keys)))
            db.commit()


def test_migration_upgrade_downgrade_preserves_existing_users_and_expenses(postgres_engine):
    # DDL is transactional in PostgreSQL; rollback restores head after this test.
    config = Config(str(ROOT / "alembic.ini"))
    user_id, expense_id = uuid4(), uuid4()
    with postgres_engine.connect() as connection:
        transaction = connection.begin()
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, "0001_users_expenses")
            connection.execute(text("INSERT INTO users (id, email, password_hash) VALUES (:id, :email, :hash)"),
                               {"id": user_id, "email": "legacy@example.com", "hash": "existing-hash-preserved"})
            connection.execute(text("""INSERT INTO expenses
                (id, owner_id, amount_pence, currency, category, expense_date)
                VALUES (:id, :owner, 1250, 'GBP', 'fuel', '2026-04-06')"""), {"id": expense_id, "owner": user_id})
            command.upgrade(config, "head")
            command.check(config)
            assert connection.scalar(text("SELECT password_hash FROM users WHERE id=:id"), {"id": user_id}) == "existing-hash-preserved"
            assert connection.scalar(text("SELECT amount_pence FROM expenses WHERE id=:id"), {"id": expense_id}) == 1250
            assert connection.scalar(text("SELECT display_name FROM users WHERE id=:id"), {"id": user_id}) is None
            command.downgrade(config, "0001_users_expenses")
            assert connection.scalar(text("SELECT amount_pence FROM expenses WHERE id=:id"), {"id": expense_id}) == 1250
            command.upgrade(config, "head")
        finally:
            transaction.rollback()
