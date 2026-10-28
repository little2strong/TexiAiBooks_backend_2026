from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import create_model
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.profiles import Key
from app.models.books import Business, Election, Mileage, Transaction, Vehicle
from app.schemas.books import (ElectionInput, MileageInput, MileagePatch, Reversal,
                               TransactionInput, TransactionPatch, VehicleInput, Versioned, VehicleLookup)
from app.services.books import (CATEGORIES, check_version, digest, exact_mutation, history, owned,
                                page, restore, rows, tax_dates, tax_year, wire, write, validate_input, profile)
from app.services.ledger import (TX_FIELDS, eligibility, mileage_total, new_transaction,
                                 sync_legacy_projection, update_transaction, validate_mileage, ensure_open_period, lock_mileage_use)
from app.schemas.results import Page, TransactionRead, VehicleRead, MileageRead

router = APIRouter(tags=["ledger"])
Limit = Annotated[int, Query(ge=1, le=100)]
VehiclePatch = create_model("VehiclePatch", __base__=Versioned,
    **{name: (field.rebuild_annotation() | None, None) for name, field in VehicleInput.model_fields.items()})


def vehicle_response(db, vehicle, year=None):
    data = {**wire(vehicle), **vehicle.details}
    data.pop("details", None)
    driver=profile(db,vehicle.owner_id,"driver")
    prior=list(db.scalars(rows(db,Election,vehicle.owner_id).where(Election.vehicle_id==vehicle.id)))
    declared_prior=any(e.evidence.get("prior_capital_allowances") or e.evidence.get("prior_vehicle_expense_claim") for e in prior)
    actual_claim=db.scalar(rows(db,Transaction,vehicle.owner_id).where(Transaction.vehicle_id==vehicle.id,
        Transaction.review_status=="confirmed",Transaction.deductible_pence>0,
        Transaction.category_id.in_([key for key,item in CATEGORIES.items() if item["requires_vehicle"]])))
    reasons=[]
    if vehicle.licence_class=="hackney" or (driver and driver.data["licence_type"]=="hackney"): reasons.append("commercial_vehicle_excluded")
    if vehicle.ownership!="owned": reasons.append("rental_lease_review_required")
    if not driver: reasons.append("driver_context_required")
    if declared_prior or actual_claim: reasons.append("prior_claim_restriction")
    eligible = not reasons
    data["eligible_methods"] = ["actual", "mileage"] if eligible else ["actual"]
    data["eligibility_reasons"] = reasons
    if vehicle.method_locked:
        data["eligible_methods"]=[vehicle.claim_method]
        data["eligibility_reasons"]=["mileage_method_already_used"]
    if year:
        data.update(mileage_total(db, vehicle.owner_id, year, vehicle.id))
        data["tax_year"] = year
        from app.services.tax import rule_set
        data["rule_set_id"] = rule_set(year, "england_wales_ni")["id"]
    return data


@router.post("/vehicles/lookup", operation_id="V01")
def lookup(data: VehicleLookup, user: CurrentUser, request: Request):
    # A registration lookup is optional; manual vehicle entry is fully supported.
    plate = data.registration
    provider = getattr(request.app.state, "vehicle_lookup", None)
    if provider is None:
        return {"registration": plate, "lookup_status": "unavailable", "manual_entry_allowed": True}
    try:
        return provider.lookup(plate)
    except Exception:
        raise HTTPException(503, "Vehicle lookup unavailable; use manual entry") from None


@router.get("/vehicles", operation_id="V02",response_model=Page[VehicleRead])
def vehicles(user: CurrentUser, db: SessionDep, settings: SettingsDep,
             active: bool = True, limit: Limit = 50, cursor: str | None = None):
    query = rows(db, Vehicle, user.id).where(Vehicle.active == active)
    return page(db, query, Vehicle, user.id, settings, limit, cursor, filters={"active": active},
                serializer=lambda v: vehicle_response(db, v))


@router.post("/vehicles", operation_id="V03", status_code=201,response_model=VehicleRead)
def create_vehicle(data: VehicleInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        if db.scalar(rows(db, Vehicle, user.id).where(Vehicle.registration == data.registration)):
            raise HTTPException(409, "Vehicle already exists")
        values = data.model_dump()
        details = {k: values.pop(k) for k in ("make", "model", "year", "colour", "fuel")}
        item = Vehicle(owner_id=user.id, **values, details=details)
        db.add(item)
        history(db, item, "create")
        return vehicle_response(db, item)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/vehicles/{id}", operation_id="V04",response_model=VehicleRead)
def vehicle_detail(id: UUID, user: CurrentUser, db: SessionDep, tax_year: str = "2026-27"):
    tax_dates(tax_year)
    return vehicle_response(db, owned(db, Vehicle, user.id, id), tax_year)


@router.patch("/vehicles/{id}", operation_id="V06",response_model=VehicleRead)
def patch_vehicle(id: UUID, data: VehiclePatch, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Vehicle, user.id, id)
        check_version(row, data.expected_version)
        changes = data.model_dump(exclude_unset=True, exclude={"expected_version"})
        if not changes:
            raise HTTPException(422, "Empty patch")
        values = {name: getattr(row, name, row.details.get(name)) for name in VehicleInput.model_fields}
        values.update(changes)
        validated = validate_input(VehicleInput,values)
        # Identity/eligibility changes require a distinct vehicle so old claims retain their basis.
        if db.scalar(rows(db, Election, user.id).where(Election.vehicle_id == id)) and set(changes) & {
                "registration", "licence_class", "ownership", "business_start_on"}:
            raise HTTPException(409, "Vehicle has election history; create a replacement vehicle for eligibility changes")
        before = wire(row)
        for field in changes:
            if field in row.details:
                row.details = {**row.details, field: getattr(validated, field)}
            else:
                setattr(row, field, getattr(validated, field))
        row.version += 1
        history(db, row, "correction", before)
        return vehicle_response(db, row)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.post("/vehicles/{id}/claim-method", operation_id="V05")
def elect(id: UUID, data: ElectionInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Vehicle, user.id, id)
        check_version(row, data.expected_version)
        if data.acknowledgement_version!="hmrc-2026-10-27":
            raise HTTPException(409,"Claim-method acknowledgement changed; reload reference data")
        if data.effective_from < row.business_start_on:
            raise HTTPException(422, "Election precedes vehicle business start")
        if row.method_locked or row.claim_method == data.method:
            raise HTTPException(409, "An existing election prevents this change")
        if db.scalar(rows(db, Election, user.id).where(Election.vehicle_id == id, Election.effective_from >= data.effective_from)):
            raise HTTPException(409, "Election overlaps existing history")
        if data.method == "mileage":
            driver=profile(db,user.id,"driver")
            if driver is None: raise HTTPException(409,"Save driver licence context before electing mileage")
            prior=list(db.scalars(rows(db,Election,user.id).where(Election.vehicle_id==id)))
            declared_prior=any(e.evidence.get("prior_capital_allowances") or e.evidence.get("prior_vehicle_expense_claim") for e in prior)
            if row.licence_class == "hackney" or driver.data["licence_type"]=="hackney" or row.ownership != "owned" or declared_prior or data.prior_capital_allowances or data.prior_vehicle_expense_claim:
                raise HTTPException(422, "Vehicle is not eligible for the supported simplified-mileage rules")
            running_cost_ids=[key for key,category in CATEGORIES.items() if category["requires_vehicle"]]
            if db.scalar(rows(db, Transaction, user.id).where(Transaction.vehicle_id == id, Transaction.deductible_pence > 0,
                Transaction.review_status=="confirmed",Transaction.category_id.in_(running_cost_ids))):
                raise HTTPException(409, "Prior actual-cost deductions require specialist review")
        before = wire(row)
        for log in db.scalars(rows(db,Mileage,user.id).where(Mileage.vehicle_id==id,Mileage.active.is_(True),Mileage.occurred_on>=data.effective_from)):
            ensure_open_period(db,user.id,log.business_id,log.occurred_on)
        election = Election(owner_id=user.id, vehicle_id=id, method=data.method,
            effective_from=data.effective_from, evidence={**data.model_dump(mode="json"),
                "official_url":"https://www.gov.uk/simpler-income-tax-simplified-expenses/vehicles",
                "verified_at":"2026-10-27T00:00:00Z"})
        db.add(election)
        row.claim_method = data.method
        # HMRC explicitly requires continued mileage use; actual-cost changes have separate history checks.
        row.method_locked = bool(data.method == "mileage" and db.scalar(rows(db,Mileage,user.id).where(
            Mileage.vehicle_id==id,Mileage.active.is_(True),Mileage.business_miles>0,Mileage.occurred_on>=data.effective_from)))
        row.version += 1
        mutation = history(db, row, "election", before)
        return {**vehicle_response(db, row), "election_id": election.id, "mutation_id": mutation}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


def filtered_transactions(db, owner, year=None, from_on=None, to_on=None, kind=None,
                          review_status=None, claim_status=None, source_ids=None, category_ids=None, q=None):
    query = rows(db, Transaction, owner)
    if year:
        start, end = tax_dates(year)
        query = query.where(Transaction.occurred_on.between(start, end))
    if from_on and to_on and from_on > to_on:
        raise HTTPException(422, "from must not exceed to")
    for column, value, comparison in [(Transaction.occurred_on, from_on, "ge"), (Transaction.occurred_on, to_on, "le")]:
        if value:
            query = query.where(column >= value if comparison == "ge" else column <= value)
    for column, value in [(Transaction.kind, kind), (Transaction.review_status, review_status), (Transaction.claim_status, claim_status)]:
        if value:
            query = query.where(column == value)
    if source_ids:
        query = query.where(Transaction.source_id.in_(source_ids))
    if category_ids:
        query = query.where(Transaction.category_id.in_(category_ids))
    if q:
        query = query.where(Transaction.description.icontains(q, autoescape=True))
    return query


@router.get("/transactions", operation_id="L01",response_model=Page[TransactionRead])
def transactions(user: CurrentUser, db: SessionDep, settings: SettingsDep, tax_year: str | None = None,
    from_on: Annotated[date | None, Query(alias="from")] = None, to_on: Annotated[date | None, Query(alias="to")] = None,
    kind: Literal["income", "expense"] | None = None,
    review_status: Literal["draft", "confirmed", "reversed"] | None = None,
    claim_status: Literal["claimable", "personal", "excluded"] | None = None,
    source_ids: Annotated[list[UUID] | None, Query()] = None, category_ids: Annotated[list[UUID] | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None, limit: Limit = 50, cursor: str | None = None):
    filters = dict(year=tax_year, from_on=from_on, to_on=to_on, kind=kind, review_status=review_status,
                   claim_status=claim_status, source_ids=source_ids, category_ids=category_ids, q=q)
    return page(db, filtered_transactions(db, user.id, **filters), Transaction, user.id, settings,
                limit, cursor, Transaction.occurred_on, filters)


@router.post("/transactions", operation_id="L02", status_code=201,response_model=TransactionRead)
def create_transaction(data: TransactionInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    return write(db, user, request, key, data.model_dump(mode="json"), lambda: wire(new_transaction(db, user.id, data)))


@router.get("/transactions/{id}", operation_id="L03",response_model=TransactionRead)
def transaction(id: UUID, user: CurrentUser, db: SessionDep):
    row = owned(db, Transaction, user.id, id)
    return {**wire(row), "receipt": {"id": row.receipt_id} if row.receipt_id else None, "payout": None}


@router.patch("/transactions/{id}", operation_id="L04",response_model=TransactionRead)
def patch_transaction(id: UUID, data: TransactionPatch, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    return write(db, user, request, key, data.model_dump(mode="json"),
                 lambda: wire(update_transaction(db, owned(db, Transaction, user.id, id), data)))


@router.delete("/transactions/{id}", operation_id="L05", status_code=204)
def void_transaction(id: UUID, expected_version: int, reason: Annotated[str, Query(min_length=1, max_length=500)],
                     user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Transaction, user.id, id)
        check_version(row, expected_version)
        ensure_open_period(db,user.id,row.business_id,row.occurred_on)
        if row.receipt_id or row.import_origin_key or row.review_status == "reversed":
            raise HTTPException(409, "Use the originating workflow or reverse the existing void")
        before = wire(row)
        row.review_status = "reversed"
        row.version += 1
        history(db, row, "void", before, reason)
        sync_legacy_projection(db, row)
    write(db, user, request, key, {"reason": reason, "version": expected_version}, apply)


@router.post("/transactions/{id}/reversals", operation_id="L06",response_model=TransactionRead)
def reverse_transaction(id: UUID, data: Reversal, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Transaction, user.id, id)
        if row.receipt_id or row.import_origin_key:
            raise HTTPException(409, "Reverse through the originating workflow")
        mutation = exact_mutation(db, row, data)
        ensure_open_period(db,user.id,row.business_id,row.occurred_on)
        if mutation.before:
            ensure_open_period(db,user.id,row.business_id,date.fromisoformat(mutation.before["occurred_on"]))
        before = wire(row)
        if mutation.before:
            restore(row, mutation.before, TX_FIELDS)
        else:
            row.review_status = "reversed"
        row.version += 1
        mutation.reversed_by = history(db, row, "reversal", before, data.reason)
        sync_legacy_projection(db, row)
        return wire(row)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.get("/mileage-logs", operation_id="M01",response_model=Page[MileageRead])
def mileage(user: CurrentUser, db: SessionDep, settings: SettingsDep, tax_year: str,
            vehicle_id: UUID | None = None, limit: Limit = 50, cursor: str | None = None):
    start, end = tax_dates(tax_year)
    query = rows(db, Mileage, user.id).where(Mileage.active.is_(True), Mileage.occurred_on.between(start, end))
    if vehicle_id:
        owned(db, Vehicle, user.id, vehicle_id)
        query = query.where(Mileage.vehicle_id == vehicle_id)
    return {**page(db, query, Mileage, user.id, settings, limit, cursor, Mileage.occurred_on,
                   {"year": tax_year, "vehicle_id": vehicle_id}), "summary": mileage_total(db, user.id, tax_year, vehicle_id)}


@router.post("/mileage-logs", operation_id="M02", status_code=201)
def create_mileage(data: MileageInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        validate_mileage(db, user.id, data)
        evidence_hash = digest(data.model_dump(mode="json"))
        if db.scalar(rows(db, Mileage, user.id).where(Mileage.evidence_hash == evidence_hash)):
            raise HTTPException(409, "Mileage evidence already recorded")
        row = Mileage(owner_id=user.id, **data.model_dump(), evidence_hash=evidence_hash)
        db.add(row)
        history(db, row, "create")
        lock_mileage_use(db,user.id,row.vehicle_id,row.occurred_on)
        return {**wire(row), "summary": mileage_total(db, user.id, tax_year(data.occurred_on), data.vehicle_id)}
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.patch("/mileage-logs/{id}", operation_id="M03")
def patch_mileage(id: UUID, data: MileagePatch, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Mileage, user.id, id)
        check_version(row, data.expected_version)
        if not row.active:
            raise HTTPException(409, "Mileage is void")
        ensure_open_period(db,user.id,row.business_id,row.occurred_on)
        changes = data.model_dump(exclude_unset=True, exclude={"expected_version"})
        if not changes:
            raise HTTPException(422, "Empty patch")
        values = {name: getattr(row, name) for name in MileageInput.model_fields}
        values.update(changes)
        for name, value in list(values.items()):
            if isinstance(value, Decimal): values[name] = str(value)
        validated = validate_input(MileageInput,values)
        validate_mileage(db, user.id, validated,exclude_id=row.id)
        before = wire(row)
        for name in changes:
            setattr(row, name, getattr(validated, name))
        row.evidence_hash = digest(validated.model_dump(mode="json"))
        row.version += 1
        history(db, row, "correction", before)
        lock_mileage_use(db,user.id,row.vehicle_id,row.occurred_on)
        return wire(row)
    return write(db, user, request, key, data.model_dump(mode="json"), apply)


@router.delete("/mileage-logs/{id}", operation_id="M04", status_code=204)
def void_mileage(id: UUID, expected_version: int, reason: Annotated[str, Query(min_length=1, max_length=500)],
                 user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        row = owned(db, Mileage, user.id, id)
        check_version(row, expected_version)
        ensure_open_period(db,user.id,row.business_id,row.occurred_on)
        if not row.active: raise HTTPException(409, "Mileage already void")
        before = wire(row)
        row.active = False
        row.version += 1
        history(db, row, "void", before, reason)
    write(db, user, request, key, {"version": expected_version, "reason": reason}, apply)
