"""Staff boundary tests use the existing disposable PostgreSQL fixtures."""
import base64
import secrets
import time
from datetime import timedelta
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from pydantic import SecretStr
import pytest
from sqlalchemy import select

from app.core.security import password_hash
from app.models import DeviceSession, User
from app.models.books import Business, PrivateFile, Receipt, SupportRecord, Transaction
from app.models.common import utc_now
from app.models.staff import AccountantHandoff, DriverAssignment, StaffAccount, StaffAudit, StaffEntry, StaffTeam
from app.services.books import catalog_id
from app.services.staff import totp
from app.services.vault import encrypt


def mutation(auth):
    return {**auth, "Idempotency-Key": str(uuid4())}


@pytest.fixture
def panel(client, db_session, account):
    settings = client.app.state.settings
    settings.identifier_encryption_keys = [SecretStr(Fernet.generate_key().decode())]
    team = StaffTeam(name="Team one")
    other_team = StaffTeam(name="Team two")
    db_session.add_all([team, other_team])
    db_session.flush()
    members = {}
    for role in ("admin", "senior_accountant", "accountant", "support", "other"):
        seed = base64.b32encode(secrets.token_bytes(20)).decode()
        user = User(email=f"{role}@practice.example", password_hash=password_hash.hash("staff-password-123"))
        db_session.add(user)
        db_session.flush()
        staff = StaffAccount(id=user.id, name=role.title(), role="accountant" if role == "other" else role,
            team_id=other_team.id if role == "other" else team.id, totp_secret=encrypt(settings, seed))
        db_session.add(staff)
        db_session.commit()
        challenge = client.post("/api/v1/staff/auth/login", json={"email": user.email, "password": "staff-password-123"})
        assert challenge.status_code == 200, challenge.text
        result = client.post("/api/v1/staff/auth/verify", json={"challenge_id": challenge.json()["challenge_id"], "code": totp(seed, int(time.time()) // 30)})
        assert result.status_code == 200, result.text
        members[role] = (staff, {"Authorization": "Bearer " + result.json()["access_token"]}, seed)
    driver, driver_auth = account
    owner = UUID(driver["id"])
    db_session.add(DriverAssignment(driver_id=owner, accountant_id=members["accountant"][0].id))
    db_session.commit()
    return members, owner, driver_auth


def test_staff_tokens_are_separate_and_assignments_are_enforced(client, panel):
    members, owner, driver_auth = panel
    for role in ("accountant", "senior_accountant", "admin", "support"):
        response = client.post("/api/v1/staff/drivers/search", headers=members[role][1], json={})
        assert response.status_code == 200, response.text
        assert [row["id"] for row in response.json()["items"]] == [str(owner)]
    assert client.post("/api/v1/staff/drivers/search", headers=members["other"][1], json={}).json()["total"] == 0
    assert client.post(f"/api/v1/staff/drivers/{owner}/overview", headers=members["other"][1], json={"tax_year": "2026-27"}).status_code == 404
    assert client.get("/api/v1/staff/me", headers=driver_auth).status_code == 401
    assert client.get("/api/v1/me", headers=members["admin"][1]).status_code == 401


def test_mfa_replay_revocation_and_server_idle_timeout(client, panel, db_session):
    members, _, _ = panel
    staff, auth, seed = members["accountant"]
    challenge = client.post("/api/v1/staff/auth/login", json={"email": "accountant@practice.example", "password": "staff-password-123"}).json()
    assert client.post("/api/v1/staff/auth/verify", json={"challenge_id": challenge["challenge_id"], "code": totp(seed, int(time.time()) // 30)}).status_code == 401
    device = db_session.scalar(select(DeviceSession).where(DeviceSession.user_id == staff.id))
    device.last_used_at = utc_now() - timedelta(minutes=16)
    db_session.commit()
    assert client.get("/api/v1/staff/me", headers=auth).status_code == 401
    assert client.post("/api/v1/staff/auth/logout", headers=members["support"][1]).status_code == 204
    assert client.get("/api/v1/staff/me", headers=members["support"][1]).status_code == 401


def test_consented_requests_assignment_versions_and_unknown_year(client, panel, db_session):
    members, owner, driver_auth = panel
    client.app.state.settings.accountant_recipients = ["verified-test-practice"]
    response = client.post("/api/v1/accountant-requests", headers=mutation(driver_auth), json={
        "kind": "filing_question", "recipient_reference": "verified-test-practice", "consent_version": "test-v1"})
    assert response.status_code == 201, response.text
    row = client.post("/api/v1/staff/handoffs/search", headers=members["admin"][1], json={"filters": {"tax_year": "2026-27"}}).json()["items"][0]
    assert row["tax_year"] is None
    dashboard = client.post("/api/v1/staff/dashboard", headers=members["accountant"][1], json={"tax_year": "2026-27"}).json()
    assert dashboard["pending_handoffs"] == dashboard["year_not_supplied"] == 1
    assert dashboard["due_soon"] == dashboard["overdue"] == 0
    payload = {"ids": [row["id"]], "accountant_id": str(members["other"][0].id), "versions": {row["id"]: 1}, "reason": "Transfer workload"}
    assert client.post("/api/v1/staff/handoffs/assign", headers=mutation(members["senior_accountant"][1]), json=payload).status_code == 403
    key = mutation(members["admin"][1])
    result = client.post("/api/v1/staff/handoffs/assign", headers=key, json=payload)
    assert result.status_code == 200, result.text
    assert client.post("/api/v1/staff/handoffs/assign", headers=key, json=payload).json() == result.json()
    assert client.post("/api/v1/staff/handoffs/assign", headers=mutation(members["admin"][1]), json=payload).status_code == 409
    assert client.post("/api/v1/staff/drivers/search", headers=members["accountant"][1], json={}).json()["total"] == 0


def test_pre_panel_accountant_idempotency_response_stays_replayable(client, panel, db_session):
    members, owner, driver_auth = panel
    from app.models.books import Idempotency
    from app.services.books import digest
    key = uuid4()
    original_payload = {"kind": "filing_question", "export_id": None, "recipient_reference": "verified-test-practice", "message": None, "consent_version": "test-v1"}
    original_response = {"id": str(uuid4()), "status": "requested", "delivered": False}
    db_session.add(Idempotency(owner_id=owner, request_key=key,
        digest=digest(["POST", "/api/v1/accountant-requests", "", original_payload]), response=original_response))
    db_session.commit()
    response = client.post("/api/v1/accountant-requests", headers={**driver_auth, "Idempotency-Key": str(key)}, json=original_payload)
    assert response.status_code == 201, response.text
    assert response.json() == original_response


def test_support_cannot_edit_reveal_or_export_but_can_note(client, panel, db_session):
    members, owner, _ = panel
    auth = members["support"][1]
    assert client.post(f"/api/v1/staff/drivers/{owner}/identifiers/reveal", headers=auth, json={"tax_year": "2026-27", "field": "utr", "reason": "Review return"}).status_code == 403
    assert client.post("/api/v1/staff/exports", headers=auth, json={"resource": "drivers", "query": {}}).status_code == 403
    assert client.post(f"/api/v1/staff/drivers/{owner}/messages", headers=mutation(auth), json={"body": "Not permitted"}).status_code == 403
    result = client.post(f"/api/v1/staff/drivers/{owner}/notes", headers=mutation(auth), json={"body": "Evidence requested", "kind": "ticket"})
    assert result.status_code == 201, result.text
    assert result.json()["kind"] == "ticket"
    assert db_session.scalar(select(StaffEntry).where(StaffEntry.driver_id == owner)).body == "Evidence requested"


def test_identifiers_reveal_is_audited_without_values_and_search_is_exact(client, panel, db_session):
    members, owner, driver_auth = panel
    result = client.put("/api/v1/me/tax-profile", headers=mutation(driver_auth), json={"tax_year": "2026-27",
        "region": "england_wales_ni", "has_paye_job": False, "employments": [], "utr": "1234567890", "ni_number": "AB123456C"})
    assert result.status_code == 200, result.text
    result = client.post(f"/api/v1/staff/drivers/{owner}/identifiers/reveal", headers=members["accountant"][1], json={
        "tax_year": "2026-27", "field": "utr", "reason": "Verify the client return"})
    assert result.status_code == 200, result.text
    assert result.json()["value"] == "1234567890"
    event = db_session.scalar(select(StaffAudit).where(StaffAudit.action == "identifier_revealed"))
    assert "1234567890" not in str(event.after)
    for search, count in (("1234567890", 1), ("9234567890", 0)):
        result = client.post("/api/v1/staff/drivers/search", headers=members["accountant"][1], json={"search": search})
        assert result.status_code == 200, result.text
        assert result.json()["total"] == count


def test_human_messages_do_not_expose_internal_notes_to_driver(client, panel):
    members, owner, driver_auth = panel
    accountant = mutation(members["accountant"][1])
    assert client.post(f"/api/v1/staff/drivers/{owner}/notes", headers=accountant, json={"body": "Private practice note"}).status_code == 201
    assert client.post(f"/api/v1/staff/drivers/{owner}/messages", headers=mutation(members["accountant"][1]), json={"body": "Please send evidence"}).status_code == 201
    assert client.post("/api/v1/me/accountant-messages", headers=mutation(driver_auth), json={"body": "Evidence attached"}).status_code == 201
    result = client.post("/api/v1/me/accountant-messages/search", headers=driver_auth, json={}).json()
    assert result["total"] == 2
    assert {row["body"] for row in result["items"]} == {"Please send evidence", "Evidence attached"}


def test_financial_correction_reuses_eligibility_and_atomic_staff_audit(client, panel, db_session):
    members, owner, driver_auth = panel
    business = Business(owner_id=owner, kind="self_employment", name="Test taxi")
    db_session.add(business)
    db_session.commit()
    response = client.post("/api/v1/transactions", headers=mutation(driver_auth), json={"kind": "expense", "business_id": str(business.id),
        "amount_pence": 10000, "occurred_on": "2026-10-21", "category_id": str(catalog_id("category", "phone_data"))})
    assert response.status_code == 201, response.text
    row = response.json()
    payload = {"expected_version": row["version"], "category_id": str(catalog_id("category", "fines"))}
    result = client.patch(f"/api/v1/staff/drivers/{owner}/expenses/{row['id']}", headers=mutation(members["accountant"][1]), json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["deductible_pence"] == 0
    assert result.json()["claim_status"] == "excluded"
    event = db_session.scalar(select(StaffAudit).where(StaffAudit.action == "expense_corrected"))
    assert event.before["deductible_pence"] == 10000
    assert event.after["result"]["deductible_pence"] == 0
    assert client.patch(f"/api/v1/staff/drivers/{owner}/expenses/{row['id']}", headers=mutation(members["accountant"][1]), json=payload).status_code == 409


def test_staff_receipt_confirmation_and_exact_correction(client, panel, db_session):
    members, owner, _ = panel
    business = Business(owner_id=owner, kind="self_employment", name="Test taxi")
    file = PrivateFile(owner_id=owner, sha256="c" * 64, mime_type="image/png", content=b"private", size_bytes=7, scan_status="pending")
    db_session.add_all([business, file])
    db_session.flush()
    receipt = Receipt(owner_id=owner, business_id=business.id, file_id=file.id, reviewed={
        "merchant": "Synthetic supplier", "amount_pence": 10000, "occurred_on": "2026-10-21"})
    db_session.add(receipt)
    db_session.commit()
    auth = members["accountant"][1]
    result = client.post(f"/api/v1/staff/drivers/{owner}/receipts/{receipt.id}/review", headers=mutation(auth), json={
        "expected_version": 1, "decision": "approve", "category_id": str(catalog_id("category", "phone_data")), "business_use_percent": "75", "reason": "Evidence reviewed"})
    assert result.status_code == 200, result.text
    assert result.json()["transaction"]["deductible_pence"] == 7500
    row = result.json()["receipt"]
    reversed = client.post(f"/api/v1/staff/drivers/{owner}/receipts/{receipt.id}/reversals", headers=mutation(auth), json={
        "expected_version": row["version"], "mutation_id": result.json()["mutation_id"], "reason": "Correct category"})
    assert reversed.status_code == 200, reversed.text
    assert reversed.json()["transaction"]["review_status"] == "reversed"
    assert client.get(f"/api/v1/staff/drivers/{owner}/documents/{file.id}/content", headers=auth).status_code == 409


def test_table_paging_saved_views_private_csv_and_tax_no_profile(client, panel, db_session):
    members, owner, _ = panel
    auth = members["accountant"][1]
    result = client.post(f"/api/v1/staff/drivers/{owner}/tax", headers=auth, json={"tax_year": "2026-27"})
    assert result.status_code == 200, result.text
    assert result.json()["estimate"]["available"] is False
    assert result.json()["rules"]["rules"]
    result = client.post("/api/v1/staff/views", headers=mutation(auth), json={"resource": "drivers", "name": "My work", "query": {"sort": "email"}})
    assert result.status_code == 201, result.text
    assert client.post("/api/v1/staff/views/search", headers=members["other"][1], json={"resource": "drivers"}).json()["items"] == []
    assert client.delete(f"/api/v1/staff/views/{result.json()['id']}", headers=members["other"][1]).status_code == 404
    assert client.post("/api/v1/staff/drivers/search", headers=auth, json={"sort": "password_hash"}).status_code == 422
    assert client.post("/api/v1/staff/views", headers=mutation(auth), json={"resource": "drivers", "name": "Private search", "query": {"search": "1234567890"}}).status_code == 422
    csv = client.post("/api/v1/staff/exports", headers=auth, json={"resource": "drivers", "query": {}})
    assert csv.status_code == 200, csv.text
    assert "driver@example.com" in csv.text and "password" not in csv.text
    assert csv.headers["cache-control"] == "no-store"


def test_filed_requires_senior_ready_state_and_real_reference(client, panel, db_session):
    members, owner, _ = panel
    request = SupportRecord(owner_id=owner, kind="accountant_request", data={"kind": "filing_question"})
    db_session.add(request); db_session.flush()
    handoff = AccountantHandoff(id=request.id, driver_id=owner, tax_year="2026-27")
    db_session.add(handoff); db_session.commit()
    path = f"/api/v1/staff/handoffs/{handoff.id}"
    payload = {"expected_version": 1, "status": "filed", "reason": "External filing", "filing_reference": "synthetic-reference"}
    assert client.patch(path, headers=mutation(members["accountant"][1]), json=payload).status_code == 403
    assert client.patch(path, headers=mutation(members["senior_accountant"][1]), json=payload).status_code == 422
    ready = client.patch(path, headers=mutation(members["accountant"][1]), json={"expected_version": 1, "status": "ready_to_file", "reason": "Reviewed all supplied evidence"})
    assert ready.status_code == 200, ready.text
    filed = client.patch(path, headers=mutation(members["senior_accountant"][1]), json={**payload, "expected_version": 2})
    assert filed.status_code == 200, filed.text
    assert filed.json()["filing_reference"] == "synthetic-reference"


def test_unknown_date_receipt_review_and_full_legacy_activity(client, panel, db_session):
    members, owner, driver_auth = panel
    business = Business(owner_id=owner, kind="self_employment", name="Synthetic business")
    file = PrivateFile(owner_id=owner, sha256="d" * 64, mime_type="image/png", content=b"private", size_bytes=7)
    db_session.add_all([business, file]); db_session.flush()
    receipt = Receipt(owner_id=owner, business_id=business.id, file_id=file.id)
    db_session.add(receipt); db_session.commit()
    auth = members["accountant"][1]
    result = client.post(f"/api/v1/staff/drivers/{owner}/receipts/search", headers=auth, json={"filters": {"tax_year": "2026-27"}})
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1
    updated = client.patch(f"/api/v1/staff/drivers/{owner}/receipts/{receipt.id}", headers=mutation(auth), json={
        "expected_version": 1, "merchant": "Reviewed supplier", "amount_pence": 12345, "occurred_on": "2026-10-21"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["amount_pence"] == 12345
    tx = db_session.scalar(select(Transaction).where(Transaction.receipt_id == receipt.id))
    assert tx.review_status == "draft"
    result = client.post(f"/api/v1/staff/drivers/{owner}/activity/search", headers=auth, json={})
    assert result.status_code == 200, result.text
    actions = {row["action"] for row in result.json()["items"]}
    assert {"receipt_fields_corrected", "review"} <= actions


def test_document_scan_job_quarantine_and_bounded_retry(client, panel, db_session):
    members, owner, _ = panel
    file = PrivateFile(owner_id=owner, sha256="f" * 64, mime_type="image/png", content=b"private", size_bytes=7)
    db_session.add(file); db_session.flush()
    from app.models.books import Job
    job = Job(owner_id=owner, kind="private_scan", resource_id=file.id, status="failed", attempts=5, retryable=True)
    db_session.add(job); db_session.commit()
    path = f"/api/v1/staff/drivers/{owner}/documents/{file.id}/scan-retries"
    auth = members["accountant"][1]
    assert client.post(path, headers=mutation(auth)).status_code == 409
    job.attempts = 1; db_session.commit()
    result = client.post(path, headers=mutation(auth))
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "queued"


def test_server_paging_sort_filter_and_full_csv_not_just_page(client, panel, db_session):
    members, _, _ = panel
    for index in range(4):
        db_session.add(User(email=f"paged-{index}@example.invalid", display_name="=1+2" if index == 0 else f"Paged {index}", password_hash="unusable-test-hash"))
    db_session.commit()
    auth = members["admin"][1]
    page1 = client.post("/api/v1/staff/drivers/search", headers=auth, json={"page": 1, "page_size": 2, "sort": "email", "order": "asc"}).json()
    page2 = client.post("/api/v1/staff/drivers/search", headers=auth, json={"page": 2, "page_size": 2, "sort": "email", "order": "asc"}).json()
    assert page1["total"] == page2["total"] == 5
    assert not ({row["id"] for row in page1["items"]} & {row["id"] for row in page2["items"]})
    csv = client.post("/api/v1/staff/exports", headers=auth, json={"resource": "drivers", "query": {"page_size": 1}})
    assert csv.status_code == 200, csv.text
    assert all(f"paged-{index}@example.invalid" in csv.text for index in range(4))
    assert "'=1+2" in csv.text
