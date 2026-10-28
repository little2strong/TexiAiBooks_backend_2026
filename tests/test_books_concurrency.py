from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.main import create_app
from app.models import DeviceSession, RefreshCredential, User
from app.models.books import Business, Transaction
from app.schemas.user import UserCreate
from app.services.auth import register_user
from app.services.books import primary_business
from app.services.sessions import new_session
from tests.test_books import headers, tx_data

pytestmark=pytest.mark.postgres


@pytest.fixture
def committed_books(postgres_engine,settings):
    factory=sessionmaker(bind=postgres_engine,expire_on_commit=False)
    with factory() as db:
        user=register_user(db,UserCreate(email=f'books-race-{uuid4().hex}@example.com',password='safe-password-123'))
        business=primary_business(db,user.id)
        db.commit()
        tokens=new_session(db,user,settings)
        owner,business_id=user.id,business.id
    try:
        yield factory,owner,str(business_id),{'Authorization':'Bearer '+tokens.access_token}
    finally:
        # Only this account in the fixture-owned disposable PostgreSQL container.
        with factory() as db:
            session_ids=list(db.scalars(select(DeviceSession.id).where(DeviceSession.user_id==owner)))
            db.execute(delete(RefreshCredential).where(RefreshCredential.session_id.in_(session_ids)))
            for table in reversed(Base.metadata.sorted_tables):
                if 'owner_id' in table.c: db.execute(delete(table).where(table.c.owner_id==owner))
                elif 'user_id' in table.c: db.execute(delete(table).where(table.c.user_id==owner))
            db.execute(delete(User).where(User.id==owner))
            db.commit()


def test_concurrent_same_key_posts_only_once_and_stale_edits_conflict(committed_books,settings):
    factory,owner,business,auth=committed_books
    barrier=Barrier(2)
    key=uuid4()
    def post():
        with TestClient(create_app(settings,factory)) as client:
            barrier.wait(timeout=10)
            result=client.post('/api/v1/transactions',headers=headers(auth,key),json=tx_data(business))
            assert result.status_code==201,result.text
            return result.json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(post) for _ in range(2)]
        outcomes=[future.result(timeout=15) for future in futures]
    assert outcomes[0]==outcomes[1]
    id=outcomes[0]['id']
    with factory() as db:
        assert len(list(db.scalars(select(Transaction).where(Transaction.owner_id==owner))))==1
    barrier=Barrier(2)
    def correct(amount):
        with TestClient(create_app(settings,factory)) as client:
            barrier.wait(timeout=10)
            return client.patch('/api/v1/transactions/'+id,headers=headers(auth),json={'expected_version':1,'amount_pence':amount}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(correct,amount) for amount in (27000,28000)]
        outcomes=[future.result(timeout=15) for future in futures]
    assert sorted(outcomes)==[200,409]
