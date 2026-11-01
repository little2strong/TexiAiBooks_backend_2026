"""Tax return workspace, admin screens and driver tools, on disposable PostgreSQL."""
from decimal import Decimal
from uuid import UUID

import pytest

from app.models import User
from app.models.books import Mutation, Receipt, Business, PrivateFile, SupportRecord, Transaction
from app.models.common import utc_now
from app.models.staff import AccountantHandoff, DriverAssignment, StaffAudit, TaxRate
from app.services.books import catalog_id
from tests.test_staff_panel import mutation, panel  # noqa: F401
from tests.test_books import headers

YEAR = "2025-26"
SPEC_URL = "https://www.gov.uk/government/publications/rates-and-allowances-income-tax"


@pytest.fixture
def driver_books(client, panel):  # noqa: F811
    members, owner, auth = panel
    response = client.put("/api/v1/me/driver-profile", headers=headers(auth), json={"licence_type": "private_hire", "council_code": "manual", "work_pattern": "full_time"})
    assert response.status_code == 200, response.text
    business = response.json()["primary_business_id"]
    response = client.put("/api/v1/me/tax-profile", headers=headers(auth), json={"tax_year": YEAR, "region": "england_wales_ni", "has_paye_job": False, "employments": []})
    assert response.status_code == 200, response.text
    return members, owner, auth, business


def income(client, auth, business, pence=3000000, on="2025-10-20"):
    response = client.post("/api/v1/transactions", headers=headers(auth), json={"kind": "income", "amount_pence": pence, "occurred_on": on,
        "business_id": business, "source_id": str(catalog_id("source", "uber"))})
    assert response.status_code == 201, response.text
    return response.json()


def open_return(client, members, owner, role="accountant", year=YEAR):
    response = client.post("/api/v1/staff/returns", headers=mutation(members[role][1]), json={"driver_id": str(owner), "tax_year": year})
    assert response.status_code == 201, response.text
    return client.get("/api/v1/staff/returns/" + response.json()["id"], headers=members[role][1]).json()


def post_return(client, members, row, action, role="accountant", **body):
    return client.post(f"/api/v1/staff/returns/{row['id']}/{action}", headers=mutation(members[role][1]), json={"expected_version": row["version"], **body})


def signed_off(client, members, auth, row):
    sent = post_return(client, members, row, "request-approval", reason="Review complete")
    assert sent.status_code == 200, sent.text
    current = sent.json()
    decided = client.post(f"/api/v1/me/tax-returns/{row['id']}/decision", headers=headers(auth), json={
        "expected_version": current["version"], "review_version": current["review_version"], "decision": "approve"})
    assert decided.status_code == 200, decided.text
    return decided.json()


def test_adjustment_changes_estimate_but_never_the_driver_record(client, db_session, driver_books):
    members, owner, auth, business = driver_books
    posted = income(client, auth, business)
    row = open_return(client, members, owner)
    assert row["estimate"]["profit_pence"] == 3000000
    added = post_return(client, members, row, "adjustments", target="capital_allowances", amount_pence=200000, reason="Main pool allowance on Prius")
    assert added.status_code == 201, added.text
    adjusted = added.json()
    assert adjusted["estimate"]["profit_pence"] == 2800000
    assert adjusted["estimate"]["adjustment_capital_allowances_pence"] == 200000
    assert client.get("/api/v1/transactions/" + posted["id"], headers=auth).json()["amount_pence"] == 3000000
    # The driver's own estimate agrees, because one engine serves every screen.
    assert client.get(f"/api/v1/tax/estimate?tax_year={YEAR}", headers=auth).json()["profit_pence"] == 2800000
    voided = post_return(client, members, adjusted, f"adjustments/{adjusted['adjustments'][0]['id']}/void", reason="Claimed by mistake")
    assert voided.status_code == 200, voided.text
    assert voided.json()["estimate"]["profit_pence"] == 3000000
    assert voided.json()["adjustments"][0]["voided_at"]
    assert post_return(client, members, voided.json(), "adjustments", target="income", amount_pence=0, reason="Nothing").status_code == 422
    assert post_return(client, members, voided.json(), "adjustments", target="capital_allowances", amount_pence=-5, reason="Wrong sign").status_code == 422


def test_support_and_outside_staff_cannot_touch_returns(client, driver_books):
    members, owner, _, _ = driver_books
    assert client.post("/api/v1/staff/returns", headers=mutation(members["support"][1]), json={"driver_id": str(owner), "tax_year": YEAR}).status_code == 403
    assert client.post("/api/v1/staff/returns", headers=mutation(members["other"][1]), json={"driver_id": str(owner), "tax_year": YEAR}).status_code == 404
    row = open_return(client, members, owner)
    assert client.get("/api/v1/staff/returns/" + row["id"], headers=members["other"][1]).status_code == 404
    assert client.get("/api/v1/staff/returns/" + row["id"], headers=members["support"][1]).status_code == 200
    assert post_return(client, members, row, "adjustments", role="support", target="income", amount_pence=5, reason="Not allowed").status_code == 403
    assert client.post("/api/v1/staff/returns/search", headers=members["other"][1], json={}).json()["total"] == 0


def test_open_items_block_signoff_and_current_year_is_blocked(client, db_session, driver_books):
    members, owner, auth, business = driver_books
    income(client, auth, business)
    file = PrivateFile(owner_id=owner, sha256="a" * 64, mime_type="image/png", content=b"x", size_bytes=1, scan_status="clean")
    db_session.add(file); db_session.flush()
    db_session.add(Receipt(owner_id=owner, file_id=file.id, business_id=UUID(business), processing_status="review_required"))
    db_session.commit()
    row = open_return(client, members, owner)
    assert row["blockers"] == 1
    assert next(item for item in row["checklist"] if item["id"] == "receipts")["status"] == "block"
    blocked = post_return(client, members, row, "request-approval", reason="Trying early")
    assert blocked.status_code == 409 and "Receipts reviewed" in blocked.json()["detail"]
    assert client.put("/api/v1/me/tax-profile", headers=headers(auth), json={"tax_year": "2026-27", "region": "england_wales_ni", "has_paye_job": False, "employments": []}).status_code == 200
    current = open_return(client, members, owner, year="2026-27")
    assert next(item for item in current["checklist"] if item["id"] == "year_ended")["status"] == "block"


def test_full_flow_signoff_filing_freeze_and_reopen(client, db_session, driver_books):
    members, owner, auth, business = driver_books
    income(client, auth, business)
    request = SupportRecord(owner_id=owner, kind="accountant_request", data={"kind": "filing_question"})
    db_session.add(request); db_session.flush()
    db_session.add(AccountantHandoff(id=request.id, driver_id=owner, tax_year=YEAR)); db_session.commit()
    row = open_return(client, members, owner)
    # No filing without the driver's sign-off.
    assert post_return(client, members, row, "file", role="senior_accountant", filing_reference="HMRC-123", reason="Filed").status_code == 409
    approved = signed_off(client, members, auth, row)
    assert approved["status"] == "driver_approved"
    current = client.get("/api/v1/staff/returns/" + row["id"], headers=members["senior_accountant"][1]).json()
    assert post_return(client, members, current, "file", filing_reference="HMRC-123", reason="Filed").status_code == 403
    filed = post_return(client, members, current, "file", role="senior_accountant", filing_reference="HMRC-123", reason="Filed online")
    assert filed.status_code == 200, filed.text
    filed = filed.json()
    assert filed["status"] == "filed" and filed["filed_by_name"]
    assert client.get(f"/api/v1/staff/handoffs", headers=members["admin"][1]).status_code in {404, 405}
    overview = client.post(f"/api/v1/staff/drivers/{owner}/overview", headers=members["admin"][1], json={"tax_year": YEAR}).json()
    assert overview["handoffs"][0]["status"] == "filed" and overview["handoffs"][0]["filing_reference"] == "HMRC-123"
    # The year is locked for new records.
    locked = client.post("/api/v1/transactions", headers=headers(auth), json={"kind": "income", "amount_pence": 100, "occurred_on": "2025-11-01",
        "business_id": business, "source_id": str(catalog_id("source", "uber"))})
    assert locked.status_code == 409
    frozen_tax = client.get(f"/api/v1/tax/estimate?tax_year={YEAR}", headers=auth).json()
    assert frozen_tax["frozen"] is True

    # A rate change entered as data alters open work but not the filed year.
    for year, expected_changes in ((YEAR, False),):
        draft = client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={"tax_year": year, "region": "england_wales_ni", "code": "class4",
            "value": {"lower_pence": 1257000, "upper_pence": 5027000, "rates": ["0.10", "0.02"], "class2_compulsory_pence": 0,
                "class2_small_profits_threshold_pence": 684500, "class2_weekly_rate_pence": 350}, "official_url": SPEC_URL, "reason": "Rate change test"})
        assert draft.status_code == 201, draft.text
        rate = draft.json()
        # Draft and approved rows do not apply; activation has to come in order.
        assert client.post(f"/api/v1/staff/rates/{rate['id']}/activate", headers=mutation(members["admin"][1]), json={"expected_version": 1, "reason": "Too early"}).status_code == 409
        approved_rate = client.post(f"/api/v1/staff/rates/{rate['id']}/approve", headers=mutation(members["admin"][1]), json={"expected_version": 1, "reason": "Checked against HMRC"})
        assert approved_rate.status_code == 200, approved_rate.text
        active = client.post(f"/api/v1/staff/rates/{rate['id']}/activate", headers=mutation(members["admin"][1]), json={"expected_version": 2, "reason": "Go live"})
        assert active.status_code == 200, active.text
    assert client.get(f"/api/v1/tax/estimate?tax_year={YEAR}", headers=auth).json()["class4_pence"] == frozen_tax["class4_pence"]

    # Reopening needs seniority, keeps the old snapshot, then the new rate applies.
    current = client.get("/api/v1/staff/returns/" + row["id"], headers=members["senior_accountant"][1]).json()
    assert post_return(client, members, current, "reopen", reason="Amendment").status_code == 403
    reopened = post_return(client, members, current, "reopen", role="senior_accountant", reason="HMRC amendment")
    assert reopened.status_code == 200, reopened.text
    reopened = reopened.json()
    assert reopened["status"] == "in_preparation" and reopened["earlier_snapshots"][0]["filing_reference"] == "HMRC-123"
    new_tax = client.get(f"/api/v1/tax/estimate?tax_year={YEAR}", headers=auth).json()
    assert new_tax["frozen"] is False
    assert new_tax["class4_pence"] == round((3000000 - 1257000) * 0.10)


def test_books_changed_after_signoff_require_a_new_version(client, driver_books):
    members, owner, auth, business = driver_books
    income(client, auth, business)
    row = open_return(client, members, owner)
    signed_off(client, members, auth, row)
    income(client, auth, business, pence=5000, on="2025-11-01")
    current = client.get("/api/v1/staff/returns/" + row["id"], headers=members["senior_accountant"][1]).json()
    stale = post_return(client, members, current, "file", role="senior_accountant", filing_reference="HMRC-9", reason="Filed")
    assert stale.status_code == 409 and "changed" in stale.json()["detail"]


def test_driver_can_request_changes_and_only_on_the_current_version(client, driver_books):
    members, owner, auth, business = driver_books
    income(client, auth, business)
    row = open_return(client, members, owner)
    sent = post_return(client, members, row, "request-approval", reason="Review complete").json()
    decision = {"expected_version": sent["version"], "review_version": sent["review_version"], "decision": "request_changes"}
    assert client.post(f"/api/v1/me/tax-returns/{row['id']}/decision", headers=headers(auth), json=decision).status_code == 422
    changed = client.post(f"/api/v1/me/tax-returns/{row['id']}/decision", headers=headers(auth), json={**decision, "note": "Uber figure looks wrong"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["status"] == "in_preparation"
    assert client.post(f"/api/v1/me/tax-returns/{row['id']}/decision", headers=headers(auth), json={**decision, "expected_version": changed.json()["version"], "note": "Again"}).status_code == 409
    thread = client.post(f"/api/v1/staff/drivers/{owner}/messages/search", headers=members["accountant"][1], json={}).json()
    assert "Uber figure looks wrong" in thread["items"][0]["body"]
    other = client.post("/api/v1/auth/register", json={"email": "second@example.com", "password": "safe-password-123"})
    login = client.post("/api/v1/auth/login", data={"username": "second@example.com", "password": "safe-password-123"}).json()
    assert client.get("/api/v1/me/tax-returns", headers={"Authorization": "Bearer " + login["access_token"]}).json()["items"] == []
    assert client.post(f"/api/v1/me/tax-returns/{row['id']}/decision", headers=headers({"Authorization": "Bearer " + login["access_token"]}), json={**decision, "note": "Mine"}).status_code == 404


def test_rate_validation_and_admin_only(client, driver_books):
    members, *_ = driver_books
    base = {"tax_year": "2027-28", "region": "england_wales_ni", "code": "class4", "official_url": SPEC_URL, "reason": "Next year"}
    assert client.post("/api/v1/staff/rates", headers=mutation(members["senior_accountant"][1]), json={**base, "value": {}}).status_code == 403
    assert client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={**base, "value": {"lower_pence": 1}}).status_code == 422
    assert client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={**base, "code": "nonsense", "value": {}}).status_code == 422
    assert client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={**base, "code": "vat", "value": {"threshold_pence": 1}}).status_code == 422
    # A value that would crash every estimate in the year is refused at draft time.
    bad_class4 = {"lower_pence": 1257000, "upper_pence": 5027000, "rates": ["6%", "2%"], "class2_compulsory_pence": 0,
        "class2_small_profits_threshold_pence": 710500, "class2_weekly_rate_pence": 365}
    refused = client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={**base, "value": bad_class4})
    assert refused.status_code == 422 and "calculated" in refused.json()["detail"]
    bad_mileage = {"first_band_miles": "ten thousand", "first_rate_pence": 55, "remaining_rate_pence": 25, "motorcycle_rate_pence": 24, "band_scope": "person"}
    assert client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={**base, "code": "mileage", "value": bad_mileage}).status_code == 422
    assert client.post("/api/v1/staff/rates/search", headers=members["accountant"][1], json={}).status_code == 403
    assert client.post("/api/v1/staff/rates/effective", headers=members["admin"][1], json={"tax_year": "2027-28"}).json()["unavailable_reason"]
    # A partly configured year stays unavailable to drivers and to the panel's year picker.
    assert "2027-28" not in client.get("/api/v1/staff/config", headers=members["admin"][1]).json()["tax_years"]


def test_mtd_threshold_edit_changes_driver_status_with_audit(client, db_session, driver_books):
    members, owner, auth, _ = driver_books
    assert client.get("/api/v1/mtd/status", headers=auth).json()["status"] == "unknown"
    put = client.put("/api/v1/tax-history/2025-26", headers=headers(auth), json={"gross_se_income_pence": 3500000, "paye_income_pence": 2000000, "source": "filed", "return_filed": "yes"})
    assert put.status_code == 200, put.text
    assert put.json()["mtd"]["status"] == "upcoming"
    assert put.json()["mtd"]["qualifying_income_pence"] == 3500000
    for action, version in (("approve", 1), ("activate", 2)):
        if action == "approve":
            created = client.post("/api/v1/staff/rates", headers=mutation(members["admin"][1]), json={"tax_year": "2025-26", "region": "uk", "code": "mtd_threshold",
                "value": {"threshold_pence": 4000000, "mandation_tax_year": "2027-28"}, "official_url": SPEC_URL, "reason": "Government raised threshold"})
            assert created.status_code == 201, created.text
        result = client.post(f"/api/v1/staff/rates/{created.json()['id']}/{action}", headers=mutation(members["admin"][1]), json={"expected_version": version, "reason": "Checked"})
        assert result.status_code == 200, result.text
    assert client.get("/api/v1/mtd/status", headers=auth).json()["status"] == "not_required"
    changes = db_session.query(Mutation).filter(Mutation.owner_id == owner, Mutation.action == "mtd_status_change").all()
    assert len(changes) >= 3 and all(item.reason for item in changes)
    # Prompt when takings look like profit.
    prompted = client.put("/api/v1/tax-history/2024-25", headers=headers(auth), json={"gross_se_income_pence": 1000000, "profit_pence": 1000000})
    assert prompted.json()["prompts"] == ["confirm_takings_before_costs"]
    assert client.post(f"/api/v1/staff/drivers/{owner}/mtd/override", headers=mutation(members["accountant"][1]), json={"exempt": True, "reason": "Digitally excluded"}).status_code == 403
    override = client.post(f"/api/v1/staff/drivers/{owner}/mtd/override", headers=mutation(members["senior_accountant"][1]), json={"exempt": True, "reason": "Digitally excluded"})
    assert override.json()["status"] == "exempt"
    view = client.post(f"/api/v1/staff/drivers/{owner}/mtd", headers=members["accountant"][1])
    assert view.status_code == 200 and view.json()["status"] == "exempt" and len(view.json()["history"]) == 2


def test_mileage_band_is_per_person_across_vehicles(client, driver_books):
    members, owner, auth, business = driver_books
    logs = []
    for registration, miles in (("AA11AAA", "6000.00"), ("BB22BBB", "5000.00")):
        created = client.post("/api/v1/vehicles", headers=headers(auth), json={"registration": registration, "ownership": "owned", "licence_class": "private_hire", "business_start_on": "2025-04-06"})
        assert created.status_code == 201, created.text
        row = created.json()
        elected = client.post(f"/api/v1/vehicles/{row['id']}/claim-method", headers=headers(auth), json={"expected_version": row["version"], "method": "mileage", "effective_from": "2025-04-06",
            "prior_capital_allowances": False, "prior_vehicle_expense_claim": False, "acknowledgement_version": "hmrc-2026-10-27"})
        assert elected.status_code == 200, elected.text
        posted = client.post("/api/v1/mileage-logs", headers=headers(auth), json={"business_id": business, "vehicle_id": row["id"], "occurred_on": "2025-05-01", "business_miles": miles, "private_miles": "0.00", "purpose": "Fares"})
        assert posted.status_code == 201, posted.text
    summary = client.get(f"/api/v1/mileage-logs?tax_year={YEAR}", headers=auth).json()["summary"]
    # Spec case: 11,000 miles across two vehicles in a 45p year is 10,000 x 45p + 1,000 x 25p.
    assert summary["deduction_pence"] == 475000
    assert summary["threshold_remaining"] == "0.00"


def test_vehicle_disposal_ends_method_lock_and_blocks_later_mileage(client, driver_books):
    members, owner, auth, business = driver_books
    row = client.post("/api/v1/vehicles", headers=headers(auth), json={"registration": "CC33CCC", "ownership": "owned", "licence_class": "private_hire", "business_start_on": "2025-04-06"}).json()
    elected = client.post(f"/api/v1/vehicles/{row['id']}/claim-method", headers=headers(auth), json={"expected_version": row["version"], "method": "mileage", "effective_from": "2025-04-06",
        "prior_capital_allowances": False, "prior_vehicle_expense_claim": False, "acknowledgement_version": "hmrc-2026-10-27"}).json()
    # Proceeds only belong on actual-cost vehicles.
    assert client.post(f"/api/v1/vehicles/{row['id']}/disposal", headers=headers(auth), json={"expected_version": elected["version"], "disposed_on": "2025-09-01", "disposal_reason": "sold", "proceeds_pence": 100}).status_code == 422
    sold = client.post(f"/api/v1/vehicles/{row['id']}/disposal", headers=headers(auth), json={"expected_version": elected["version"], "disposed_on": "2025-09-01", "disposal_reason": "sold"})
    assert sold.status_code == 200, sold.text
    assert sold.json()["active"] is False
    trip = {"business_id": business, "vehicle_id": row["id"], "business_miles": "10.00", "private_miles": "0.00", "purpose": "Fares"}
    assert client.post("/api/v1/mileage-logs", headers=headers(auth), json={**trip, "occurred_on": "2025-09-02"}).status_code == 422
    assert client.post("/api/v1/mileage-logs", headers=headers(auth), json={**trip, "occurred_on": "2025-08-02"}).status_code == 201


def test_documents_status_scope_and_home_summary(client, driver_books):
    members, owner, auth, _ = driver_books
    from datetime import timedelta
    from app.services.tax import today
    for doc_type, delta in (("mot", -1), ("insurance", 10), ("phv_licence", 300)):
        response = client.post("/api/v1/me/documents", headers=headers(auth), json={"doc_type": doc_type, "expires_on": str(today() + timedelta(days=delta))})
        assert response.status_code == 201, response.text
    states = {row["doc_type"]: row["expiry_status"] for row in client.get("/api/v1/me/documents", headers=auth).json()["items"]}
    assert states == {"mot": "expired", "insurance": "expiring_soon", "phv_licence": "valid"}
    summary = client.get("/api/v1/home/summary", headers=auth)
    assert summary.status_code == 200, summary.text
    assert [row["doc_type"] for row in summary.json()["expiring_documents"]] == ["mot", "insurance"]
    assert summary.json()["mtd"]["status"] == "unknown"
    assert summary.json()["vat"]["status"] == "below"
    staff_view = client.post(f"/api/v1/staff/drivers/{owner}/compliance/search", headers=members["accountant"][1], json={"sort": "expires_on"})
    assert staff_view.status_code == 200, staff_view.text
    assert staff_view.json()["total"] == 3
    assert client.post(f"/api/v1/staff/drivers/{owner}/compliance/search", headers=members["other"][1], json={"sort": "expires_on"}).status_code == 404


def test_platform_report_dispute_keeps_books_untouched(client, driver_books):
    members, owner, auth, business = driver_books
    income(client, auth, business, pence=100000)
    uber = str(catalog_id("source", "uber"))
    report = {"tax_year": YEAR, "source_id": uber, "reported_gross_pence": 120000}
    response = client.put("/api/v1/tax/platform-reports", headers=headers(auth), json=report)
    assert response.status_code == 200, response.text
    row = next(item for item in response.json()["items"] if item["source"] == "Uber")
    assert (row["status"], row["difference_pence"]) == ("mismatch", 20000)
    disputed = client.put("/api/v1/tax/platform-reports", headers=headers(auth), json={**report, "dispute_note": "Refunded trips were included"}).json()
    assert next(item for item in disputed["items"] if item["source"] == "Uber")["status"] == "disputed"
    assert client.get(f"/api/v1/dashboard?tax_year={YEAR}", headers=auth).json()["income_pence"] == 100000
    workspace = open_return(client, members, owner)
    assert next(item for item in workspace["checklist"] if item["id"] == "platform")["status"] == "warn"
    assert client.put("/api/v1/tax/platform-reports", headers=headers(auth), json={**report, "source_id": str(catalog_id("source", "cash"))}).status_code == 422


def test_vat_monitor_warns_near_threshold(client, driver_books):
    members, owner, auth, business = driver_books
    from app.services.tax import today
    income(client, auth, business, pence=7500000, on=str(today()))
    client.put("/api/v1/me/tax-profile", headers=headers(auth), json={"tax_year": "2026-27", "region": "england_wales_ni", "has_paye_job": False, "employments": []})
    result = client.get("/api/v1/tax/vat-monitor", headers=auth).json()
    assert result["status"] == "approaching" and result["threshold_pence"] == 9000000


def test_revoking_access_ends_it_at_once_and_blocks_reassignment(client, db_session, driver_books):
    members, owner, auth, _ = driver_books
    request = SupportRecord(owner_id=owner, kind="accountant_request", data={"kind": "filing_question"}, created_at=utc_now())
    db_session.add(request); db_session.flush()
    handoff = AccountantHandoff(id=request.id, driver_id=owner, tax_year=YEAR)
    db_session.add(handoff); db_session.commit()
    assert client.get("/api/v1/me/accountant-access", headers=auth).json()["has_accountant"] is True
    assert client.post(f"/api/v1/staff/drivers/{owner}/overview", headers=members["accountant"][1], json={"tax_year": YEAR}).status_code == 200
    assert client.get("/api/v1/me/access-log", headers=auth).json()["items"][0]["who"] == "Accountant"
    assert client.post("/api/v1/me/accountant-access/revocation", headers=headers(auth), json={"confirm_understood": False}).status_code == 422
    revoked = client.post("/api/v1/me/accountant-access/revocation", headers=headers(auth), json={"confirm_understood": True, "reason": "Changed accountant"})
    assert revoked.status_code == 200, revoked.text
    assert client.post(f"/api/v1/staff/drivers/{owner}/overview", headers=members["accountant"][1], json={"tax_year": YEAR}).status_code == 404
    assign = client.post("/api/v1/staff/handoffs/assign", headers=mutation(members["admin"][1]), json={"ids": [str(handoff.id)], "accountant_id": str(members["accountant"][0].id),
        "versions": {str(handoff.id): 1}, "reason": "Put them back"})
    assert assign.status_code == 409 and "revoked" in assign.json()["detail"]


def test_user_admin_guards(client, driver_books):
    members, *_ = driver_books
    admin = members["admin"][1]
    assert client.post("/api/v1/staff/users/search", headers=members["accountant"][1], json={"sort": "name"}).status_code == 403
    assert client.post("/api/v1/staff/users/search", headers=admin, json={"sort": "name"}).json()["total"] == 5
    team = client.post("/api/v1/staff/teams", headers=mutation(admin), json={"name": "North"}).json()
    new = {"email": "new.accountant@practice.example", "name": "New Accountant", "role": "accountant", "password": "long-enough-password-1"}
    assert client.post("/api/v1/staff/users", headers=mutation(admin), json=new).status_code == 422
    created = client.post("/api/v1/staff/users", headers=mutation(admin), json={**new, "team_id": team["id"]})
    assert created.status_code == 201, created.text
    assert "password" not in created.text.lower()
    assert client.post("/api/v1/staff/users", headers=mutation(admin), json={**new, "team_id": team["id"]}).status_code == 409
    # A driver identity is never promoted implicitly.
    assert client.post("/api/v1/staff/users", headers=mutation(admin), json={**new, "email": "driver@example.com", "team_id": team["id"]}).status_code == 409
    login = client.post("/api/v1/staff/auth/login", json={"email": new["email"], "password": new["password"]})
    assert login.status_code == 200
    bearer = {"Authorization": "Bearer " + login.json()["access_token"]}
    me = created.json()
    deactivated = client.patch("/api/v1/staff/users/" + me["id"], headers=mutation(admin), json={"expected_version": me["version"], "active": False, "reason": "Left the practice"})
    assert deactivated.status_code == 200, deactivated.text
    assert client.get("/api/v1/staff/me", headers=bearer).status_code == 401
    admin_row = next(row for row in client.post("/api/v1/staff/users/search", headers=admin, json={"sort": "name", "page_size": 50}).json()["items"] if row["role"] == "admin")
    assert client.patch("/api/v1/staff/users/" + admin_row["id"], headers=mutation(admin), json={"expected_version": admin_row["version"], "active": False, "reason": "Self removal"}).status_code == 409
    assert client.patch("/api/v1/staff/users/" + admin_row["id"], headers=mutation(admin), json={"expected_version": admin_row["version"], "role": "support", "reason": "Self demotion"}).status_code == 409
    assert client.post("/api/v1/staff/audit/search", headers=admin, json={"filters": {"action": "staff_updated"}}).json()["total"] == 1


def test_ai_feedback_is_recorded_and_scoped(client, db_session, driver_books):
    members, owner, auth, business = driver_books
    file = PrivateFile(owner_id=owner, sha256="b" * 64, mime_type="image/png", content=b"x", size_bytes=1, scan_status="clean")
    db_session.add(file); db_session.flush()
    receipt = Receipt(owner_id=owner, file_id=file.id, business_id=UUID(business), processing_status="review_required",
        extraction={"merchant": "Shell", "amount_pence": 4200, "occurred_on": "2025-10-01", "confidence": 0.61, "warnings": ["low_contrast"], "suggested_category_id": str(catalog_id("category", "fuel"))})
    empty_file = PrivateFile(owner_id=owner, sha256="c" * 64, mime_type="image/png", content=b"y", size_bytes=1, scan_status="clean")
    db_session.add_all([receipt, empty_file]); db_session.flush()
    db_session.add(Receipt(owner_id=owner, file_id=empty_file.id, business_id=UUID(business), processing_status="queued"))
    db_session.commit()
    accountant = members["accountant"][1]
    queue = client.post("/api/v1/staff/ai-reviews/search", headers=accountant, json={"filters": {"feedback": "open"}})
    assert queue.status_code == 200, queue.text
    assert queue.json()["total"] == 1
    assert queue.json()["items"][0]["suggested_category"] == "fuel"
    assert client.post("/api/v1/staff/ai-reviews/search", headers=members["other"][1], json={}).json()["total"] == 0
    path = f"/api/v1/staff/ai-reviews/{receipt.id}/feedback"
    assert client.post(path, headers=mutation(accountant), json={"verdict": "corrected", "reason": "Wrong"}).status_code == 422
    assert client.post(path, headers=mutation(members["support"][1]), json={"verdict": "accepted"}).status_code == 403
    assert client.post(path, headers=mutation(members["other"][1]), json={"verdict": "accepted"}).status_code == 404
    saved = client.post(path, headers=mutation(accountant), json={"verdict": "corrected", "corrections": {"merchant": "Shell Heathrow"}, "reason": "OCR cut the name"})
    assert saved.status_code == 201, saved.text
    assert saved.json()["feedback_verdict"] == "corrected"
    summary = client.post("/api/v1/staff/ai-reviews/summary", headers=accountant).json()
    assert (summary["extractions"], summary["reviewed"], summary["open"], summary["corrected"]) == (1, 1, 0, 1)
    # Feedback never changes the ledger or the receipt's own review state.
    assert db_session.get(Receipt, receipt.id).review_status == "pending"


def test_deletion_erases_personal_data_and_keeps_tax_records_locked(client, db_session, driver_books):
    members, owner, auth, business = driver_books
    income(client, auth, business)
    client.patch("/api/v1/me", headers=headers(auth), json={"first_name": "Ali", "last_name": "Khan", "expected_version": 1})
    made = client.post("/api/v1/me/privacy-requests", headers=headers(auth), json={"kind": "deletion", "detail": "Please delete my account"})
    assert made.status_code == 201, made.text
    assert "five years" in made.json()["notice"]
    assert client.post("/api/v1/me/privacy-requests", headers=headers(auth), json={"kind": "deletion"}).status_code == 409
    admin = members["admin"][1]
    assert client.post("/api/v1/staff/privacy-requests/search", headers=members["senior_accountant"][1], json={}).status_code == 403
    row = client.post("/api/v1/staff/privacy-requests/search", headers=admin, json={"filters": {"kind": "deletion"}}).json()["items"][0]
    assert row["driver_name"] == "Ali Khan" and row["overdue"] is False
    path = f"/api/v1/staff/privacy-requests/{row['id']}"
    assert client.patch(path, headers=mutation(admin), json={"expected_version": row["version"], "status": "completed", "resolution": "Done"}).status_code == 409
    assert client.post(path + "/execute-deletion", headers=mutation(admin), json={"expected_version": row["version"], "confirm_driver_name": "Someone else", "reason": "Requested"}).status_code == 422
    done = client.post(path + "/execute-deletion", headers=mutation(admin), json={"expected_version": row["version"], "confirm_driver_name": "ali khan", "reason": "Requested by the driver"})
    assert done.status_code == 200, done.text
    # 2025-26 ends April 2026, so filing falls on 31 Jan 2027 and retention runs to 31 Jan 2032.
    assert done.json()["retain_until"] == "2032-01-31"
    user = db_session.get(User, owner)
    db_session.refresh(user)
    assert user.email is None and user.display_name is None
    assert client.get("/api/v1/me", headers=auth).status_code == 401
    assert db_session.query(Transaction).filter(Transaction.owner_id == owner).count() == 1
    assert db_session.get(DriverAssignment, owner) is None
    # The driver leaves working lists, for admins too.
    assert client.post("/api/v1/staff/drivers/search", headers=admin, json={}).json()["total"] == 0
    assert client.post(f"/api/v1/staff/drivers/{owner}/overview", headers=admin, json={"tax_year": YEAR}).status_code == 404
    assert db_session.query(StaffAudit).filter(StaffAudit.action == "personal_data_deleted").count() == 1


def test_this_version_has_no_staff_billing_surface(client, driver_books):
    members, owner, auth, _ = driver_books
    admin = members["admin"][1]
    assert client.post("/api/v1/staff/subscriptions/search", headers=admin, json={}).status_code == 404
    assert "subscription" not in client.get("/api/v1/home/summary", headers=auth).json()
    assert "subscription" not in client.post(f"/api/v1/staff/drivers/{owner}/overview", headers=admin, json={"tax_year": YEAR}).json()
    # Every feature stays available without a plan.
    assert client.get("/api/v1/me/subscription", headers=auth).json()["status"] == "none"
