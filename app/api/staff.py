"""Accountant access is explicit; driver owner endpoints keep their contracts."""
import csv
import io
from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from sqlalchemy import String, func, literal, select, union_all

from app.api import documents, reports, support
from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.profiles import Key
from app.core.security import DUMMY_HASH, password_hash
from app.models import DeviceSession, User
from app.models.books import Job, Mileage, Mutation, PrivateFile, Profile, Receipt, SupportRecord, Transaction
from app.models.common import utc_now
from app.models.staff import AccountantHandoff, DriverAssignment, StaffAccount, StaffAudit, StaffEntry, StaffView
from app.schemas.books import Confirmation, ReceiptPatch, Reversal, TransactionPatch
from app.schemas.staff import (AssignmentInput, EntryInput, ExportInput, HandoffPatch, RevealInput,
    ReviewInput, StaffLogin, StaffLoginResult, TableQuery, ViewInput, ViewSearch, YearInput)
from app.services.auth_security import rate_limit
from app.services.books import (CATEGORIES, SOURCES, check_version, history, owned, profile, rows,
    tax_dates, tax_year, wire, write)
from app.services.files import receipt_wire, store_file
from app.services.ledger import mileage_total, update_transaction
from app.services.sessions import lock_user
from app.services.staff import (IDLE_SECONDS, StaffAuth, add_audit, driver_scope,
    driver_search, driver_summary, identity, paginate, query_filters, require_driver, staff_token)
from app.services.tax import deadlines, estimate, payment_timeline, rule_set, today
from app.services.vault import decrypt

router = APIRouter(prefix="/staff", tags=["staff accountant panel"])
driver_router = APIRouter(tags=["human accountant messages"])


@router.post("/auth/login", response_model=StaffLoginResult)
def login(data: StaffLogin, db: SessionDep, settings: SettingsDep, request: Request):
    email = str(data.email).strip().lower()
    rate_limit(db, settings, request, "staff_login", email, target_limit=5)
    user = db.scalar(select(User).where(User.email == email))
    if user:
        lock_user(db, user.id)
        db.refresh(user)
    staff = db.get(StaffAccount, user.id, populate_existing=True) if user else None
    valid = password_hash.verify(data.password.get_secret_value(), user.password_hash if user else DUMMY_HASH)
    if not valid or not staff or not staff.active:
        raise HTTPException(401, "Invalid staff credentials")
    device = DeviceSession(user_id=staff.id, device_name="Accountant web panel", last_used_at=utc_now(),
        expires_at=utc_now() + timedelta(minutes=settings.access_token_expire_minutes))
    db.add(device)
    db.flush()
    token = staff_token(staff, device, settings)
    add_audit(db, staff, "login_succeeded")
    db.commit()
    return {"access_token": token, "expires_in": settings.access_token_expire_minutes * 60,
            "staff": identity(db, staff)}


@router.post("/auth/logout", status_code=204)
def logout(auth: StaffAuth, db: SessionDep):
    staff, device = auth
    lock_user(db, staff.id)
    db.refresh(device)
    device.revoked_at = utc_now()
    add_audit(db, staff, "logout")
    db.commit()


@router.get("/me")
def me(auth: StaffAuth, db: SessionDep):
    return identity(db, auth[0])


@router.get("/config")
def config(auth: StaffAuth, settings: SettingsDep):
    # The verified registry is authoritative; unsupported years are not offered.
    years = ["2025-26", "2026-27"]
    return {"tax_years": [rule_set(year, "england_wales_ni")["tax_year"] for year in years],
        "current_tax_year": tax_year(today()), "idle_timeout_seconds": IDLE_SECONDS,
        "upload_max_bytes": settings.upload_max_bytes,
        "categories": list(CATEGORIES.values()), "sources": list(SOURCES.values())}


def audit_read(db, staff, action, driver_id=None, after=None):
    add_audit(db, staff, action, driver_id, after=after)
    db.commit()


def handoff_wire(db, row):
    request = db.get(SupportRecord, row.id)
    driver = db.get(User, row.driver_id)
    summary = driver_summary(db, driver)
    return {**wire(row), "driver_name": summary["name"], "driver_email": summary["email"],
        "accountant_id": summary["accountant_id"], "accountant_name": summary["accountant_name"],
        "tax_year": row.tax_year, "request_type": request.data["kind"],
        "created_at": request.created_at, "age_days": (utc_now() - request.created_at).days,
        "workflow_events": audit_projection(db, row.driver_id, row.id)}


def audit_projection(db, driver_id, resource_id):
    records = db.execute(select(StaffAudit, StaffAccount.name).join(StaffAccount,
        StaffAccount.id == StaffAudit.actor_id).where(StaffAudit.driver_id == driver_id,
        StaffAudit.resource_id == resource_id).order_by(StaffAudit.created_at.desc(), StaffAudit.id).limit(50))
    return [{"id": event.id, "actor_name": name, "action": event.action,
        "created_at": event.created_at, "before": event.before, "after": event.after} for event, name in records]


def review_projection(db, driver_id, resource_id):
    # A later correction/reversal must not inherit a previous reviewer's name.
    records = db.execute(select(StaffAudit, StaffAccount.name).join(StaffAccount,
        StaffAccount.id == StaffAudit.actor_id).where(StaffAudit.driver_id == driver_id,
        (StaffAudit.resource_id == resource_id) | (StaffAudit.before["id"].astext == str(resource_id)),
        StaffAudit.action.in_(["receipt_approve", "receipt_reject", "receipt_confirmation_reversed", "receipt_fields_corrected", "expense_corrected"]))
        .order_by(StaffAudit.created_at.desc(), StaffAudit.id).limit(1)).first()
    if not records or records[0].action not in {"receipt_approve", "receipt_reject"}:
        return {"reviewed_by": None, "reviewed_at": None}
    return {"reviewed_by": records[1], "reviewed_at": records[0].created_at}


def filtered_drivers(db, staff, data, settings):
    query = driver_search(db, staff, data.search)
    if data.search.strip().isdigit():
        candidates = list(db.scalars(query.limit(1001)))
        if len(candidates) > 1000:
            raise HTTPException(422, "Narrow this search through the assigned-driver list")
        matches = []
        for candidate in candidates:
            tax_profiles = db.scalars(rows(db, Profile, candidate.id).where(Profile.kind == "tax"))
            if any(p.identifiers and decrypt(settings, p.identifiers).get("utr") == data.search.strip() for p in tax_profiles):
                matches.append(candidate.id)
        query = query.where(User.id.in_(matches))
    return query


def global_table(db, staff, resource, data, settings):
    if resource == "drivers":
        query_filters(data, {"accountant_id"})
        query = filtered_drivers(db, staff, data, settings)
        if data.filters.get("accountant_id"):
            query = query.where(User.id.in_(select(DriverAssignment.driver_id).where(
                DriverAssignment.accountant_id == UUID(data.filters["accountant_id"]))))
        actual_name = select(func.concat(Profile.data["first_name"].astext, " ", Profile.data["last_name"].astext)).where(
            Profile.owner_id == User.id, Profile.kind == "me", Profile.scope == "").scalar_subquery()
        return paginate(db, query, User, data, {"created_at": User.created_at, "name": func.coalesce(actual_name, User.display_name),
            "email": User.email}, lambda row: driver_summary(db, row))
    if resource == "handoffs":
        query_filters(data, {"status", "tax_year", "accountant_id"})
        query = select(AccountantHandoff).join(SupportRecord, SupportRecord.id == AccountantHandoff.id).where(
            AccountantHandoff.driver_id.in_(filtered_drivers(db, staff, data, settings).with_only_columns(User.id)))
        for key in ("status", "tax_year"):
            if data.filters.get(key):
                column = AccountantHandoff.status if key == "status" else AccountantHandoff.tax_year
                query = query.where((column == data.filters[key]) | column.is_(None) if key == "tax_year" else column == data.filters[key])
        if data.filters.get("accountant_id"):
            query = query.where(AccountantHandoff.driver_id.in_(select(DriverAssignment.driver_id).where(
                DriverAssignment.accountant_id == UUID(data.filters["accountant_id"]))))
        return paginate(db, query, AccountantHandoff, data,
            {"created_at": SupportRecord.created_at, "status": AccountantHandoff.status,
             "tax_year": AccountantHandoff.tax_year}, lambda row: handoff_wire(db, row))
    raise HTTPException(404, "Resource not supported")


@router.post("/drivers/search")
def drivers(data: TableQuery, auth: StaffAuth, db: SessionDep, settings: SettingsDep):
    result = global_table(db, auth[0], "drivers", data, settings)
    for row in result["items"]:
        add_audit(db, auth[0], "driver_list_view", row["id"])
    db.commit()
    return result


@router.post("/handoffs/search")
def handoffs(data: TableQuery, auth: StaffAuth, db: SessionDep, settings: SettingsDep):
    result = global_table(db, auth[0], "handoffs", data, settings)
    audit_read(db, auth[0], "handoff_queue_view", after={"count": len(result["items"])})
    return result


@router.post("/accountants/search")
def accountants(data: TableQuery, auth: StaffAuth, db: SessionDep):
    staff = auth[0]
    if staff.role not in {"admin", "senior_accountant"}:
        raise HTTPException(403, "Reassignment requires a senior accountant or admin")
    query = select(StaffAccount).where(StaffAccount.active.is_(True), StaffAccount.role.in_(["accountant", "senior_accountant"]))
    if staff.role != "admin":
        query = query.where(StaffAccount.team_id == staff.team_id, StaffAccount.team_id.is_not(None))
    if data.search:
        query = query.where(StaffAccount.name.ilike("%" + data.search.replace("%", "\\%") + "%"))
    query_filters(data, set())
    return paginate(db, query, StaffAccount, data, {"name": StaffAccount.name, "created_at": StaffAccount.name},
        lambda row: identity(db, row))


@router.post("/handoffs/assign")
def assign(data: AssignmentInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    if staff.role not in {"admin", "senior_accountant"}:
        raise HTTPException(403, "Reassignment requires a senior accountant or admin")
    target = db.get(StaffAccount, data.accountant_id)
    if not target or not target.active or target.role not in {"accountant", "senior_accountant"}:
        raise HTTPException(422, "Select an active accountant")
    if staff.role != "admin" and (not staff.team_id or target.team_id != staff.team_id):
        raise HTTPException(403, "Target accountant must be in your team")
    def apply():
        selected = list(db.scalars(select(AccountantHandoff).where(AccountantHandoff.id.in_(data.ids)).order_by(AccountantHandoff.driver_id)))
        if len(selected) != len(set(data.ids)):
            raise HTTPException(404, "Handoff not found")
        for row in selected:
            lock_user(db, row.driver_id)
            require_driver(db, staff, row.driver_id)
            db.refresh(row)
            check_version(row, data.versions.get(str(row.id)))
        for driver_id in sorted({row.driver_id for row in selected}):
            row = next(item for item in selected if item.driver_id == driver_id)
            assignment = db.get(DriverAssignment, row.driver_id, populate_existing=True)
            before = {"accountant_id": str(assignment.accountant_id) if assignment else None}
            if not assignment:
                db.add(DriverAssignment(driver_id=row.driver_id, accountant_id=target.id))
            else:
                assignment.accountant_id = target.id
                assignment.version += 1
            # Every affected handoff changes version because assignment is shown there.
            for affected in db.scalars(select(AccountantHandoff).where(AccountantHandoff.driver_id == row.driver_id)):
                affected.version += 1
            add_audit(db, staff, "driver_reassigned", row.driver_id, row.id, before,
                {"accountant_id": str(target.id), "reason": data.reason})
        db.flush()
        return {"items": [handoff_wire(db, row) for row in selected]}
    return write(db, db.get(User, staff.id), request, key, data.model_dump(mode="json"), apply)


@router.patch("/handoffs/{id}")
def update_handoff(id: UUID, data: HandoffPatch, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    staff = auth[0]
    def apply():
        row = db.get(AccountantHandoff, id)
        if not row:
            raise HTTPException(404, "Handoff not found")
        lock_user(db, row.driver_id)
        require_driver(db, staff, row.driver_id, write=True)
        db.refresh(row)
        check_version(row, data.expected_version)
        if (data.status == "filed" or row.status == "filed") and staff.role not in {"admin", "senior_accountant"}:
            raise HTTPException(403, "Filing sign-off requires a senior accountant")
        if data.status == "filed" and (row.status != "ready_to_file" or not data.filing_reference):
            raise HTTPException(422, "Ready-to-file review and actual external filing reference required")
        before = wire(row)
        row.status, row.filing_reference = data.status, data.filing_reference
        row.version += 1
        db.flush()
        add_audit(db, staff, "handoff_updated", row.driver_id, row.id, before, {**wire(row), "reason": data.reason})
        return handoff_wire(db, row)
    return write(db, db.get(User, staff.id), request, key, data.model_dump(mode="json"), apply)


@router.post("/dashboard")
def dashboard(data: YearInput, auth: StaffAuth, db: SessionDep):
    staff = auth[0]
    tax_dates(data.tax_year)
    queue = list(db.scalars(select(AccountantHandoff).join(SupportRecord, AccountantHandoff.id == SupportRecord.id).where(
        AccountantHandoff.driver_id.in_(driver_scope(staff)),
        (AccountantHandoff.tax_year == data.tax_year) | AccountantHandoff.tax_year.is_(None))))
    due = deadlines(data.tax_year)[0]
    days = (due["due_on"] - today()).days
    workload = [{"id": status, "status": status, "count": sum(row.status == status for row in queue)} for status in
        ("new", "in_review", "waiting_on_driver", "ready_to_file", "filed")]
    result = {"assigned_drivers": db.scalar(select(func.count()).select_from(driver_scope(staff).subquery())),
        "pending_handoffs": sum(row.status != "filed" for row in queue),
        "due_soon": sum(row.status != "filed" and row.tax_year is not None for row in queue) if 0 <= days <= 30 else 0,
        "overdue": sum(row.status != "filed" and row.tax_year is not None for row in queue) if days < 0 else 0,
        "year_not_supplied": sum(row.tax_year is None for row in queue),
        "deadline": {**due, "days_remaining": days}, "workload": workload, "as_of": utc_now()}
    audit_read(db, staff, "dashboard_view")
    return result


@router.post("/drivers/{driver_id}/overview")
def overview(driver_id: UUID, data: YearInput, auth: StaffAuth, db: SessionDep):
    user = require_driver(db, auth[0], driver_id)
    lock_user(db, driver_id)
    tax_dates(data.tax_year)
    tax = profile(db, driver_id, "tax", data.tax_year)
    driver = profile(db, driver_id, "driver")
    result = {**driver_summary(db, user), "tax_year": data.tax_year,
        "utr_masked": tax.data.get("utr_masked") if tax else None,
        "ni_masked": tax.data.get("ni_masked") if tax else None,
        "driver_profile": driver.data if driver else {}, "subscription": support.subscription(user, db),
        "totals": reports.dashboard_response(db, driver_id, data.tax_year),
        "handoffs": [handoff_wire(db, item) for item in db.scalars(select(AccountantHandoff).where(
            AccountantHandoff.driver_id == driver_id,
            (AccountantHandoff.tax_year == data.tax_year) | AccountantHandoff.tax_year.is_(None)).order_by(AccountantHandoff.id))]}
    audit_read(db, auth[0], "financial_overview_view", driver_id)
    return result


def driver_table(db, staff, driver_id, resource, data):
    require_driver(db, staff, driver_id)
    allowed = {"income": {"tax_year", "review_status", "claim_status", "source_id"},
        "expenses": {"tax_year", "review_status", "claim_status", "category_id"},
        "receipts": {"tax_year", "review_status", "claim_status"}, "mileage": {"tax_year", "vehicle_id"},
        "documents": {"scan_status", "mime_type"}, "messages": set(), "notes": {"kind"}, "activity": {"action", "resource_id"}}
    if resource not in allowed:
        raise HTTPException(404, "Unsupported driver resource")
    query_filters(data, allowed[resource])
    year = data.filters.get("tax_year")
    start, end = tax_dates(year) if year else (None, None)
    if resource in {"income", "expenses"}:
        if not year:
            raise HTTPException(422, "Select a tax year")
        query = rows(db, Transaction, driver_id).where(Transaction.kind == ("income" if resource == "income" else "expense"),
            Transaction.occurred_on.between(start, end))
        for field in ("review_status", "claim_status", "category_id", "source_id"):
            if data.filters.get(field):
                value = UUID(data.filters[field]) if field.endswith("_id") else data.filters[field]
                query = query.where(getattr(Transaction, field) == value)
        if data.search:
            query = query.where(Transaction.description.ilike("%" + data.search.replace("%", "\\%") + "%"))
        def serialize(row):
            receipt = db.get(Receipt, row.receipt_id) if row.receipt_id else None
            extraction = receipt.extraction or {} if receipt else {}
            category = CATEGORIES.get(row.category_id, {})
            return {**wire(row), "category_name": category.get("code", "Uncategorised").replace("_", " ").title(),
                "source_name": SOURCES.get(row.source_id, {}).get("name"),
            "ai_category": extraction.get("suggested_category_id"), "ai_confidence": extraction.get("confidence"),
                "ai_reason": extraction.get("warnings", []), "receipt_version": receipt.version if receipt else None,
                **review_projection(db, driver_id, row.receipt_id or row.id)}
        return paginate(db, query, Transaction, data, {"created_at": Transaction.created_at,
            "occurred_on": Transaction.occurred_on, "amount_pence": Transaction.amount_pence,
            "review_status": Transaction.review_status}, serialize)
    if resource == "mileage":
        if not year:
            raise HTTPException(422, "Select a tax year")
        query = rows(db, Mileage, driver_id).where(Mileage.occurred_on.between(start, end), Mileage.active.is_(True))
        if data.filters.get("vehicle_id"):
            query = query.where(Mileage.vehicle_id == UUID(data.filters["vehicle_id"]))
        if data.search:
            query = query.where(Mileage.purpose.ilike("%" + data.search.replace("%", "\\%") + "%"))
        result = paginate(db, query, Mileage, data, {"created_at": Mileage.created_at,
            "occurred_on": Mileage.occurred_on, "business_miles": Mileage.business_miles})
        return {**result, "summary": mileage_total(db, driver_id, year)}
    if resource == "documents":
        query = rows(db, PrivateFile, driver_id)
        for field in ("scan_status", "mime_type"):
            if data.filters.get(field):
                query = query.where(getattr(PrivateFile, field) == data.filters[field])
        if data.search:
            term = "%" + data.search.replace("%", "\\%") + "%"
            query = query.where(PrivateFile.mime_type.ilike(term) | PrivateFile.scan_status.ilike(term))
        return paginate(db, query, PrivateFile, data, {"created_at": PrivateFile.created_at, "size_bytes": PrivateFile.size_bytes},
            lambda row: {"id": row.id, "mime_type": row.mime_type, "size_bytes": row.size_bytes,
                "scan_status": row.scan_status, "created_at": row.created_at})
    if resource == "receipts":
        query = rows(db, Receipt, driver_id)
        if year:
            value = func.coalesce(Receipt.reviewed["occurred_on"].astext, Receipt.extraction["occurred_on"].astext)
            query = query.where(value.is_(None) | value.between(str(start), str(end)))
        if data.filters.get("review_status"):
            query = query.where(Receipt.review_status == data.filters["review_status"])
        if data.filters.get("claim_status"):
            query = query.where(Receipt.claim_status == data.filters["claim_status"])
        if data.search:
            merchant = func.coalesce(Receipt.reviewed["merchant"].astext, Receipt.extraction["merchant"].astext)
            query = query.where(merchant.ilike("%" + data.search.replace("%", "\\%") + "%"))
        return paginate(db, query, Receipt, data, {"created_at": Receipt.created_at, "review_status": Receipt.review_status},
            lambda row: receipt_wire(db, row))
    if resource in {"messages", "notes"}:
        query = select(StaffEntry).where(StaffEntry.driver_id == driver_id,
            StaffEntry.kind == "message" if resource == "messages" else StaffEntry.kind.in_(["note", "ticket"]))
        if data.filters.get("kind"):
            query = query.where(StaffEntry.kind == data.filters["kind"])
        if data.search:
            query = query.where(StaffEntry.body.ilike("%" + data.search.replace("%", "\\%") + "%"))
        return paginate(db, query, StaffEntry, data, {"created_at": StaffEntry.created_at},
            lambda row: {**wire(row), "author": db.get(StaffAccount, row.staff_id).name if row.staff_id else "Driver"})
    if resource == "activity":
        staff_events = select(StaffAudit.id, StaffAudit.created_at, StaffAudit.action, StaffAudit.before,
            func.coalesce(StaffAudit.resource_id.cast(String), StaffAudit.before["id"].astext).label("resource_id"),
            StaffAudit.after, StaffAccount.name.label("actor_name")).join(StaffAccount, StaffAccount.id == StaffAudit.actor_id).where(StaffAudit.driver_id == driver_id)
        book_events = select(Mutation.id, Mutation.created_at, Mutation.action, Mutation.before,
            Mutation.resource_id.cast(String).label("resource_id"), Mutation.after,
            literal("Driver/service — legacy actor not recorded").label("actor_name")).where(Mutation.owner_id == driver_id)
        events = union_all(staff_events, book_events).subquery()
        query = select(events)
        if data.filters.get("action"):
            query = query.where(events.c.action == data.filters["action"])
        if data.filters.get("resource_id"):
            query = query.where(events.c.resource_id == data.filters["resource_id"])
        if data.search:
            query = query.where(events.c.action.ilike("%" + data.search.replace("%", "\\%") + "%"))
        if data.sort != "created_at":
            raise HTTPException(422, "Unsupported activity sort field")
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        ordering = events.c.created_at.desc() if data.order == "desc" else events.c.created_at.asc()
        records = db.execute(query.order_by(ordering, events.c.id).offset((data.page - 1) * data.page_size).limit(data.page_size)).mappings()
        return {"items": [dict(row) for row in records], "total": total, "page": data.page, "page_size": data.page_size}
    raise HTTPException(404, "Unsupported driver resource")


@router.post("/drivers/{driver_id}/{resource}/search")
def driver_resource(driver_id: UUID, resource: str, data: TableQuery, auth: StaffAuth, db: SessionDep):
    result = driver_table(db, auth[0], driver_id, resource, data)
    audit_read(db, auth[0], resource + "_view", driver_id,
        {"ids": [str(row["id"]) for row in result["items"]]})
    return result


@router.post("/drivers/{driver_id}/tax")
def tax(driver_id: UUID, data: YearInput, auth: StaffAuth, db: SessionDep):
    require_driver(db, auth[0], driver_id)
    lock_user(db, driver_id)
    context = profile(db, driver_id, "tax", data.tax_year)
    rules = rule_set(data.tax_year, context.data["region"] if context else "england_wales_ni")
    try:
        calculation = estimate(db, driver_id, data.tax_year)
    except HTTPException as error:
        if error.status_code not in {404, 409, 422}:
            raise
        calculation = {"available": False, "reason": error.detail}
    safe_inputs = ("region", "has_paye_job", "property_income_pence", "interest_pence", "class4_exempt",
        "student_loan_plan", "marriage_allowance_status", "marriage_allowance_eligible")
    calculation_context = {key: context.data[key] for key in safe_inputs if context and key in context.data}
    if context:
        calculation_context["employments"] = [{key: item[key] for key in
            ("gross_annual_pay_pence", "tax_paid_pence", "student_loan_paid_pence") if key in item}
            for item in context.data.get("employments", [])]
    result = {"estimate": calculation, "payments": payment_timeline(db, driver_id, data.tax_year),
        "rules": rules, "calculation_context": calculation_context}
    audit_read(db, auth[0], "tax_view", driver_id)
    return result


@router.post("/drivers/{driver_id}/identifiers/reveal")
def reveal(driver_id: UUID, data: RevealInput, auth: StaffAuth, db: SessionDep, settings: SettingsDep):
    staff = auth[0]
    require_driver(db, staff, driver_id, write=True)
    item = profile(db, driver_id, "tax", data.tax_year)
    values = decrypt(settings, item.identifiers) if item and item.identifiers else {}
    if not values.get(data.field):
        raise HTTPException(404, "Identifier not provided")
    audit_read(db, staff, "identifier_revealed", driver_id,
        {"field": data.field, "tax_year": data.tax_year, "reason": data.reason})
    return {"value": values[data.field], "expires_in": 30}


def financial_context(db, auth, request, driver_id, before, action):
    staff = auth[0]
    lock_user(db, driver_id)
    user = require_driver(db, staff, driver_id, write=True)
    request.state.staff_audit = {"staff": staff, "driver_id": driver_id, "before": before, "action": action}
    return user


@router.patch("/drivers/{driver_id}/expenses/{expense_id}")
def edit_expense(driver_id: UUID, expense_id: UUID, data: TransactionPatch, auth: StaffAuth,
                 db: SessionDep, request: Request, key: Key):
    require_driver(db, auth[0], driver_id, write=True)
    lock_user(db, driver_id)
    row = owned(db, Transaction, driver_id, expense_id)
    if row.kind != "expense":
        raise HTTPException(404, "Expense not found")
    user = financial_context(db, auth, request, driver_id, wire(row), "expense_corrected")
    return write(db, user, request, key, data.model_dump(mode="json"), lambda: wire(update_transaction(db, row, data)))


@router.get("/drivers/{driver_id}/receipts/{receipt_id}")
def receipt(driver_id: UUID, receipt_id: UUID, auth: StaffAuth, db: SessionDep):
    require_driver(db, auth[0], driver_id)
    row = owned(db, Receipt, driver_id, receipt_id)
    result = receipt_wire(db, row)
    file = owned(db, PrivateFile, driver_id, row.file_id)
    result.update({"file_id": file.id, "scan_status": file.scan_status, "mime_type": file.mime_type})
    result.update(review_projection(db, driver_id, row.id))
    audit_read(db, auth[0], "receipt_view", driver_id, {"receipt_id": str(receipt_id)})
    return result


@router.post("/drivers/{driver_id}/receipts/{receipt_id}/review")
def receipt_review(driver_id: UUID, receipt_id: UUID, data: ReviewInput, auth: StaffAuth,
                   db: SessionDep, request: Request, key: Key):
    require_driver(db, auth[0], driver_id, write=True)
    lock_user(db, driver_id)
    row = owned(db, Receipt, driver_id, receipt_id)
    user = financial_context(db, auth, request, driver_id, receipt_wire(db, row), "receipt_" + data.decision)
    request.state.staff_audit["reason"] = data.reason
    return documents.confirm(receipt_id, Confirmation(expected_version=data.expected_version,
        category_id=data.category_id, business_use_percent=data.business_use_percent,
        claim_status="claimable" if data.decision == "approve" else "excluded"), user, db, request, key)


@router.post("/drivers/{driver_id}/receipts/{receipt_id}/reversals")
def receipt_reversal(driver_id: UUID, receipt_id: UUID, data: Reversal, auth: StaffAuth,
                     db: SessionDep, request: Request, key: Key):
    require_driver(db, auth[0], driver_id, write=True)
    lock_user(db, driver_id)
    row = owned(db, Receipt, driver_id, receipt_id)
    user = financial_context(db, auth, request, driver_id, receipt_wire(db, row), "receipt_confirmation_reversed")
    request.state.staff_audit["reason"] = data.reason
    return documents.reverse_receipt(receipt_id, data, user, db, request, key)


@router.patch("/drivers/{driver_id}/receipts/{receipt_id}")
def edit_receipt(driver_id: UUID, receipt_id: UUID, data: ReceiptPatch, auth: StaffAuth,
                 db: SessionDep, request: Request, key: Key):
    require_driver(db, auth[0], driver_id, write=True)
    lock_user(db, driver_id)
    row = owned(db, Receipt, driver_id, receipt_id)
    user = financial_context(db, auth, request, driver_id, receipt_wire(db, row), "receipt_fields_corrected")
    return documents.review(receipt_id, data, user, db, request, key)


@router.post("/drivers/{driver_id}/documents", status_code=201)
def upload_document(driver_id: UUID, file: Annotated[UploadFile, File()], auth: StaffAuth,
                    db: SessionDep, settings: SettingsDep, request: Request, key: Key):
    require_driver(db, auth[0], driver_id, write=True)
    content, mime = documents.upload_content(file, settings, "receipt")
    def apply():
        require_driver(db, auth[0], driver_id, write=True)
        stored = store_file(db, driver_id, content, mime)
        db.add(Job(owner_id=driver_id, kind="private_scan", resource_id=stored.id))
        add_audit(db, auth[0], "document_uploaded", driver_id, stored.id,
            after={"mime_type": mime, "size_bytes": len(content), "scan_status": stored.scan_status})
        return {"id": stored.id, "scan_status": stored.scan_status, "mime_type": mime, "size_bytes": len(content)}
    import hashlib
    return write(db, db.get(User, driver_id), request, key, {"sha256": hashlib.sha256(content).hexdigest(),
        "staff_id": str(auth[0].id)}, apply)


@router.get("/drivers/{driver_id}/documents/{file_id}/content")
def download_document(driver_id: UUID, file_id: UUID, auth: StaffAuth, db: SessionDep):
    require_driver(db, auth[0], driver_id)
    response = documents.private_download(db, driver_id, file_id)
    audit_read(db, auth[0], "document_downloaded", driver_id, {"file_id": str(file_id)})
    return response


@router.post("/drivers/{driver_id}/documents/{file_id}/scan-retries")
def retry_scan(driver_id: UUID, file_id: UUID, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    user = require_driver(db, auth[0], driver_id, write=True)
    def apply():
        require_driver(db, auth[0], driver_id, write=True)
        file = owned(db, PrivateFile, driver_id, file_id)
        job = db.scalar(rows(db, Job, driver_id).where(Job.resource_id == file_id, Job.kind == "private_scan").order_by(Job.created_at.desc()))
        if file.scan_status in {"clean", "generated"} or not job or job.status != "failed" or job.attempts >= 5 or not job.retryable:
            raise HTTPException(409, "This scan cannot be retried")
        job.status, job.error_code, job.finished_at = "queued", None, None
        job.version += 1
        add_audit(db, auth[0], "document_scan_retried", driver_id, file_id)
        return {"file_id": file.id, "job_id": job.id, "status": "queued"}
    return write(db, user, request, key, {"staff_id": str(auth[0].id)}, apply)


def create_entry(driver_id, data, auth, db, request, key, kind):
    staff = auth[0]
    user = require_driver(db, staff, driver_id, write=kind == "message")
    if not data.body.strip():
        raise HTTPException(422, "Enter a message or note")
    def apply():
        require_driver(db, staff, driver_id, write=kind == "message")
        row = StaffEntry(driver_id=driver_id, staff_id=staff.id, kind=kind, body=data.body.strip())
        db.add(row)
        db.flush()
        add_audit(db, staff, kind + "_added", driver_id, row.id, after={"entry_id": str(row.id)})
        return {**wire(row), "author": staff.name}
    return write(db, user, request, key, {"body": data.body, "kind": kind, "staff_id": str(staff.id)}, apply)


@router.post("/drivers/{driver_id}/messages", status_code=201)
def message(driver_id: UUID, data: EntryInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    return create_entry(driver_id, data, auth, db, request, key, "message")


@router.post("/drivers/{driver_id}/notes", status_code=201)
def note(driver_id: UUID, data: EntryInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    return create_entry(driver_id, data, auth, db, request, key, data.kind)


@router.post("/views/search")
def views(data: ViewSearch, auth: StaffAuth, db: SessionDep):
    return {"items": [wire(row) for row in db.scalars(select(StaffView).where(
        StaffView.staff_id == auth[0].id, StaffView.resource == data.resource).order_by(StaffView.name))]}


@router.post("/views", status_code=201)
def save_view(data: ViewInput, auth: StaffAuth, db: SessionDep, request: Request, key: Key):
    if data.resource in {"drivers", "handoffs"} and data.query.search.strip().isdigit():
        raise HTTPException(422, "Clear the UTR search before saving a view")
    def apply():
        count = db.scalar(select(func.count()).select_from(StaffView).where(StaffView.staff_id == auth[0].id))
        if count >= 100:
            raise HTTPException(409, "Remove a saved view before adding another")
        row = StaffView(staff_id=auth[0].id, resource=data.resource, name=data.name, query=data.query.model_dump())
        db.add(row)
        db.flush()
        return wire(row)
    return write(db, db.get(User, auth[0].id), request, key, data.model_dump(), apply)


@router.delete("/views/{id}", status_code=204)
def delete_view(id: UUID, auth: StaffAuth, db: SessionDep):
    row = db.scalar(select(StaffView).where(StaffView.id == id, StaffView.staff_id == auth[0].id))
    if not row:
        raise HTTPException(404, "View not found")
    db.delete(row)
    db.commit()


@router.post("/exports")
def export(data: ExportInput, auth: StaffAuth, db: SessionDep, settings: SettingsDep):
    if auth[0].role == "support":
        raise HTTPException(403, "Support cannot export financial records")
    if data.driver_id:
        lock_user(db, data.driver_id)
        require_driver(db, auth[0], data.driver_id)
    chunks = []
    query = data.query.model_copy(update={"page": 1, "page_size": 100})
    while True:
        page = driver_table(db, auth[0], data.driver_id, data.resource, query) if data.driver_id else global_table(
            db, auth[0], data.resource, query, settings)
        if page["total"] > 10000:
            raise HTTPException(422, "Narrow export to 10,000 records or fewer")
        chunks.extend(page["items"])
        if len(chunks) >= page["total"] or not page["items"]:
            break
        query = query.model_copy(update={"page": query.page + 1})
    # Only scalar presentation fields; never serialize private model columns.
    fields = sorted({key for item in chunks for key, value in item.items() if not isinstance(value, (dict, list, bytes))})
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for item in chunks:
        values = {}
        for field in fields:
            value = item.get(field)
            text = "" if value is None else str(value)
            values[field] = "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
        writer.writerow(values)
    audit_read(db, auth[0], "csv_exported", data.driver_id, {"resource": data.resource, "rows": len(chunks)})
    return Response("\ufeff" + output.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="taxiaibooks-export.csv"', "Cache-Control": "no-store"})


@driver_router.post("/me/accountant-messages/search")
def driver_messages(data: TableQuery, user: CurrentUser, db: SessionDep):
    return paginate(db, select(StaffEntry).where(StaffEntry.driver_id == user.id, StaffEntry.kind == "message"),
        StaffEntry, data, {"created_at": StaffEntry.created_at},
        lambda row: {**wire(row), "author": db.get(StaffAccount, row.staff_id).name if row.staff_id else "You"})


@driver_router.post("/me/accountant-messages", status_code=201)
def driver_message(data: EntryInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        if not data.body.strip():
            raise HTTPException(422, "Enter a message")
        row = StaffEntry(driver_id=user.id, kind="message", body=data.body.strip())
        db.add(row)
        db.flush()
        return {**wire(row), "author": "You"}
    return write(db, user, request, key, data.model_dump(), apply)
