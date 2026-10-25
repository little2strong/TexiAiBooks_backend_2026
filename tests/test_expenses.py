from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.models import Expense

pytestmark = pytest.mark.postgres


def test_expense_lifecycle(client, account, expense_data, db_session):
    user, headers = account
    created = client.post("/api/v1/expenses", headers=headers, json=expense_data)
    assert created.status_code == 201
    expense = created.json()
    assert expense["owner_id"] == user["id"]
    assert expense["amount_pence"] == 1250
    assert expense["currency"] == "GBP"
    assert datetime.fromisoformat(expense["created_at"]).tzinfo is not None
    path = f"/api/v1/expenses/{expense['id']}"
    assert client.get(path, headers=headers).json() == expense
    assert client.get("/api/v1/expenses", headers=headers).json()["items"] == [expense]
    updated = client.patch(path, headers=headers, json={"amount_pence": 1800, "note": None})
    assert updated.status_code == 200
    assert updated.json()["amount_pence"] == 1800
    assert updated.json()["note"] is None
    assert updated.json()["category"] == "fuel"
    assert updated.json()["updated_at"] > expense["updated_at"]
    deleted = client.delete(path, headers=headers)
    assert deleted.status_code == 204 and not deleted.content
    assert client.get(path, headers=headers).status_code == 404
    assert client.patch(path, headers=headers, json={"note": "again"}).status_code == 404
    assert client.delete(path, headers=headers).status_code == 404
    assert client.get("/api/v1/expenses", headers=headers).json()["items"] == []
    stored = db_session.get(Expense, UUID(expense["id"]))
    assert stored is not None and stored.deleted_at.tzinfo is not None


@pytest.mark.parametrize("amount", [0, -1, 1.5, "100", True, 2_147_483_648, None])
def test_invalid_amounts(client, account, expense_data, amount):
    _, headers = account
    assert client.post("/api/v1/expenses", headers=headers, json=expense_data | {"amount_pence": amount}).status_code == 422


@pytest.mark.parametrize("patch", [
    {}, {"amount_pence": 0}, {"amount_pence": -100}, {"amount_pence": 0.5},
    {"amount_pence": "100"}, {"amount_pence": True}, {"amount_pence": None},
    {"category": None}, {"category": "unknown"}, {"currency": None}, {"currency": "USD"},
    {"expense_date": None}, {"expense_date": "bad-date"}, {"note": "a" * 2001}, {"note": 123},
])
def test_invalid_patches(client, account, expense_data, patch):
    _, headers = account
    expense = client.post("/api/v1/expenses", headers=headers, json=expense_data).json()
    response = client.patch(f"/api/v1/expenses/{expense['id']}", headers=headers, json=patch)
    assert response.status_code == 422


@pytest.mark.parametrize("changes", [{"currency": "USD"}, {"category": "unknown"}, {"expense_date": "bad-date"}, {"note": "a" * 2001}, {"note": 123}])
def test_invalid_create_fields(client, account, expense_data, changes):
    _, headers = account
    assert client.post("/api/v1/expenses", headers=headers, json=expense_data | changes).status_code == 422


def test_ownership_and_forged_owner(client, account, expense_data):
    alice, alice_headers = account
    bob = client.post("/api/v1/auth/register", json={"email": "bob@example.com", "password": "safe-password-456"}).json()
    login = client.post("/api/v1/auth/login", data={"username": "bob@example.com", "password": "safe-password-456"}).json()
    bob_headers = {"Authorization": f"Bearer {login['access_token']}"}
    expense = client.post("/api/v1/expenses", headers=bob_headers, json=expense_data).json()
    path = f"/api/v1/expenses/{expense['id']}"
    assert client.get(path, headers=alice_headers).status_code == 404
    assert client.patch(path, headers=alice_headers, json={"amount_pence": 1}).status_code == 404
    assert client.delete(path, headers=alice_headers).status_code == 404
    assert client.get("/api/v1/expenses", headers=alice_headers).json()["items"] == []
    forged = client.post("/api/v1/expenses", headers=alice_headers, json=expense_data | {"owner_id": bob["id"]})
    assert forged.status_code == 422
    assert client.patch(path, headers=bob_headers, json={"owner_id": alice["id"]}).status_code == 422
    assert client.get(path, headers=bob_headers).json() == expense


def test_pagination_is_bounded_and_deterministic(client, account, expense_data):
    _, headers = account
    records = []
    for date in ("2026-10-20", "2026-10-22", "2026-10-22", "2026-10-21"):
        response = client.post("/api/v1/expenses", headers=headers, json=expense_data | {"expense_date": date})
        assert response.status_code == 201
        records.append(response.json())
    expected = sorted(records, key=lambda item: (item["expense_date"], item["created_at"], item["id"]), reverse=True)
    first = client.get("/api/v1/expenses?limit=2&offset=0", headers=headers).json()
    second = client.get("/api/v1/expenses?limit=2&offset=2", headers=headers).json()
    assert first == {"items": expected[:2], "limit": 2, "offset": 0}
    assert second["items"] == expected[2:]
    assert client.get("/api/v1/expenses?limit=2&offset=0", headers=headers).json() == first
    assert client.get("/api/v1/expenses?offset=99", headers=headers).json()["items"] == []
    for query in ("limit=0", "limit=101", "offset=-1", "offset=100001"):
        assert client.get(f"/api/v1/expenses?{query}", headers=headers).status_code == 422


def test_missing_expense_returns_404(client, account):
    _, headers = account
    path = f"/api/v1/expenses/{uuid4()}"
    assert client.get(path, headers=headers).status_code == 404
    assert client.patch(path, headers=headers, json={"note": "missing"}).status_code == 404
    assert client.delete(path, headers=headers).status_code == 404


def test_expenses_require_authentication(client, expense_data):
    path = f"/api/v1/expenses/{uuid4()}"
    assert client.post("/api/v1/expenses", json=expense_data).status_code == 401
    assert client.get("/api/v1/expenses").status_code == 401
    assert client.get(path).status_code == 401
    assert client.patch(path, json={"note": "hello"}).status_code == 401
    assert client.delete(path).status_code == 401


def test_real_database_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
