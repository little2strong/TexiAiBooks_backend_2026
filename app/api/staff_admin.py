"""Staff administration: AI review, users and roles, rates and privacy."""
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
import secrets

from fastapi import APIRouter, HTTPException, Request
from pydantic import EmailStr, Field, SecretStr, field_validator
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, SessionDep
from app.api.profiles import Key
from app.core.security import password_hash
from app.models import DeviceSession, User
from app.models.auth import ExternalIdentity
from app.models.books import (Notification, PhoneIdentity, PrivacyRequest, Profile, Receipt, SupportRecord, Transaction)
from app.models.common import utc_now
from app.models.books import TaxReturn
from app.models.staff import AccountantHandoff, AiFeedback, DriverAssignment, StaffAccount, StaffAudit, TaxRate
from app.schemas.books import Body, Version, Versioned, Year
from app.schemas.staff import StaffRole, TableQuery, YearInput
from app.schemas.user import normalize_email
from app.services.books import CATEGORIES, check_version, history, owned, profile, rows, tax_dates, wire, write
from app.services.files import receipt_wire
from app.services.staff import (StaffAuth, add_audit, driver_name, driver_scope, identity, paginate, query_filters,
    require_admin, require_driver)
from app.services.ledger import mileage_deduction
from app.services.tax import REGIONS, RULE_CODES, UK_SOURCES, builtin_values, calculate, deadlines, rule_set, today

router = APIRouter(prefix="/staff", tags=["staff administration"])
driver_router = APIRouter(tags=["driver privacy requests"])
RETENTION_YEARS = 5


def staff_user(db, staff):
    return db.get(User, staff.id)


def term(value):
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# AI review -----------------------------------------------------------------

class FeedbackInput(Body):
    verdict: Literal["accepted", "corrected", "rejected"]
    corrections: dict[str, str] = Field(default_factory=dict, max_length=10)
    reason: str | None = Field(default=None, max_length=500)


def extracted():
    # SQL NULL and JSON null both mean OCR supplied nothing.
    return func.jsonb_typeof(Receipt.extraction) == "object"


def ai_wire(db, row):
    base = receipt_wire(db, row)
    extraction = row.extraction or {}
    category = CATEGORIES.get(UUID(extraction["suggested_category_id"])) if extraction.get("suggested_category_id") else None
    feedback = db.scalar(select(AiFeedback).where(AiFeedback.receipt_id == row.id).order_by(AiFeedback.created_at.desc(), AiFeedback.id))
    reviewer = db.get(StaffAccount, feedback.staff_id) if feedback else None
    return {"id": row.id, "driver_id": row.owner_id, "driver_name": driver_name(db, db.get(User, row.owner_id)),
        "created_at": row.created_at, "version": row.version, "review_status": row.review_status, "merchant": base.get("merchant"),
        "amount_pence": base.get("amount_pence"), "occurred_on": base.get("occurred_on"),
        "suggested_category": category["code"] if category else None, "confidence": extraction.get("confidence"),
        "warnings": extraction.get("warnings", []), "provider": extraction.get("provider"),
        "feedback_verdict": feedback.verdict if feedback else None, "feedback_by": reviewer.name if reviewer else None,
        "feedback_reason": feedback.reason if feedback else None, "feedback_corrections": feedback.corrections if feedback else {}}


@router.post("/ai-reviews/search")
def ai_reviews(data: TableQuery, auth: StaffAuth, db: SessionDep):
    staff = auth[0]
    query_filters(data, {"review_status", "feedback"})
    query = select(Receipt).where(Receipt.owner_id.in_(driver_scope(staff)), extracted())
    if data.filters.get("review_status"):
        query = query.where(Receipt.review_status == data.filters["review_status"])
    reviewed = select(AiFeedback.receipt_id)
    if data.filters.get("feedback") == "open":
        query = query.where(~Receipt.id.in_(reviewed))
    elif data.filters.get("feedback") == "done":
        query = query.where(Receipt.id.in_(reviewed))
    result = paginate(db, query, Receipt, data, {"created_at": Receipt.created_at, "review_status": Receipt.review_status},
        lambda row: ai_wire(db, row))
    add_audit(db, staff, "ai_review_queue_view", after={"count": len(result["items"])})
    db.commit()
    return result


@router.post("/ai-reviews/summary")
def ai_summary(auth: StaffAuth, db: SessionDep):
    staff = auth[0]
    scope = driver_scope(staff)
    counts = dict(db.execute(select(AiFeedback.verdict, func.count()).where(AiFeedback.driver_id.in_(scope)).group_by(AiFeedback.verdict)).all())
    total = db.scalar(select(func.count()).select_from(Receipt).where(Receipt.owner_id.in_(scope), extracted()))
    reviewed = db.scalar(select(func.count(func.distinct(AiFeedback.receipt_id))).where(AiFeedback.driver_id.in_(scope)))
    decided = sum(counts.values())
    return {"extractions": total, "reviewed": reviewed, "open": max(0, total - reviewed), "accepted": counts.get("accepted", 0),
        "corrected": counts.get("corrected", 0), "rejected": counts.get("rejected", 0),
        "acceptance_percent": round(counts.get("accepted", 0) * 100 / decided) if decided else None}


@router.post("/ai-reviews/{receipt_id}/feedback", status_code=201)
def ai_feedback(receipt_id: UUID, data: FeedbackInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    if data.verdict == "corrected" and not data.corrections:
        raise HTTPException(422, "List the corrected fields")
    if data.verdict != "accepted" and not (data.reason or "").strip():
        raise HTTPException(422, "Give a reason for this feedback")
    def apply():
        row = db.get(Receipt, receipt_id)
        if not row:
            raise HTTPException(404, "Receipt not found")
        require_driver(db, staff, row.owner_id, write=True)
        if not row.extraction:
            raise HTTPException(409, "This receipt has no AI extraction to review")
        db.add(AiFeedback(receipt_id=row.id, driver_id=row.owner_id, staff_id=staff.id, verdict=data.verdict,
            corrections=data.corrections, reason=data.reason, created_at=utc_now()))
        db.flush()
        add_audit(db, staff, "ai_feedback_" + data.verdict, row.owner_id, row.id, after={"fields": sorted(data.corrections), "reason": data.reason})
        return ai_wire(db, row)
    return write(db, staff_user(db, staff), request, key, {**data.model_dump(mode="json"), "receipt_id": str(receipt_id)}, apply)


# Users and roles -----------------------------------------------------------

class StaffCreate(Body):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    role: StaffRole
    password: SecretStr = Field(min_length=12, max_length=128)


class StaffPatch(Versioned):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: StaffRole | None = None
    active: bool | None = None
    reason: str = Field(min_length=3, max_length=500)


class PasswordReset(Versioned):
    password: SecretStr = Field(min_length=12, max_length=128)
    reason: str = Field(min_length=3, max_length=500)


def assigned_count(db, staff_id):
    return db.scalar(select(func.count()).select_from(DriverAssignment).where(DriverAssignment.accountant_id == staff_id))


def staff_wire(db, row):
    last_seen = db.scalar(select(func.max(DeviceSession.last_used_at)).where(DeviceSession.user_id == row.id))
    return {**identity(db, row), "active": row.active, "version": row.version,
        "last_seen_at": last_seen, "assigned_drivers": assigned_count(db, row.id)}


def end_sessions(db, staff_id):
    # Access must end at once rather than waiting for the token to expire.
    db.execute(update(DeviceSession).where(DeviceSession.user_id == staff_id, DeviceSession.revoked_at.is_(None)).values(revoked_at=utc_now()))


@router.post("/users/search")
def search_users(data: TableQuery, auth: StaffAuth, db: SessionDep):
    require_admin(auth[0])
    query_filters(data, {"role", "active"})
    query = select(StaffAccount).join(User, User.id == StaffAccount.id)
    if data.search:
        query = query.where(StaffAccount.name.ilike(term(data.search), escape="\\") | User.email.ilike(term(data.search), escape="\\"))
    if data.filters.get("role"):
        query = query.where(StaffAccount.role == data.filters["role"])
    if data.filters.get("active"):
        query = query.where(StaffAccount.active.is_(data.filters["active"] == "true"))
    return paginate(db, query, StaffAccount, data, {"name": StaffAccount.name, "role": StaffAccount.role, "created_at": StaffAccount.name},
        lambda row: staff_wire(db, row))


@router.post("/users", status_code=201)
def create_user(data: StaffCreate, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    require_admin(staff)
    email = normalize_email(str(data.email))
    hashed = password_hash.hash(data.password.get_secret_value())
    def apply():
        # Existing driver identities are never promoted implicitly.
        if db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "This email already has an account")
        user = User(email=email, password_hash=hashed, display_name=data.name)
        db.add(user)
        db.flush()
        row = StaffAccount(id=user.id, name=data.name, role=data.role, totp_secret=b"", last_totp_counter=-1)
        db.add(row)
        db.flush()
        add_audit(db, staff, "staff_created", resource_id=row.id, after={"role": data.role, "name": data.name})
        return staff_wire(db, row)
    # The fingerprint must not contain the password.
    return write(db, staff_user(db, staff), request, key, {"email": email, "name": data.name, "role": data.role}, apply)


@router.patch("/users/{id}")
def update_user(id: UUID, data: StaffPatch, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    require_admin(staff)
    changes = data.model_dump(exclude_unset=True, exclude={"expected_version", "reason"})
    if not changes:
        raise HTTPException(422, "Nothing to change")
    def apply():
        row = db.get(StaffAccount, id, populate_existing=True)
        if not row:
            raise HTTPException(404, "Staff member not found")
        check_version(row, data.expected_version)
        before = staff_wire(db, row)
        removes_admin = row.role == "admin" and row.active and (changes.get("active") is False or changes.get("role", "admin") != "admin")
        if removes_admin:
            if row.id == staff.id:
                raise HTTPException(409, "You cannot remove your own administrator access")
            others = db.scalar(select(func.count()).select_from(StaffAccount).where(StaffAccount.role == "admin", StaffAccount.active.is_(True), StaffAccount.id != row.id))
            if not others:
                raise HTTPException(409, "At least one active administrator must remain")
        if changes.get("active") is False and row.id == staff.id:
            raise HTTPException(409, "You cannot deactivate your own account")
        leaves_accountant_work = row.role == "accountant" and (changes.get("active") is False or changes.get("role", "accountant") != "accountant")
        drivers = assigned_count(db, row.id)
        if leaves_accountant_work and drivers:
            # Otherwise those drivers would sit with someone who can no longer work on them.
            raise HTTPException(409, f"Move this accountant's {drivers} assigned driver(s) to another accountant first")
        for field, value in changes.items():
            setattr(row, field, value)
        row.version += 1
        if changes.get("active") is False or "role" in changes:
            end_sessions(db, row.id)
        db.flush()
        add_audit(db, staff, "staff_updated", resource_id=row.id, before=before, after={**staff_wire(db, row), "reason": data.reason})
        return staff_wire(db, row)
    return write(db, staff_user(db, staff), request, key, {**data.model_dump(mode="json"), "id": str(id)}, apply)


@router.post("/users/{id}/password")
def reset_staff_password(id: UUID, data: PasswordReset, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    """Set a new first password, for when someone is locked out and email recovery is not set up."""
    staff = auth[0]
    require_admin(staff)
    if id == staff.id:
        raise HTTPException(409, "Use password recovery to change your own password")
    hashed = password_hash.hash(data.password.get_secret_value())
    def apply():
        row = db.get(StaffAccount, id, populate_existing=True)
        if not row:
            raise HTTPException(404, "Staff member not found")
        check_version(row, data.expected_version)
        db.get(User, row.id).password_hash = hashed
        row.version += 1
        end_sessions(db, row.id)
        db.flush()
        add_audit(db, staff, "staff_password_reset", resource_id=row.id, after={"reason": data.reason})
        return staff_wire(db, row)
    # The fingerprint must not contain the password.
    return write(db, staff_user(db, staff), request, key, {"id": str(id), "expected_version": data.expected_version, "reason": data.reason}, apply)


# Admin overview ------------------------------------------------------------

def counts(db, column, query):
    return dict(db.execute(query.with_only_columns(column, func.count()).group_by(column)).all())


@router.post("/admin/overview")
def admin_overview(data: YearInput, auth: StaffAuth, db: SessionDep):
    """Practice-wide numbers for the admin console: people, work waiting and things only an admin can do."""
    staff = auth[0]
    require_admin(staff)
    tax_dates(data.tax_year)
    drivers = driver_scope(staff)
    assigned = select(DriverAssignment.driver_id)
    driver_total = db.scalar(select(func.count()).select_from(drivers.subquery()))
    unassigned = db.scalar(select(func.count()).select_from(drivers.where(~User.id.in_(assigned)).subquery()))
    staff_counts = dict(db.execute(select(StaffAccount.role, func.count()).where(StaffAccount.active.is_(True)).group_by(StaffAccount.role)).all())
    inactive = db.scalar(select(func.count()).select_from(StaffAccount).where(StaffAccount.active.is_(False)))
    open_handoff = (AccountantHandoff.status != "filed") & ((AccountantHandoff.tax_year == data.tax_year) | AccountantHandoff.tax_year.is_(None))
    handoffs = counts(db, AccountantHandoff.status, select(AccountantHandoff).where(AccountantHandoff.driver_id.in_(drivers), open_handoff))
    unassigned_handoffs = db.scalar(select(func.count()).select_from(AccountantHandoff).where(
        AccountantHandoff.driver_id.in_(drivers), open_handoff, ~AccountantHandoff.driver_id.in_(assigned)))
    returns = counts(db, TaxReturn.status, select(TaxReturn).where(TaxReturn.owner_id.in_(drivers), TaxReturn.tax_year == data.tax_year))
    privacy_open = PrivacyRequest.status.in_(["received", "in_progress"])
    privacy = {"open": db.scalar(select(func.count()).select_from(PrivacyRequest).where(privacy_open)),
        "overdue": db.scalar(select(func.count()).select_from(PrivacyRequest).where(privacy_open, PrivacyRequest.due_on < today()))}
    rates = counts(db, TaxRate.status, select(TaxRate).where(TaxRate.status.in_(["draft", "approved"])))
    ai_open = db.scalar(select(func.count()).select_from(Receipt).where(Receipt.owner_id.in_(drivers), extracted(),
        ~Receipt.id.in_(select(AiFeedback.receipt_id))))
    workload = []
    for row in db.scalars(select(StaffAccount).where(StaffAccount.role == "accountant").order_by(StaffAccount.active.desc(), StaffAccount.name)):
        theirs = select(DriverAssignment.driver_id).where(DriverAssignment.accountant_id == row.id)
        workload.append({"id": row.id, "name": row.name, "active": row.active, "assigned_drivers": assigned_count(db, row.id),
            "open_handoffs": db.scalar(select(func.count()).select_from(AccountantHandoff).where(AccountantHandoff.driver_id.in_(theirs), open_handoff)),
            "returns_in_progress": db.scalar(select(func.count()).select_from(TaxReturn).where(TaxReturn.owner_id.in_(theirs),
                TaxReturn.tax_year == data.tax_year, TaxReturn.status != "filed"))})
    due = deadlines(data.tax_year)[0]
    result = {"tax_year": data.tax_year, "as_of": utc_now(),
        "drivers": {"total": driver_total, "unassigned": unassigned},
        "staff": {"admins": staff_counts.get("admin", 0), "accountants": staff_counts.get("accountant", 0), "inactive": inactive},
        "handoffs": {"open": sum(handoffs.values()), "unassigned": unassigned_handoffs,
            **{status: handoffs.get(status, 0) for status in ("new", "in_review", "waiting_on_driver", "ready_to_file")}},
        "returns": {status: returns.get(status, 0) for status in ("in_preparation", "awaiting_driver", "driver_approved", "filed")},
        "privacy": privacy, "rates": {"draft": rates.get("draft", 0), "approved": rates.get("approved", 0)},
        "ai_reviews_open": ai_open, "deadline": {**due, "days_remaining": (due["due_on"] - today()).days},
        "workload": workload}
    add_audit(db, staff, "admin_overview_view")
    db.commit()
    return result


@router.post("/audit/search")
def audit_log(data: TableQuery, auth: StaffAuth, db: SessionDep):
    require_admin(auth[0])
    query_filters(data, {"action", "kind"})
    query = select(StaffAudit)
    if data.filters.get("kind") == "changes":
        query = query.where(~StaffAudit.action.like("%\\_view", escape="\\"), ~StaffAudit.action.in_(["login_succeeded", "logout", "receipt_view"]))
    if data.filters.get("action"):
        query = query.where(StaffAudit.action == data.filters["action"])
    if data.search:
        query = query.where(StaffAudit.action.ilike(term(data.search), escape="\\"))
    def serialize(row):
        actor = db.get(StaffAccount, row.actor_id)
        return {"id": row.id, "actor_name": actor.name if actor else "Unknown", "action": row.action, "driver_id": row.driver_id,
            "driver_name": driver_name(db, db.get(User, row.driver_id)) if row.driver_id else None,
            "resource_id": row.resource_id, "created_at": row.created_at, "before": row.before, "after": row.after}
    return paginate(db, query, StaffAudit, data, {"created_at": StaffAudit.created_at}, serialize)


# Tax rates -----------------------------------------------------------------

class RateInput(Body):
    tax_year: Year
    region: Literal["england_wales_ni", "scotland", "uk"]
    code: str = Field(min_length=1, max_length=32)
    value: dict
    official_url: str = Field(pattern=r"^https://[^\s]+$", max_length=500)
    reason: str = Field(min_length=3, max_length=500)


class RateAction(Versioned):
    reason: str = Field(min_length=3, max_length=500)


def required_keys(code):
    if code == "mtd_threshold":
        return {"threshold_pence", "mandation_tax_year"}
    if code == "vat":
        return {"threshold_pence"}
    return set(builtin_values("2026-27", "england_wales_ni")[code])


def validate_rate(data):
    if data.code not in (*RULE_CODES, *UK_SOURCES):
        raise HTTPException(422, "Unknown rate family")
    if (data.code in UK_SOURCES) != (data.region == "uk"):
        raise HTTPException(422, "MTD and VAT rates are UK-wide; other rates need a tax region")
    tax_dates(data.tax_year)
    missing = required_keys(data.code) - set(data.value)
    if missing:
        raise HTTPException(422, "Missing rate fields: " + ", ".join(sorted(missing)))
    pence_fields = [key for key in data.value if key.endswith("_pence")]
    if any(not isinstance(data.value[key], int) or isinstance(data.value[key], bool) or data.value[key] < 0 for key in pence_fields):
        raise HTTPException(422, "Pence fields must be whole, non-negative numbers")
    if data.code == "income":
        bands = data.value["bands"]
        if not isinstance(bands, list) or len(bands) < 2 or bands[-1][0] is not None or any(
                len(band) != 2 or not (band[0] is None or isinstance(band[0], int)) for band in bands):
            raise HTTPException(422, "Income bands must be [upper, rate] pairs ending with an open top band")
    if data.code in RULE_CODES:
        dry_run(data)


def dry_run(data):
    # A bad row would break every estimate in its year once active, so prove it computes first.
    region = data.region if data.region in REGIONS else "england_wales_ni"
    values = {**builtin_values("2026-27", region), data.code: data.value}
    rules = {"rules": [{"code": code, "value": value} for code, value in values.items()]}
    try:
        calculate(3000000, {"region": region, "employments": []}, data.tax_year, rules)
        calculate(13000000, {"region": region, "employments": []}, data.tax_year, rules)
        mileage_deduction(Decimal(12000), data.tax_year, rates=values["mileage"])
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "These values cannot be calculated; check the format of each rate") from None


def rate_wire(db, row):
    names = {id: db.get(StaffAccount, id).name for id in {row.created_by, row.approved_by} if id}
    return {**wire(row), "created_by_name": names.get(row.created_by), "approved_by_name": names.get(row.approved_by)}


@router.post("/rates/search")
def search_rates(data: TableQuery, auth: StaffAuth, db: SessionDep):
    require_admin(auth[0])
    query_filters(data, {"tax_year", "region", "status", "code"})
    query = select(TaxRate)
    for key in ("tax_year", "region", "status", "code"):
        if data.filters.get(key):
            query = query.where(getattr(TaxRate, key) == data.filters[key])
    return paginate(db, query, TaxRate, data, {"created_at": TaxRate.created_at, "tax_year": TaxRate.tax_year,
        "status": TaxRate.status, "code": TaxRate.code}, lambda row: rate_wire(db, row))


@router.post("/rates/effective")
def effective_rates(data: YearInput, auth: StaffAuth, db: SessionDep, region: str = "england_wales_ni"):
    require_admin(auth[0])
    try:
        return rule_set(data.tax_year, region, db)
    except HTTPException as error:
        if error.status_code != 422:
            raise
        return {"id": None, "tax_year": data.tax_year, "region": region, "version": None, "rules": [], "unavailable_reason": error.detail}


@router.post("/rates", status_code=201)
def draft_rate(data: RateInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    require_admin(staff)
    validate_rate(data)
    def apply():
        row = TaxRate(**data.model_dump(), created_by=staff.id)
        db.add(row)
        db.flush()
        add_audit(db, staff, "tax_rate_drafted", resource_id=row.id, after=wire(row))
        return rate_wire(db, row)
    return write(db, staff_user(db, staff), request, key, data.model_dump(mode="json"), apply)


def rate_transition(id, data, auth, db, request, key, target):
    staff = auth[0]
    require_admin(staff)
    def apply():
        row = db.get(TaxRate, id, populate_existing=True)
        if not row:
            raise HTTPException(404, "Rate not found")
        check_version(row, data.expected_version)
        before = wire(row)
        allowed = {"approved": "draft", "active": "approved", "retired": "active"}[target]
        if row.status != allowed:
            raise HTTPException(409, f"Only a {allowed} rate can move to {target}")
        if target == "approved":
            row.approved_by = staff.id
        if target == "active":
            # Exactly one active row per key; superseded rows stay as history.
            for current in db.scalars(select(TaxRate).where(TaxRate.tax_year == row.tax_year, TaxRate.region == row.region,
                    TaxRate.code == row.code, TaxRate.status == "active")):
                current.status = "retired"
                current.version += 1
            db.flush()
            row.activated_at = utc_now()
        row.status = target
        row.version += 1
        db.flush()
        add_audit(db, staff, "tax_rate_" + target, resource_id=row.id, before=before, after={**wire(row), "reason": data.reason})
        return rate_wire(db, row)
    return write(db, staff_user(db, staff), request, key, {**data.model_dump(), "id": str(id), "target": target}, apply)


@router.post("/rates/{id}/approve")
def approve_rate(id: UUID, data: RateAction, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    return rate_transition(id, data, auth, db, request, key, "approved")


@router.post("/rates/{id}/activate")
def activate_rate(id: UUID, data: RateAction, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    return rate_transition(id, data, auth, db, request, key, "active")


@router.post("/rates/{id}/retire")
def retire_rate(id: UUID, data: RateAction, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    return rate_transition(id, data, auth, db, request, key, "retired")


# Privacy requests ----------------------------------------------------------

class PrivacyInput(Body):
    kind: Literal["export", "access", "correction", "deletion"]
    detail: str | None = Field(default=None, max_length=2000)


class StaffPrivacyInput(PrivacyInput):
    driver_id: UUID


class PrivacyPatch(Versioned):
    status: Literal["in_progress", "completed", "rejected"]
    resolution: str = Field(min_length=3, max_length=2000)


class DeletionInput(Versioned):
    confirm_driver_name: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=3, max_length=2000)


def privacy_wire(db, row):
    driver = db.get(User, row.owner_id)
    handler = db.get(StaffAccount, row.handled_by) if row.handled_by else None
    return {**wire(row), "driver_id": row.owner_id, "driver_name": driver_name(db, driver), "driver_email": driver.email,
        "handled_by_name": handler.name if handler else None, "overdue": row.status in {"received", "in_progress"} and row.due_on < today()}


def new_privacy_request(db, owner, data):
    # UK GDPR: respond within one calendar month of receipt.
    return PrivacyRequest(owner_id=owner, kind=data.kind, detail=data.detail, due_on=today() + timedelta(days=30))


def retention_date(db, owner):
    """Tax records stay at least five years after the 31 January filing deadline."""
    from app.services.books import tax_year as year_of
    latest = db.scalar(select(func.max(Transaction.occurred_on)).where(Transaction.owner_id == owner)) or today()
    _, end = tax_dates(year_of(latest))
    return end.replace(year=end.year + 1 + RETENTION_YEARS, month=1, day=31)


@router.post("/privacy-requests/search")
def privacy_requests(data: TableQuery, auth: StaffAuth, db: SessionDep):
    require_admin(auth[0])
    query_filters(data, {"status", "kind"})
    query = select(PrivacyRequest)
    for key in ("status", "kind"):
        if data.filters.get(key):
            query = query.where(getattr(PrivacyRequest, key) == data.filters[key])
    return paginate(db, query, PrivacyRequest, data, {"created_at": PrivacyRequest.created_at, "due_on": PrivacyRequest.due_on,
        "status": PrivacyRequest.status}, lambda row: privacy_wire(db, row))


@router.post("/privacy-requests", status_code=201)
def staff_privacy_request(data: StaffPrivacyInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    require_admin(staff)
    user = require_driver(db, staff, data.driver_id)
    def apply():
        row = new_privacy_request(db, data.driver_id, data)
        db.add(row)
        db.flush()
        history(db, row, "privacy_request", None, data.detail)
        add_audit(db, staff, "privacy_request_logged", data.driver_id, row.id, after={"kind": data.kind})
        return privacy_wire(db, row)
    return write(db, user, request, key, {**data.model_dump(mode="json"), "staff_id": str(staff.id)}, apply)


@router.patch("/privacy-requests/{id}")
def update_privacy_request(id: UUID, data: PrivacyPatch, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    require_admin(staff)
    def apply():
        row = db.get(PrivacyRequest, id, populate_existing=True)
        if not row:
            raise HTTPException(404, "Request not found")
        check_version(row, data.expected_version)
        if row.status in {"completed", "rejected"}:
            raise HTTPException(409, "This request is closed")
        if row.kind == "deletion" and data.status == "completed":
            raise HTTPException(409, "Complete a deletion request with the deletion action")
        before = wire(row)
        row.status, row.resolution, row.handled_by = data.status, data.resolution, staff.id
        row.completed_at = utc_now() if data.status in {"completed", "rejected"} else None
        row.version += 1
        history(db, row, "privacy_update", before, data.resolution)
        add_audit(db, staff, "privacy_request_updated", row.owner_id, row.id, after={"status": data.status})
        return privacy_wire(db, row)
    return write(db, staff_user(db, staff), request, key, {**data.model_dump(), "id": str(id)}, apply)


@router.post("/privacy-requests/{id}/execute-deletion")
def execute_deletion(id: UUID, data: DeletionInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    """Erase personal data at once; tax records and filing evidence stay locked until retain_until."""
    staff = auth[0]
    require_admin(staff)
    def apply():
        row = db.get(PrivacyRequest, id, populate_existing=True)
        if not row or row.kind != "deletion":
            raise HTTPException(404, "Deletion request not found")
        check_version(row, data.expected_version)
        if row.status in {"completed", "rejected"}:
            raise HTTPException(409, "This request is closed")
        user = db.get(User, row.owner_id)
        name = driver_name(db, user)
        if data.confirm_driver_name.strip().casefold() != name.casefold():
            raise HTTPException(422, "Type the driver's name exactly to confirm deletion")
        owner = row.owner_id
        for kind in ("me", "driver", "trade", "accountant_access"):
            item = profile(db, owner, kind)
            if item:
                item.data = {}
                item.identifiers = None
                item.version += 1
        for record in db.scalars(rows(db, SupportRecord, owner).where(SupportRecord.kind.in_(["conversation", "message"]))):
            db.delete(record)
        for record in db.scalars(rows(db, Notification, owner)):
            db.delete(record)
        for record in db.scalars(rows(db, PhoneIdentity, owner)):
            db.delete(record)
        for record in db.scalars(select(ExternalIdentity).where(ExternalIdentity.user_id == owner)):
            db.delete(record)
        assignment = db.get(DriverAssignment, owner)
        if assignment:
            db.delete(assignment)
        db.execute(update(DeviceSession).where(DeviceSession.user_id == owner, DeviceSession.revoked_at.is_(None)).values(revoked_at=utc_now()))
        user.email, user.display_name = None, None
        user.password_hash = password_hash.hash(secrets.token_urlsafe(48))
        row.status, row.resolution, row.handled_by, row.completed_at = "completed", data.reason, staff.id, utc_now()
        row.retain_until = retention_date(db, owner)
        row.version += 1
        db.flush()
        add_audit(db, staff, "personal_data_deleted", owner, row.id, after={"retain_until": row.retain_until, "reason": data.reason})
        return privacy_wire(db, row)
    return write(db, staff_user(db, staff), request, key, {**data.model_dump(), "id": str(id)}, apply)


@driver_router.post("/me/privacy-requests", status_code=201)
def my_privacy_request(data: PrivacyInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        open_request = db.scalar(rows(db, PrivacyRequest, user.id).where(PrivacyRequest.kind == data.kind, PrivacyRequest.status.in_(["received", "in_progress"])))
        if open_request:
            raise HTTPException(409, "You already have an open request of this kind")
        row = new_privacy_request(db, user.id, data)
        db.add(row)
        history(db, row, "privacy_request", None, data.detail)
        return {**wire(row), "notice": "Tax records and filing evidence must be kept for at least five years after the filing deadline, then they are deleted."}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@driver_router.get("/me/privacy-requests")
def my_privacy_requests(user: CurrentUser, db: SessionDep):
    return {"items": [wire(row) for row in db.scalars(rows(db, PrivacyRequest, user.id).order_by(PrivacyRequest.created_at.desc()))]}
