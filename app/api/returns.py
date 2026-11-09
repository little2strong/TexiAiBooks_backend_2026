"""Tax return workspace: checklist, adjustments, driver sign-off and recorded filing.

Nothing here sends a return to HMRC. Filing records an external reference and
freezes the year's calculation so later rate changes cannot alter it.
"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from pydantic import Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.api.profiles import Key
from app.api.reports import dashboard_response
from app.api.staff import audit_projection, audit_read
from app.models import User
from app.models.books import Mileage, Notification, Profile, TaxAdjustment, TaxReturn, Transaction, Vehicle
from app.models.common import utc_now
from app.models.staff import AccountantHandoff, StaffAccount, StaffEntry
from app.schemas.books import Body, Version, Versioned, Year
from app.schemas.staff import TableQuery
from app.services.books import check_version, history, owned, profile, rows, tax_dates, wire, write
from app.services.sessions import lock_user
from app.services.staff import (StaffAuth, add_audit, driver_name, driver_scope, driver_summary, paginate,
    query_filters, require_driver)
from app.services.tax import estimate, rule_set, today

router = APIRouter(prefix="/staff", tags=["staff tax returns"])
driver_router = APIRouter(tags=["driver tax return sign-off"])


class ReturnCreate(Body):
    driver_id: UUID
    tax_year: Year


class AdjustmentInput(Versioned):
    target: Literal["income", "expenses", "capital_allowances"]
    amount_pence: int = Field(strict=True, ge=-9_000_000_000_000, le=9_000_000_000_000)
    reason: str = Field(min_length=3, max_length=500)
    record_type: Literal["transaction", "mileage", "receipt"] | None = None
    record_id: UUID | None = None


class ReasonInput(Versioned):
    reason: str = Field(min_length=3, max_length=500)


class FileInput(ReasonInput):
    filing_reference: str = Field(min_length=3, max_length=200)


class DriverDecision(Versioned):
    review_version: Version
    decision: Literal["approve", "request_changes"]
    note: str | None = Field(default=None, max_length=2000)


def checklist(db, owner, year):
    """Blocking items must clear before sign-off. Warnings stay visible but do not stop it."""
    start, end = tax_dates(year)
    totals = dashboard_response(db, owner, year)
    drafts = db.scalar(select(func.count()).select_from(Transaction).where(Transaction.owner_id == owner,
        Transaction.review_status == "draft", Transaction.occurred_on.between(start, end)))
    logged = select(Mileage.vehicle_id).where(Mileage.owner_id == owner, Mileage.active.is_(True), Mileage.occurred_on.between(start, end))
    unelected = db.scalar(select(func.count()).select_from(Vehicle).where(Vehicle.owner_id == owner, Vehicle.claim_method == "unset", Vehicle.id.in_(logged)))
    tax = profile(db, owner, "tax", year)
    has_records = bool(totals["income_pence"]) or bool(totals["has_data"])
    mismatched = [row for row in db.scalars(rows(db, Profile, owner).where(Profile.kind == "platform_report", Profile.scope.startswith(year + ":")))
                  if row.data.get("status") != "matched"]
    def item(id, label, passed, detail, severity="block", tab=None):
        return {"id": id, "label": label, "status": "pass" if passed else severity, "detail": detail, "tab": tab}
    return [
        item("year_ended", "Tax year has ended", today() > end, f"The {year} tax year ends on {end}. A full-year return cannot be reviewed before then."),
        item("tax_profile", "Tax profile supplied", bool(tax), "Region, PAYE and other income inputs drive the calculation." if tax else "The driver has not saved tax profile inputs for this year.", tab="tax"),
        item("drafts", "No unconfirmed ledger drafts", not drafts, f"{drafts} draft posting(s) are excluded from totals.", tab="income"),
        item("receipts", "Receipts reviewed", not totals["pending_receipts"], f"{totals['pending_receipts']} receipt(s) still need a decision.", tab="receipts"),
        item("reconciliation", "Statements reconciled", not totals["unresolved_issues"], f"{totals['unresolved_issues']} reconciliation issue(s) remain open.", tab="income"),
        item("vehicle_methods", "Vehicle method chosen", not unelected, f"{unelected} vehicle(s) have mileage but no claim method.", tab="mileage"),
        item("records", "Records exist for the year", has_records, "Income, expenses or mileage were recorded." if has_records else "No records exist; confirm this is a nil return.", "warn", "income"),
        item("utr", "UTR on file", bool(tax and tax.data.get("utr_masked")), "A UTR is needed before an external filing can be made.", "warn", "overview"),
        item("platform", "Platform figures agree", not mismatched, f"{len(mismatched)} platform report(s) differ from recorded gross income.", "warn", "income"),
    ]


def adjustment_wire(db, row):
    author = db.get(StaffAccount, row.created_by)
    return {**wire(row), "created_by_name": author.name if author else None}


def return_wire(db, row):
    driver = db.get(User, row.owner_id)
    summary = driver_summary(db, driver)
    return {**{key: value for key, value in wire(row).items() if key not in {"snapshot", "earlier_snapshots"}},
        "driver_id": row.owner_id, "driver_name": summary["name"], "driver_email": summary["email"],
        "accountant_name": summary["accountant_name"], "filed_by_name": db.get(StaffAccount, row.filed_by).name if row.filed_by else None}


def workspace(db, row):
    try:
        calculation = estimate(db, row.owner_id, row.tax_year)
    except HTTPException as error:
        if error.status_code not in {404, 409, 422}:
            raise
        calculation = {"available": False, "reason": error.detail}
    records = list(db.scalars(rows(db, TaxAdjustment, row.owner_id).where(TaxAdjustment.return_id == row.id).order_by(TaxAdjustment.created_at, TaxAdjustment.id)))
    items = checklist(db, row.owner_id, row.tax_year)
    return {**return_wire(db, row), "checklist": items, "blockers": sum(item["status"] == "block" for item in items),
        "estimate": calculation, "adjustments": [adjustment_wire(db, item) for item in records],
        "snapshot": row.snapshot, "earlier_snapshots": row.earlier_snapshots,
        "events": audit_projection(db, row.owner_id, row.id)}


def locked_return(db, staff, id, *, write_access=True):
    row = db.get(TaxReturn, id)
    if not row:
        raise HTTPException(404, "Tax return not found")
    lock_user(db, row.owner_id)
    require_driver(db, staff, row.owner_id, write=write_access)
    db.refresh(row)
    return row


def driver_for(db, id):
    row = db.get(TaxReturn, id)
    if not row:
        raise HTTPException(404, "Tax return not found")
    return db.get(User, row.owner_id)


def notify(db, row, title_key):
    db.add(Notification(owner_id=row.owner_id, type="tax_return", title_key=title_key, body_key=title_key + ".body",
        params={"tax_year": row.tax_year, "review_version": row.review_version}, resource_type="tax_return", resource_id=row.id))


@router.post("/returns/search")
def search_returns(data: TableQuery, auth: StaffAuth, db: SessionDep):
    staff = auth[0]
    query_filters(data, {"status", "tax_year"})
    query = select(TaxReturn).where(TaxReturn.owner_id.in_(driver_scope(staff)))
    if data.filters.get("status"):
        query = query.where(TaxReturn.status == data.filters["status"])
    if data.filters.get("tax_year"):
        query = query.where(TaxReturn.tax_year == data.filters["tax_year"])
    result = paginate(db, query, TaxReturn, data, {"created_at": TaxReturn.created_at, "tax_year": TaxReturn.tax_year,
        "status": TaxReturn.status}, lambda row: return_wire(db, row))
    audit_read(db, staff, "tax_return_queue_view", after={"count": len(result["items"])})
    return result


@router.post("/returns", status_code=201)
def open_return(data: ReturnCreate, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    user = require_driver(db, staff, data.driver_id, write=True)
    tax_dates(data.tax_year)
    def apply():
        require_driver(db, staff, data.driver_id, write=True)
        row = db.scalar(rows(db, TaxReturn, data.driver_id).where(TaxReturn.tax_year == data.tax_year))
        if not row:
            row = TaxReturn(owner_id=data.driver_id, tax_year=data.tax_year, earlier_snapshots=[], review_version=0)
            db.add(row)
            db.flush()
            add_audit(db, staff, "tax_return_opened", data.driver_id, row.id, after={"tax_year": data.tax_year})
        return return_wire(db, row)
    return write(db, user, request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


@router.get("/returns/{id}")
def get_return(id: UUID, auth: StaffAuth, db: SessionDep):
    row = locked_return(db, auth[0], id, write_access=False)
    result = workspace(db, row)
    audit_read(db, auth[0], "tax_return_view", row.owner_id, {"return_id": str(id)})
    return result


@router.post("/returns/{id}/adjustments", status_code=201)
def add_adjustment(id: UUID, data: AdjustmentInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    def apply():
        row = locked_return(db, staff, id)
        check_version(row, data.expected_version)
        if row.status != "in_preparation":
            raise HTTPException(409, "Reopen the return before changing adjustments")
        if data.amount_pence == 0:
            raise HTTPException(422, "Adjustment amount cannot be zero")
        if data.target == "capital_allowances" and data.amount_pence < 0:
            raise HTTPException(422, "Enter capital allowances as a positive deduction")
        if bool(data.record_type) != bool(data.record_id):
            raise HTTPException(422, "Link a record with both its type and its ID")
        adjustment = TaxAdjustment(owner_id=row.owner_id, return_id=row.id, tax_year=row.tax_year, created_by=staff.id,
            **data.model_dump(exclude={"expected_version"}))
        db.add(adjustment)
        row.version += 1
        db.flush()
        history(db, adjustment, "accountant_adjustment", None, data.reason)
        add_audit(db, staff, "tax_adjustment_added", row.owner_id, row.id, after=wire(adjustment))
        return workspace(db, row)
    return write(db, driver_for(db, id), request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


@router.post("/returns/{id}/adjustments/{adjustment_id}/void")
def void_adjustment(id: UUID, adjustment_id: UUID, data: ReasonInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    def apply():
        row = locked_return(db, staff, id)
        check_version(row, data.expected_version)
        if row.status != "in_preparation":
            raise HTTPException(409, "Reopen the return before changing adjustments")
        adjustment = owned(db, TaxAdjustment, row.owner_id, adjustment_id)
        if adjustment.return_id != row.id:
            raise HTTPException(404, "Adjustment not found")
        if adjustment.voided_at:
            raise HTTPException(409, "Adjustment is already void")
        before = wire(adjustment)
        adjustment.voided_at, adjustment.voided_by, adjustment.void_reason = utc_now(), staff.id, data.reason
        adjustment.version += 1
        row.version += 1
        history(db, adjustment, "accountant_adjustment_void", before, data.reason)
        add_audit(db, staff, "tax_adjustment_voided", row.owner_id, row.id, before, {"reason": data.reason})
        return workspace(db, row)
    return write(db, driver_for(db, id), request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


@router.post("/returns/{id}/request-approval")
def request_approval(id: UUID, data: ReasonInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    def apply():
        row = locked_return(db, staff, id)
        check_version(row, data.expected_version)
        if row.status != "in_preparation":
            raise HTTPException(409, "Only a return in preparation can be sent for sign-off")
        blocked = [item["label"] for item in checklist(db, row.owner_id, row.tax_year) if item["status"] == "block"]
        if blocked:
            raise HTTPException(409, "Clear the checklist first: " + "; ".join(blocked))
        calculation = estimate(db, row.owner_id, row.tax_year)
        region = profile(db, row.owner_id, "tax", row.tax_year).data["region"]
        row.review_version += 1
        row.snapshot = jsonable_encoder({"review_version": row.review_version, "estimate": calculation,
            "rules": rule_set(row.tax_year, region, db), "created_at": utc_now(), "created_by": staff.name})
        row.status = "awaiting_driver"
        row.driver_decided_at, row.driver_note = None, None
        row.version += 1
        notify(db, row, "return.approval_requested")
        add_audit(db, staff, "tax_return_sent_for_signoff", row.owner_id, row.id,
            after={"review_version": row.review_version, "total_pence": calculation["total_pence"], "reason": data.reason})
        return workspace(db, row)
    return write(db, driver_for(db, id), request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


@router.post("/returns/{id}/file")
def record_filing(id: UUID, data: FileInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    def apply():
        if staff.role not in {"admin", "senior_accountant"}:
            raise HTTPException(403, "Filing sign-off requires a senior accountant")
        row = locked_return(db, staff, id)
        check_version(row, data.expected_version)
        if row.status != "driver_approved":
            raise HTTPException(409, "The driver must approve this review version before filing is recorded")
        # Any change since sign-off produces a different estimate identity.
        if estimate(db, row.owner_id, row.tax_year)["id"] != row.snapshot["estimate"]["id"]:
            raise HTTPException(409, "Books, inputs or rates changed after sign-off; reopen and send a new version")
        row.status, row.filing_reference, row.filed_at, row.filed_by = "filed", data.filing_reference, utc_now(), staff.id
        row.version += 1
        for handoff in db.scalars(select(AccountantHandoff).where(AccountantHandoff.driver_id == row.owner_id,
                AccountantHandoff.tax_year == row.tax_year, AccountantHandoff.status != "filed")):
            before = wire(handoff)
            handoff.status, handoff.filing_reference = "filed", data.filing_reference
            handoff.version += 1
            add_audit(db, staff, "handoff_updated", row.owner_id, handoff.id, before, {**wire(handoff), "reason": "Filing recorded on the tax return"})
        notify(db, row, "return.filed")
        add_audit(db, staff, "tax_return_filed", row.owner_id, row.id,
            after={"filing_reference": data.filing_reference, "reason": data.reason, "review_version": row.review_version})
        return workspace(db, row)
    return write(db, driver_for(db, id), request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


@router.post("/returns/{id}/reopen")
def reopen(id: UUID, data: ReasonInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    def apply():
        row = locked_return(db, staff, id)
        check_version(row, data.expected_version)
        if row.status == "in_preparation":
            raise HTTPException(409, "This return is already in preparation")
        if row.status == "filed" and staff.role not in {"admin", "senior_accountant"}:
            raise HTTPException(403, "Reopening a filed return requires a senior accountant")
        previous = {**(row.snapshot or {}), "ended_status": row.status, "filing_reference": row.filing_reference, "reopen_reason": data.reason}
        row.earlier_snapshots = [*row.earlier_snapshots, jsonable_encoder(previous)]
        row.status, row.snapshot, row.filing_reference, row.filed_at, row.filed_by = "in_preparation", None, None, None, None
        row.driver_decided_at, row.driver_note = None, None
        row.version += 1
        add_audit(db, staff, "tax_return_reopened", row.owner_id, row.id, after={"reason": data.reason})
        return workspace(db, row)
    return write(db, driver_for(db, id), request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


def driver_return_wire(db, row):
    # Drivers see their figures and accountant adjustments, never internal notes or audit events.
    records = rows(db, TaxAdjustment, row.owner_id).where(TaxAdjustment.return_id == row.id, TaxAdjustment.voided_at.is_(None))
    return {"id": row.id, "tax_year": row.tax_year, "status": row.status, "version": row.version, "review_version": row.review_version,
        "estimate": (row.snapshot or {}).get("estimate"), "filing_reference": row.filing_reference, "filed_at": row.filed_at,
        "driver_decided_at": row.driver_decided_at, "driver_note": row.driver_note,
        "adjustments": [{"id": item.id, "target": item.target, "amount_pence": item.amount_pence, "reason": item.reason} for item in db.scalars(records)],
        "reminder": "Your accountant files this return. The app records the reference; it does not send anything to HMRC."}


@driver_router.get("/me/tax-returns")
def my_returns(user: CurrentUser, db: SessionDep):
    return {"items": [driver_return_wire(db, row) for row in db.scalars(rows(db, TaxReturn, user.id).order_by(TaxReturn.tax_year.desc()))]}


@driver_router.post("/me/tax-returns/{id}/decision")
def decide(id: UUID, data: DriverDecision, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, TaxReturn, user.id, id)
        check_version(row, data.expected_version)
        if row.status != "awaiting_driver" or row.review_version != data.review_version:
            raise HTTPException(409, "This review version is no longer waiting for your decision")
        before = {"status": row.status, "review_version": row.review_version}
        approved = data.decision == "approve"
        if approved and estimate(db, user.id, row.tax_year)["id"] != row.snapshot["estimate"]["id"]:
            raise HTTPException(409, "Your records changed after this review was prepared; ask your accountant for a new version")
        if not approved and not (data.note or "").strip():
            raise HTTPException(422, "Tell your accountant what needs changing")
        row.status, row.driver_decided_at, row.driver_note = "driver_approved" if approved else "in_preparation", utc_now(), data.note
        if not approved:
            row.earlier_snapshots = [*row.earlier_snapshots, {**row.snapshot, "ended_status": "changes_requested", "driver_note": data.note}]
            row.snapshot = None
            db.add(StaffEntry(driver_id=user.id, kind="message", body=f"Changes requested on {row.tax_year} return: {data.note}"))
        row.version += 1
        history(db, row, "driver_" + data.decision, before, data.note)
        return driver_return_wire(db, row)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)
