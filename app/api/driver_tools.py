"""Driver features from the product spec: tax history, MTD status, VAT monitor, home,
documents, platform figures, vehicle disposal and accountant access control."""
from datetime import date, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.api.profiles import Key
from app.api.reports import dashboard_response
from app.models import User
from app.models.books import DriverDocument, Notification, PrivateFile, Profile, SupportRecord, Transaction, Vehicle
from app.models.common import utc_now
from app.models.staff import DriverAssignment, StaffAccount, StaffAudit
from app.schemas.books import Body, NonnegativeMoney, Version, Versioned, Year
from app.services.books import SOURCES, check_version, history, owned, profile, rows, tax_dates, tax_year, wire, write
from app.services.mtd_status import evaluate, quarters
from app.services.sessions import lock_user
from app.services.staff import StaffAuth, add_audit, require_driver
from app.services.tax import deadlines, mtd_thresholds, today, vat_threshold

router = APIRouter(tags=["driver tools"])
staff_router = APIRouter(prefix="/staff", tags=["staff driver tools"])
DOCUMENT_TYPES = ("phv_licence", "taxi_badge", "vehicle_licence", "mot", "insurance", "v5c", "other")
EXPIRY_NOTICE_DAYS = 30


class TaxHistoryInput(Body):
    gross_se_income_pence: NonnegativeMoney = 0
    gross_other_se_income_pence: NonnegativeMoney = 0
    gross_property_income_pence: NonnegativeMoney = 0
    paye_income_pence: NonnegativeMoney = 0
    expenses_pence: NonnegativeMoney | None = None
    profit_pence: int | None = Field(default=None, strict=True)
    source: Literal["filed", "estimate", "extracted"] = "estimate"
    return_filed: Literal["yes", "no", "not_yet_due"] = "not_yet_due"
    evidence_file_id: UUID | None = None
    expected_version: Version | None = None


class TradeInput(Body):
    trade_start_date: date | None = None
    accounting_date: Literal["04-05", "03-31", "other"] = "04-05"


class VoluntaryInput(Body):
    opt_in: bool


class CeaseInput(Body):
    ceased_on: date
    reason: str | None = Field(default=None, max_length=500)


class DocumentInput(Body):
    doc_type: Literal["phv_licence", "taxi_badge", "vehicle_licence", "mot", "insurance", "v5c", "other"]
    reference: str | None = Field(default=None, max_length=100)
    expires_on: date | None = None
    vehicle_id: UUID | None = None
    file_id: UUID | None = None


class DocumentPatch(Versioned):
    reference: str | None = Field(default=None, max_length=100)
    expires_on: date | None = None
    file_id: UUID | None = None
    active: bool | None = None


class PlatformReport(Body):
    tax_year: Year
    source_id: UUID
    reported_gross_pence: NonnegativeMoney
    dispute_note: str | None = Field(default=None, max_length=2000)
    evidence_file_id: UUID | None = None


class DisposalInput(Versioned):
    disposed_on: date
    disposal_reason: Literal["sold", "written_off", "stolen"]
    proceeds_pence: NonnegativeMoney | None = None


class RevokeInput(Body):
    confirm_understood: Literal[True]
    reason: str | None = Field(default=None, max_length=500)


class MtdOverride(Body):
    exempt: bool
    reason: str = Field(min_length=3, max_length=500)


def history_map(db, owner):
    return {row.scope: row.data for row in db.scalars(rows(db, Profile, owner).where(Profile.kind == "tax_history"))}


def mtd_result(db, owner):
    trade = profile(db, owner, "trade")
    values = trade.data if trade else {}
    start = values.get("trade_start_date")
    result = evaluate(history_map(db, owner), mtd_thresholds(db), today(), values.get("accounting_date"),
        date.fromisoformat(start) if start else None, bool(values.get("exempt")), bool(values.get("voluntary")),
        values.get("ceased_on"), bool(values.get("exited")))
    return result


def refresh_status(db, owner, reason):
    """Every status change leaves an audit row with its reason."""
    result = mtd_result(db, owner)
    item = profile(db, owner, "mtd_status", create=True)
    if item.data.get("status") != result["status"]:
        before = dict(item.data)
        item.data = {"status": result["status"], "start_date": str(result["start_date"]) if result["start_date"] else None,
            "confidence": result["confidence"], "reason": result["reason"], "computed_at": utc_now().isoformat()}
        item.version += 1
        history(db, item, "mtd_status_change", before, reason)
    return result


def merge_trade(db, owner, **values):
    item = profile(db, owner, "trade", create=True)
    before = dict(item.data)
    item.data = {**item.data, **values}
    item.version += 1
    history(db, item, "trade_update", before)
    return item


@router.get("/tax-history")
def tax_history(user: CurrentUser, db: SessionDep):
    return {"items": [{"tax_year": row.scope, "version": row.version, **row.data}
        for row in db.scalars(rows(db, Profile, user.id).where(Profile.kind == "tax_history").order_by(Profile.scope.desc()))]}


@router.put("/tax-history/{year}")
def put_tax_history(year: str, data: TaxHistoryInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        tax_dates(year)
        if data.evidence_file_id:
            owned(db, PrivateFile, user.id, data.evidence_file_id)
        item = profile(db, user.id, "tax_history", year)
        before = None
        if item:
            check_version(item, data.expected_version)
            before = dict(item.data)
            item.version += 1
        else:
            item = profile(db, user.id, "tax_history", year, create=True)
        item.data = data.model_dump(mode="json", exclude={"expected_version"})
        history(db, item, "tax_history", before)
        status = refresh_status(db, user.id, f"Tax history changed for {year}")
        # MTD uses takings before costs. A takings figure equal to profit is probably the wrong one.
        takings = data.gross_se_income_pence + data.gross_other_se_income_pence
        prompts = ["confirm_takings_before_costs"] if data.profit_pence and (not takings or takings == data.profit_pence) else []
        return {"tax_year": year, "version": item.version, **item.data, "mtd": status, "prompts": prompts}
    return write(db, user, request, key, {**data.model_dump(mode="json"), "year": year}, apply)


@router.put("/me/trade")
def put_trade(data: TradeInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        item = merge_trade(db, user.id, **data.model_dump(mode="json"))
        return {**item.data, "mtd": refresh_status(db, user.id, "Trade details changed")}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/mtd/status")
def mtd_status(user: CurrentUser, db: SessionDep):
    lock_user(db, user.id)
    result = refresh_status(db, user.id, "Dates moved on since the last check")
    db.commit()
    return {**result, "excluded_income_note": "PAYE wages, savings, dividends and pensions do not count toward MTD."}


@router.get("/mtd/calendar")
def mtd_calendar(tax_year: str, user: CurrentUser, db: SessionDep):
    tax_dates(tax_year)
    status = mtd_result(db, user.id)
    required = status["status"] in {"mandated", "voluntary", "upcoming", "exit_eligible"}
    accepted = {record.data.get("obligation_id") for record in db.scalars(rows(db, SupportRecord, user.id).where(
        SupportRecord.kind == "mtd_update", SupportRecord.data["status"].astext == "accepted"))}
    start = status["start_date"]
    items = []
    for quarter in quarters(tax_year):
        in_scope = required and start is not None and quarter["period_end"] >= start
        state = "not_required" if not in_scope else "accepted" if quarter["id"] in accepted else "overdue" if quarter["due_on"] < today() else "upcoming"
        # Late quarterly updates only earn penalty points from 2027-28.
        items.append({**quarter, "status": state, "penalty_point": state == "overdue" and tax_year >= "2027-28"})
    return {"tax_year": tax_year, "mtd_status": status["status"], "items": items, "penalty_points": sum(item["penalty_point"] for item in items),
        "note": "Quarterly updates are cumulative for the year and are not bills. Payment dates stay 31 January and 31 July."}


@router.post("/mtd/voluntary")
def voluntary(data: VoluntaryInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        merge_trade(db, user.id, voluntary=data.opt_in)
        return refresh_status(db, user.id, "Driver chose voluntary MTD" if data.opt_in else "Driver left voluntary MTD")
    return write(db, user, request, key, data.model_dump(), apply)


@router.post("/mtd/exit")
def mtd_exit(user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        if mtd_result(db, user.id)["status"] != "exit_eligible":
            raise HTTPException(409, "You can leave MTD only after three years in a row at or below the threshold")
        merge_trade(db, user.id, exited=True)
        return refresh_status(db, user.id, "Driver left MTD after three years below the threshold")
    return write(db, user, request, key, {}, apply)


@router.post("/trade/cease")
def cease(data: CeaseInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        merge_trade(db, user.id, ceased_on=data.ceased_on.isoformat(), ceased_reason=data.reason)
        return refresh_status(db, user.id, "Driver stopped trading")
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


def vat_position(db, owner):
    # Rolling twelve months of taxable turnover, not the tax year.
    end = today()
    start = end - timedelta(days=365)
    turnover = db.scalar(select(func.coalesce(func.sum(Transaction.amount_pence), 0)).where(Transaction.owner_id == owner,
        Transaction.kind == "income", Transaction.review_status == "confirmed", Transaction.occurred_on.between(start, end)))
    threshold = vat_threshold(db, tax_year(end))
    percent = turnover * 100 // threshold if threshold else 0
    return {"period_start": start, "period_end": end, "rolling_turnover_pence": turnover, "threshold_pence": threshold, "percent_of_threshold": percent,
        "status": "over" if turnover > threshold else "approaching" if percent >= 80 else "below",
        "note": "Monitor only. From 2 January 2026 Uber and Bolt changed how VAT applies to UK fares, which can move net payouts; ask your accountant if you are near the threshold."}


@router.get("/tax/vat-monitor")
def vat_monitor(user: CurrentUser, db: SessionDep):
    return vat_position(db, user.id)


def document_wire(row, day=None):
    day = day or today()
    remaining = (row.expires_on - day).days if row.expires_on else None
    state = "no_expiry" if remaining is None else "expired" if remaining < 0 else "expiring_soon" if remaining <= EXPIRY_NOTICE_DAYS else "valid"
    return {**wire(row), "days_remaining": remaining, "expiry_status": state}


@router.get("/me/documents")
def documents(user: CurrentUser, db: SessionDep):
    return {"items": [document_wire(row) for row in db.scalars(rows(db, DriverDocument, user.id).where(DriverDocument.active.is_(True)).order_by(DriverDocument.expires_on.asc().nullslast(), DriverDocument.id))]}


@router.post("/me/documents", status_code=201)
def add_document(data: DocumentInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        if data.vehicle_id:
            owned(db, Vehicle, user.id, data.vehicle_id)
        if data.file_id:
            owned(db, PrivateFile, user.id, data.file_id)
        row = DriverDocument(owner_id=user.id, **data.model_dump())
        db.add(row)
        history(db, row, "create")
        return document_wire(row)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.patch("/me/documents/{id}")
def patch_document(id: UUID, data: DocumentPatch, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, DriverDocument, user.id, id)
        check_version(row, data.expected_version)
        changes = data.model_dump(exclude_unset=True, exclude={"expected_version"})
        if not changes:
            raise HTTPException(422, "Empty patch")
        if changes.get("file_id"):
            owned(db, PrivateFile, user.id, changes["file_id"])
        before = wire(row)
        for field, value in changes.items():
            setattr(row, field, value)
        row.version += 1
        history(db, row, "correction", before)
        return document_wire(row)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


def platform_rows(db, owner, year):
    start, end = tax_dates(year)
    recorded = dict(db.execute(select(Transaction.source_id, func.sum(Transaction.amount_pence)).where(Transaction.owner_id == owner,
        Transaction.kind == "income", Transaction.review_status == "confirmed", Transaction.occurred_on.between(start, end)).group_by(Transaction.source_id)).all())
    reports = {row.scope.split(":", 1)[1]: row for row in db.scalars(rows(db, Profile, owner).where(Profile.kind == "platform_report", Profile.scope.startswith(year + ":")))}
    items = []
    for source_id, source in SOURCES.items():
        if source["kind"] != "platform":
            continue
        report = reports.get(source["code"])
        app_gross = int(recorded.get(source_id, 0))
        items.append({"source_id": source_id, "source": source["name"], "app_gross_pence": app_gross,
            "platform_reported_gross_pence": report.data["reported_gross_pence"] if report else None,
            "difference_pence": report.data["reported_gross_pence"] - app_gross if report else None,
            "status": report.data["status"] if report else "not_entered", "dispute_note": report.data.get("dispute_note") if report else None,
            "version": report.version if report else None})
    return items


@router.get("/tax/platform-reconciliation")
def platform_reconciliation(tax_year: str, user: CurrentUser, db: SessionDep):
    tax_dates(tax_year)
    return {"tax_year": tax_year, "items": platform_rows(db, user.id, tax_year),
        "note": "Platforms report income to HMRC. Enter the figure from their annual tax summary. A dispute keeps a record for your accountant; it does not change your books."}


@router.put("/tax/platform-reports")
def put_platform_report(data: PlatformReport, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        start, end = tax_dates(data.tax_year)
        source = SOURCES.get(data.source_id)
        if not source or source["kind"] != "platform":
            raise HTTPException(422, "Select a platform income source")
        if data.evidence_file_id:
            owned(db, PrivateFile, user.id, data.evidence_file_id)
        recorded = db.scalar(select(func.coalesce(func.sum(Transaction.amount_pence), 0)).where(Transaction.owner_id == user.id, Transaction.kind == "income",
            Transaction.review_status == "confirmed", Transaction.source_id == data.source_id, Transaction.occurred_on.between(start, end)))
        status = "matched" if recorded == data.reported_gross_pence else "disputed" if data.dispute_note else "mismatch"
        item = profile(db, user.id, "platform_report", f"{data.tax_year}:{source['code']}", create=True)
        before = dict(item.data)
        item.data = {**data.model_dump(mode="json", exclude={"tax_year", "source_id"}), "status": status}
        item.version += 1
        history(db, item, "platform_report", before or None, data.dispute_note)
        return {"tax_year": data.tax_year, "items": platform_rows(db, user.id, data.tax_year)}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.post("/vehicles/{id}/disposal")
def dispose(id: UUID, data: DisposalInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Vehicle, user.id, id)
        check_version(row, data.expected_version)
        if row.details.get("disposed_on"):
            raise HTTPException(409, "This vehicle is already marked as disposed")
        if data.disposed_on < row.business_start_on or data.disposed_on > today():
            raise HTTPException(422, "Disposal date must be between the vehicle's start date and today")
        if data.proceeds_pence is not None and row.claim_method != "actual":
            raise HTTPException(422, "Sale or insurance proceeds apply only to actual-cost vehicles")
        before = wire(row)
        row.details = {**row.details, **data.model_dump(mode="json", exclude={"expected_version"})}
        # The method lock ends with the vehicle; its history stays on the record.
        row.active, row.method_locked = False, False
        row.version += 1
        mutation = history(db, row, "disposal", before, data.disposal_reason)
        warnings = ["balancing_allowance_or_charge_needs_accountant_review"] if row.claim_method == "actual" else []
        return {"id": row.id, "version": row.version, "active": row.active, "mutation_id": mutation, "warnings": warnings, **data.model_dump(mode="json", exclude={"expected_version"})}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


def access_state(db, owner):
    assignment = db.get(DriverAssignment, owner)
    accountant = db.get(StaffAccount, assignment.accountant_id) if assignment else None
    item = profile(db, owner, "accountant_access")
    return {"has_accountant": bool(accountant), "accountant_name": accountant.name if accountant else None,
        "scope": ["income", "expenses", "mileage", "receipts", "documents", "tax", "messages"] if accountant else [],
        "revoked_at": item.data.get("revoked_at") if item else None,
        "revocation_notice": "Access ends immediately. Messages and filed returns stay in the audit record. Copies the firm already downloaded are its responsibility under the data processing agreement."}


@router.get("/me/accountant-access")
def accountant_access(user: CurrentUser, db: SessionDep):
    return access_state(db, user.id)


@router.post("/me/accountant-access/revocation")
def revoke_access(data: RevokeInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        assignment = db.get(DriverAssignment, user.id, populate_existing=True)
        if not assignment:
            raise HTTPException(409, "No accountant currently has access")
        before = {"accountant_id": str(assignment.accountant_id)}
        db.delete(assignment)
        db.flush()
        item = profile(db, user.id, "accountant_access", create=True)
        item.data = {"revoked_at": utc_now().isoformat(), "reason": data.reason}
        item.version += 1
        history(db, item, "accountant_access_revoked", before, data.reason)
        return access_state(db, user.id)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/me/access-log")
def access_log(user: CurrentUser, db: SessionDep, limit: int = 50):
    limit = min(max(limit, 1), 200)
    records = db.execute(select(StaffAudit, StaffAccount.name).join(StaffAccount, StaffAccount.id == StaffAudit.actor_id).where(
        StaffAudit.driver_id == user.id).order_by(StaffAudit.created_at.desc(), StaffAudit.id).limit(limit))
    return {"items": [{"id": event.id, "who": name, "action": event.action, "at": event.created_at} for event, name in records]}


@router.get("/home/summary")
def home_summary(user: CurrentUser, db: SessionDep, year: str | None = None):
    year = year or tax_year(today())
    tax_dates(year)
    lock_user(db, user.id)
    totals = dashboard_response(db, user.id, year)
    expiring = [document_wire(row) for row in db.scalars(rows(db, DriverDocument, user.id).where(DriverDocument.active.is_(True),
        DriverDocument.expires_on.is_not(None), DriverDocument.expires_on <= today() + timedelta(days=EXPIRY_NOTICE_DAYS)).order_by(DriverDocument.expires_on))]
    status = mtd_result(db, user.id)
    next_update = None
    if status["status"] in {"mandated", "voluntary", "exit_eligible"}:
        next_update = next((item for item in quarters(year) if item["due_on"] >= today()), None)
    return {"tax_year": year, "as_of": utc_now(), "income_pence": totals["income_pence"], "expenses_pence": totals["deductible_expenses_pence"],
        "profit_pence": totals["profit_pence"], "estimated_tax_pence": totals["estimated_tax_pence"], "week_income_pence": totals["week_total_pence"],
        "business_miles": totals["business_miles"], "pending_receipts": totals["pending_receipts"], "unread_notifications": totals["unread_notifications"],
        "next_deadline": deadlines(year)[0], "expiring_documents": expiring,
        "mtd": {"status": status["status"], "start_date": status["start_date"], "reason": status["reason"], "next_update": next_update,
                "near_threshold": status["near_threshold"]},
        "vat": vat_position(db, user.id), "warnings": totals["warnings"]}


@staff_router.post("/drivers/{driver_id}/mtd")
def staff_mtd(driver_id: UUID, auth: StaffAuth, db: SessionDep):
    require_driver(db, auth[0], driver_id)
    add_audit(db, auth[0], "mtd_view", driver_id)
    result = mtd_result(db, driver_id)
    db.commit()
    return {**result, "history": [{"tax_year": row.scope, "version": row.version, **row.data} for row in db.scalars(
        rows(db, Profile, driver_id).where(Profile.kind == "tax_history").order_by(Profile.scope.desc()))],
        "vat": vat_position(db, driver_id), "platform": {year: platform_rows(db, driver_id, year) for year in [tax_year(today())]}}


@staff_router.post("/drivers/{driver_id}/mtd/override")
def staff_mtd_override(driver_id: UUID, data: MtdOverride, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    if staff.role not in {"admin", "senior_accountant"}:
        raise HTTPException(403, "MTD exemptions require a senior accountant")
    user = require_driver(db, staff, driver_id, write=True)
    def apply():
        require_driver(db, staff, driver_id, write=True)
        merge_trade(db, driver_id, exempt=data.exempt)
        result = refresh_status(db, driver_id, data.reason)
        add_audit(db, staff, "mtd_exemption_changed", driver_id, after={"exempt": data.exempt, "reason": data.reason, "status": result["status"]})
        return result
    return write(db, user, request, key, {**data.model_dump(), "staff_id": str(staff.id)}, apply)
