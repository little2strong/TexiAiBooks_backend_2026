from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.models.books import Business, Election, Mileage, Policy, SupportRecord, Transaction, Vehicle
from app.schemas.books import TransactionInput
from app.services.books import (CATEGORIES, SOURCES, catalog_id, check_version, digest,
                                history, owned, pence, primary_business, rows, tax_dates, wire, validate_input)

TX_FIELDS = ["amount_pence", "occurred_on", "source_id", "category_id", "vehicle_id", "payment_method",
             "description", "no_receipt_reason", "business_use_percent", "deductible_pence", "review_status",
             "claim_status", "eligibility_reason_codes", "business_use_override"]


def ensure_open_period(db,owner,business_id,occurred_on):
    updates=db.scalars(rows(db,SupportRecord,owner).where(SupportRecord.kind=="mtd_update",
        SupportRecord.data["status"].astext.in_(["queued","submitting","accepted","partial","unknown"])))
    for update in updates:
        preview=owned(db,SupportRecord,owner,UUID(update.data["preview_id"]))
        for snapshot in preview.data["businesses"]:
            obligation=snapshot["provider_obligation"]
            if snapshot["business_id"]==str(business_id) and date.fromisoformat(obligation["period_start"])<=occurred_on<=date.fromisoformat(obligation["period_end"]):
                raise HTTPException(409,"Period has a queued, uncertain or accepted HMRC update; use the provider correction workflow")


def eligibility(db, owner, values, claim_status="claimable"):
    owned(db, Business, owner, values["business_id"])
    category = CATEGORIES.get(values.get("category_id"))
    source_id = values.get("source_id")
    if source_id and source_id not in SOURCES:
        raise HTTPException(422, "Unknown source")
    if values["kind"] == "income":
        if source_id is None:
            raise HTTPException(422, "Income source required")
        return Decimal(100), 0, []
    if category is None:
        raise HTTPException(422, "Unknown expense category")
    percent = values.get("business_use_percent")
    if percent is None:
        policy = db.scalar(rows(db, Policy, owner).where(Policy.category_id == values["category_id"],
            Policy.effective_from <= values["occurred_on"]).order_by(Policy.effective_from.desc()))
        percent = policy.percent if policy else Decimal(100)
    reasons = []
    if claim_status != "claimable" or percent == 0:
        reasons.append("personal_or_excluded")
    code = category["code"]
    if code in {"fines", "meals", "other", "vehicle_purchase"}:
        reasons.append("specialist_review_required" if code in {"other", "vehicle_purchase"} else "not_allowable")
    if category["requires_vehicle"]:
        if not values.get("vehicle_id"):
            reasons.append("vehicle_context_required")
        else:
            vehicle = owned(db, Vehicle, owner, values["vehicle_id"])
            election = db.scalar(rows(db, Election, owner).where(Election.vehicle_id == vehicle.id,
                Election.effective_from <= values["occurred_on"]).order_by(Election.effective_from.desc()))
            if not election:
                reasons.append("claim_method_not_elected")
            elif election.method == "mileage":
                reasons.append("covered_by_mileage")
    elif values.get("vehicle_id"):
        owned(db, Vehicle, owner, values["vehicle_id"])
    deduction = 0 if reasons else pence(Decimal(values["amount_pence"]) * percent / 100)
    return percent, deduction, reasons


def derived_claim_status(kind,requested,percent,reasons):
    if kind=="income": return "claimable"
    if requested=="personal" or percent==0: return "personal"
    if requested=="excluded" or reasons: return "excluded"
    return "claimable"


def new_transaction(db, owner, data, *, claim_status="claimable", receipt_id=None, origin=None, draft=False):
    values = data.model_dump()
    if values.pop("receipt_id", None) is not None and receipt_id is None:
        raise HTTPException(409, "Use receipt confirmation to post receipt-backed transactions")
    percent, deduction, reasons = eligibility(db, owner, values, claim_status)
    ensure_open_period(db,owner,data.business_id,data.occurred_on)
    row = Transaction(owner_id=owner, **(values | {"business_use_percent": percent}),
        business_use_override=data.business_use_percent is not None,
        deductible_pence=deduction, eligibility_reason_codes=reasons,
        claim_status=derived_claim_status(data.kind,claim_status,percent,reasons),
        review_status="draft" if draft else "confirmed", receipt_id=receipt_id, import_origin_key=origin)
    db.add(row)
    db.flush()
    history(db, row, "create")
    return row


def update_transaction(db, row, data):
    check_version(row, data.expected_version)
    ensure_open_period(db,row.owner_id,row.business_id,row.occurred_on)
    if row.receipt_id or row.import_origin_key:
        raise HTTPException(409, "Use the originating receipt or reconciliation correction workflow")
    if row.review_status == "reversed":
        raise HTTPException(409, "Reverse the void before editing")
    before = wire(row)
    changes = data.model_dump(exclude_unset=True, exclude={"expected_version"})
    if row.legacy_expense_id and changes.get("amount_pence",row.amount_pence)>2_147_483_647:
        raise HTTPException(422,"Legacy expense amount exceeds its preserved integer contract")
    values = {**wire(row), **changes}
    # ORM types must stay UUID/date/Decimal throughout validation.
    current = {name: getattr(row, name) for name in TransactionInput.model_fields}
    current.update(changes)
    if isinstance(current.get("business_use_percent"), Decimal):
        current["business_use_percent"] = str(current["business_use_percent"])
    validated = validate_input(TransactionInput,current)
    ensure_open_period(db,row.owner_id,row.business_id,validated.occurred_on)
    percent, deduction, reasons = eligibility(db, row.owner_id, validated.model_dump())
    for field, value in changes.items():
        setattr(row, field, value)
    row.business_use_percent, row.deductible_pence, row.eligibility_reason_codes = percent, deduction, reasons
    row.claim_status=derived_claim_status(row.kind,"claimable",percent,reasons)
    if "business_use_percent" in changes: row.business_use_override=True
    row.version += 1
    history(db, row, "correction", before)
    sync_legacy_projection(db, row)
    return row


def sync_legacy_projection(db, transaction):
    if not transaction.legacy_expense_id:
        return
    from app.models import Expense
    from app.models.common import utc_now
    expense = owned(db, Expense, transaction.owner_id, transaction.legacy_expense_id)
    expense.amount_pence = transaction.amount_pence
    expense.expense_date = transaction.occurred_on
    expense.note = transaction.description
    code = CATEGORIES[transaction.category_id]["code"]
    expense.category = code if code in {"fuel", "maintenance", "insurance", "licensing", "parking"} else "other"
    expense.deleted_at = utc_now() if transaction.review_status == "reversed" else None


def sync_legacy(db, expense):
    """Legacy /expenses remains a compatibility projection into ONE ledger."""
    row = db.scalar(rows(db, Transaction, expense.owner_id).where(Transaction.legacy_expense_id == expense.id))
    if row is not None and row.import_origin_key:
        raise HTTPException(409, "Reverse the reconciliation link before changing this legacy expense")
    before = wire(row) if row else None
    business = primary_business(db, expense.owner_id)
    ensure_open_period(db,expense.owner_id,business.id,expense.expense_date)
    if row: ensure_open_period(db,expense.owner_id,business.id,row.occurred_on)
    if row is None:
        row = Transaction(id=expense.id, owner_id=expense.owner_id, legacy_expense_id=expense.id,
                          business_id=business.id, kind="expense", amount_pence=expense.amount_pence,
                          occurred_on=expense.expense_date)
        db.add(row)
    else:
        row.version += 1
    row.amount_pence, row.occurred_on, row.description = expense.amount_pence, expense.expense_date, expense.note
    row.currency, row.category_id = "GBP", catalog_id("category", expense.category)
    values = {"kind": "expense", "business_id": business.id, "amount_pence": row.amount_pence,
              "category_id": row.category_id, "occurred_on": row.occurred_on, "business_use_percent": Decimal(100)}
    percent, deduction, reasons = eligibility(db, expense.owner_id, values)
    row.business_use_percent, row.deductible_pence, row.eligibility_reason_codes = percent, deduction, reasons
    row.review_status = "reversed" if expense.deleted_at else "confirmed"
    row.claim_status = derived_claim_status("expense","claimable",percent,reasons)
    history(db, row, "legacy_sync", before)


def mileage_total(db, owner, year, vehicle_id=None, as_of=None, business_id=None):
    start, end = tax_dates(year)
    from app.services.tax import today
    end = min(end, as_of or today())
    query = rows(db, Mileage, owner).where(Mileage.active.is_(True), Mileage.occurred_on.between(start, end))
    if vehicle_id:
        query = query.where(Mileage.vehicle_id == vehicle_id)
    if business_id:
        query = query.where(Mileage.business_id == business_id)
    totals = {}
    for row in db.scalars(query):
        election = db.scalar(rows(db, Election, owner).where(Election.vehicle_id == row.vehicle_id,
            Election.effective_from <= row.occurred_on).order_by(Election.effective_from.desc()))
        key = row.vehicle_id
        miles, eligible = totals.get(key, (Decimal(0), Decimal(0)))
        totals[key] = (miles + row.business_miles, eligible + (row.business_miles if election and election.method == "mileage" else 0))
    total_miles = sum((x[0] for x in totals.values()), Decimal(0))
    deduction = 0
    for vehicle, (_, miles) in totals.items():
        item = owned(db, Vehicle, owner, vehicle)
        deduction += mileage_deduction(miles, year, item.licence_class)
    return {"business_miles": format(total_miles, ".2f"), "deduction_pence": deduction,
            "threshold_remaining": format(sum((max(Decimal(0), Decimal(10000) - x[1]) for x in totals.values()), Decimal(0)), ".2f")}


def mileage_deduction(miles, year, vehicle_class="private_hire"):
    if year not in {"2025-26", "2026-27"}:
        raise HTTPException(422, "Mileage rules are not verified for this tax year")
    if vehicle_class == "hackney":
        return 0
    if vehicle_class == "motorcycle":
        return pence(miles * 24)
    first_rate = 55 if year == "2026-27" else 45
    return pence(min(miles, Decimal(10000)) * first_rate + max(Decimal(0), miles - 10000) * 25)


def validate_mileage(db, owner, data, exclude_id=None):
    owned(db, Business, owner, data.business_id)
    ensure_open_period(db,owner,data.business_id,data.occurred_on)
    vehicle = owned(db, Vehicle, owner, data.vehicle_id)
    if not vehicle.active or data.occurred_on < vehicle.business_start_on:
        raise HTTPException(422, "Vehicle not active on mileage date")
    query=rows(db,Mileage,owner).where(Mileage.vehicle_id==data.vehicle_id,Mileage.active.is_(True))
    if exclude_id: query=query.where(Mileage.id!=exclude_id)
    if data.start_odometer is not None:
        for previous in db.scalars(query.where(Mileage.start_odometer.is_not(None))):
            overlap=previous.start_odometer<data.end_odometer and previous.end_odometer>data.start_odometer
            backwards=(previous.occurred_on<data.occurred_on and previous.end_odometer>data.start_odometer) or (
                previous.occurred_on>data.occurred_on and previous.start_odometer<data.end_odometer)
            if overlap or backwards: raise HTTPException(409,"Odometer evidence overlaps or moves backwards")


def lock_mileage_use(db,owner,vehicle_id,occurred_on):
    vehicle=owned(db,Vehicle,owner,vehicle_id)
    election=db.scalar(rows(db,Election,owner).where(Election.vehicle_id==vehicle_id,
        Election.effective_from<=occurred_on).order_by(Election.effective_from.desc()))
    if election and election.method=="mileage" and not vehicle.method_locked:
        before=wire(vehicle)
        vehicle.method_locked=True
        vehicle.version+=1
        history(db,vehicle,"mileage_method_used",before)


def ledger_rows(db, owner, year, as_of=None, business_id=None):
    start, end = tax_dates(year)
    from app.services.tax import today
    end = min(end, as_of or today())
    query = rows(db, Transaction, owner).where(Transaction.review_status == "confirmed", Transaction.occurred_on.between(start, end))
    if business_id:
        owned(db, Business, owner, business_id)
        query = query.where(Transaction.business_id == business_id)
    return list(db.scalars(query))


def totals(db, owner, year, as_of=None):
    records = ledger_rows(db, owner, year, as_of)
    income = sum(r.amount_pence for r in records if r.kind == "income")
    expenses = sum(r.deductible_pence for r in records if r.kind == "expense")
    mileage = mileage_total(db, owner, year, as_of=as_of)
    expenses += mileage["deduction_pence"]
    start,end=tax_dates(year)
    all_transactions=list(db.scalars(rows(db,Transaction,owner).where(Transaction.occurred_on.between(start,end)).order_by(Transaction.id)))
    all_mileage=list(db.scalars(rows(db,Mileage,owner).where(Mileage.occurred_on.between(start,end)).order_by(Mileage.id)))
    return {"income_pence": income, "deductible_expenses_pence": expenses, "profit_pence": income - expenses,
            "business_miles": mileage["business_miles"], "mileage_deduction_pence": mileage["deduction_pence"],
            "mileage_threshold_remaining": mileage["threshold_remaining"],
            "ledger_version": digest([[str(r.id), r.version] for r in all_transactions + all_mileage] + [mileage])}
