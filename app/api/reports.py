from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select, or_

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.ledger import Limit
from app.api.profiles import Key
from app.models.books import Issue, Notification, Policy, PotEntry, Receipt, Statement, Transaction
from app.models.common import utc_now
from app.schemas.books import Body, NonnegativeMoney, PolicyInput, PotInput, Reversal, Version
from app.services.books import (CATEGORIES, SOURCES, check_version, exact_mutation, history, owned,
                                page, profile, rows, tax_dates, tax_year, wire, write)
from app.services.ledger import eligibility, ensure_open_period, ledger_rows, mileage_total, totals, derived_claim_status
from app.services.sessions import lock_user
from app.services.tax import deadlines, estimate, forecast, payment_timeline, rule_set, today
from app.schemas.results import DashboardRead, TaxEstimateRead

router = APIRouter(tags=["reports and tax"])


def dashboard_response(db, owner, year):
    lock_user(db, owner)
    values = totals(db, owner, year)
    warnings = []
    try:
        tax = estimate(db, owner, year)
        estimated_tax = tax["total_pence"]
    except HTTPException as exc:
        if exc.status_code not in {409, 422}: raise
        estimated_tax = None
        warnings = [exc.detail]
    count = lambda model, *conditions: db.scalar(select(func.count()).select_from(model).where(model.owner_id == owner, *conditions))
    week_start = today() - timedelta(days=today().weekday())
    start,end=tax_dates(year)
    week_total = db.scalar(select(func.coalesce(func.sum(Transaction.amount_pence), 0)).where(
        Transaction.owner_id == owner, Transaction.review_status == "confirmed", Transaction.kind == "income",
        Transaction.occurred_on.between(max(week_start,start), min(week_start + timedelta(days=6),end,today()))))
    receipt_date=func.coalesce(Receipt.reviewed["occurred_on"].astext,Receipt.extraction["occurred_on"].astext)
    pending=count(Receipt,Receipt.review_status!="confirmed",or_(receipt_date.is_(None),receipt_date.between(str(start),str(end))))
    unresolved=db.scalar(select(func.count()).select_from(Issue).join(Statement,Issue.statement_id==Statement.id).where(
        Issue.owner_id==owner,Issue.status=="open",Statement.period_start<=end,Statement.period_end>=start))
    return {**values, "tax_year": year, "as_of": utc_now(), "estimated_tax_pence": estimated_tax,
            "has_data": bool(ledger_rows(db, owner, year)) or Decimal(values["business_miles"]) > 0,
            "pending_receipts": pending,
            "unresolved_issues": unresolved,
            "unread_notifications": count(Notification, Notification.read_at.is_(None)),
            "week_total_pence": week_total, "next_deadline": deadlines(year)[0],
            "version": values["ledger_version"], "warnings": warnings}


@router.get("/dashboard", operation_id="R01",response_model=DashboardRead)
def dashboard(tax_year: str, user: CurrentUser, db: SessionDep):
    return dashboard_response(db, user.id, tax_year)


@router.get("/reports/weekly", operation_id="R02")
def weekly(start_on: date, user: CurrentUser, db: SessionDep, business_id: UUID | None = None):
    lock_user(db, user.id)
    if business_id:
        from app.models.books import Business
        owned(db, Business, user.id, business_id)
    from app.models.books import Mileage
    end = start_on + timedelta(days=6)
    query = rows(db, Transaction, user.id).where(Transaction.kind == "income", Transaction.review_status == "confirmed",
        Transaction.occurred_on.between(start_on - timedelta(days=7), min(end,today())))
    miles_query = rows(db, Mileage, user.id).where(Mileage.active.is_(True), Mileage.occurred_on.between(start_on, min(end,today())))
    if business_id:
        query = query.where(Transaction.business_id == business_id)
        miles_query = miles_query.where(Mileage.business_id == business_id)
    records, logs = list(db.scalars(query)), list(db.scalars(miles_query))
    days = [{"date": start_on + timedelta(days=i), "income_pence": None if start_on + timedelta(days=i) > today() else
        sum(r.amount_pence for r in records if r.occurred_on == start_on + timedelta(days=i)),
        "business_miles": str(sum((r.business_miles for r in logs if r.occurred_on == start_on + timedelta(days=i)), Decimal(0))),
        "is_future": start_on + timedelta(days=i) > today()} for i in range(7)]
    sources = {}
    for r in records:
        if r.occurred_on >= start_on:
            sources[str(r.source_id)] = sources.get(str(r.source_id), 0) + r.amount_pence
    return {"start_on": start_on, "end_on": end, "total_income_pence": sum(r.amount_pence for r in records if r.occurred_on >= start_on),
        "business_miles": str(sum((r.business_miles for r in logs), Decimal(0))), "days": days,
        "sources": [{"source_id": key, "label":SOURCES[UUID(key)]["name"],"amount_pence": value} for key,value in sources.items()],
        "previous_week_total_pence": sum(r.amount_pence for r in records if r.occurred_on < start_on)}


def category_summaries(db, owner, year):
    records = ledger_rows(db, owner, year)
    start,end=tax_dates(year)
    result = []
    for category_id, category in CATEGORIES.items():
        matching = [r for r in records if r.category_id == category_id and r.kind == "expense"]
        _,end=tax_dates(year)
        policy=db.scalar(rows(db,Policy,owner).where(Policy.category_id==category_id,
            Policy.effective_from<=min(end,today())).order_by(Policy.effective_from.desc()))
        result.append({"category_id": category_id, "label": category["label_key"],
            "total_pence": sum(r.amount_pence for r in matching), "deductible_pence": sum(r.deductible_pence for r in matching),
            "business_use_percent":str(policy.percent) if policy else "100.00",
            "has_mixed_shares":len({r.business_use_percent for r in matching})>1,
            "count": len(matching), "pending_count": db.scalar(select(func.count()).select_from(Transaction).where(
                Transaction.owner_id == owner, Transaction.category_id == category_id, Transaction.review_status == "draft",
                Transaction.occurred_on.between(start,end)))})
    return result


@router.get("/reports/annual", operation_id="R03")
def annual(tax_year: str, user: CurrentUser, db: SessionDep):
    lock_user(db, user.id)
    values = totals(db, user.id, tax_year)
    records = ledger_rows(db, user.id, tax_year)
    sources = {}
    for r in records:
        if r.kind == "income": sources[str(r.source_id)] = sources.get(str(r.source_id), 0) + r.amount_pence
    try: tax = estimate(db, user.id, tax_year)
    except HTTPException as exc: tax = {"available": False, "reason": exc.detail}
    start, _ = tax_dates(tax_year)
    months = []
    for i in range(13):
        month_index = start.year * 12 + start.month - 1 + i
        key = f"{month_index // 12}-{month_index % 12 + 1:02d}"
        months.append({"month": key, "income_pence": sum(r.amount_pence for r in records if r.kind == "income" and r.occurred_on.strftime("%Y-%m") == key)})
    return {**values, "expenses_pence": values["deductible_expenses_pence"], "tax_year": tax_year, "as_of": utc_now(),
            "months": months, "sources": [{"source_id": k,"amount_pence":v} for k,v in sources.items()],
            "categories": category_summaries(db, user.id, tax_year), "tax_estimate": tax}


@router.get("/categories/summary", operation_id="R04")
def category_summary(tax_year: str, user: CurrentUser, db: SessionDep):
    lock_user(db, user.id)
    values = category_summaries(db, user.id, tax_year)
    return {"items": values, "total_deductible_pence": sum(r["deductible_pence"] for r in values),
            "personal_total_pence": sum(r["total_pence"] - r["deductible_pence"] for r in values)}


@router.get("/categories/{id}/transactions", operation_id="R05")
def category_transactions(id: UUID, tax_year: str, user: CurrentUser, db: SessionDep, settings: SettingsDep,
                          limit: Limit = 50, cursor: str | None = None):
    if id not in CATEGORIES: raise HTTPException(404, "Category not found")
    lock_user(db, user.id)
    start, end = tax_dates(tax_year)
    query = rows(db, Transaction, user.id).where(Transaction.category_id == id, Transaction.occurred_on.between(start,end))
    policy = db.scalar(rows(db, Policy, user.id).where(Policy.category_id == id).order_by(Policy.effective_from.desc()))
    return {"summary": next(r for r in category_summaries(db, user.id, tax_year) if r["category_id"] == id),
            "policy": wire(policy) if policy else {"category_id": id,"percent":"100.00","version":0},
            "transactions": page(db, query, Transaction, user.id, settings, limit, cursor, Transaction.occurred_on,
                                  {"category": id,"year":tax_year})}


@router.get("/reports/personal", operation_id="R06")
def personal(tax_year: str, user: CurrentUser, db: SessionDep, settings: SettingsDep,
             limit: Limit = 50, cursor: str | None = None):
    lock_user(db, user.id)
    start,end = tax_dates(tax_year)
    query = rows(db, Transaction, user.id).where(Transaction.kind == "expense", Transaction.review_status == "confirmed",
        Transaction.deductible_pence == 0, Transaction.occurred_on.between(start,min(end,today())))
    records = list(db.scalars(query))
    grouped=[]
    for category_id in {r.category_id for r in records}:
        matching=[r for r in records if r.category_id==category_id]
        grouped.append({"category_id":category_id,"label":CATEGORIES[category_id]["label_key"],
            "total_pence":sum(r.amount_pence for r in matching),"deductible_pence":0,"count":len(matching)})
    return {"total_pence":sum(r.amount_pence for r in records),"count":len(records),
        "by_category":grouped,
        "transactions":page(db, query, Transaction, user.id, settings, limit,cursor,Transaction.occurred_on,{"year":tax_year,"personal":True})}


@router.put("/categories/{id}/business-use", operation_id="R07")
def policy(id: UUID, data: PolicyInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        if id not in CATEGORIES: raise HTTPException(404,"Category not found")
        if data.apply_to=="future_only" and data.effective_from < today(): raise HTTPException(422,"Prospective policy cannot start in the past")
        if data.apply_to=="selected_open_period" and not data.reason: raise HTTPException(422,"Historical default correction requires a reason")
        latest = db.scalar(rows(db, Policy, user.id).where(Policy.category_id == id).order_by(Policy.effective_from.desc()))
        if data.expected_version != (latest.version if latest else 0): raise HTTPException(409,"Stale policy version")
        if latest and data.effective_from < latest.effective_from: raise HTTPException(409,"Policy precedes newer history; use per-record corrections")
        policy_before=None
        if latest and data.effective_from==latest.effective_from:
            item=latest
            policy_before=wire(item)
            item.percent,item.reason=data.percent,data.reason
            item.version+=1
        else:
            item = Policy(owner_id=user.id, category_id=id, percent=data.percent, effective_from=data.effective_from,
                          reason=data.reason,version=(latest.version+1 if latest else 1))
            db.add(item)
        affected=0
        if data.apply_to=="selected_open_period":
            _,period_end=tax_dates(tax_year(data.effective_from))
            query=rows(db,Transaction,user.id).where(Transaction.category_id==id,Transaction.review_status=="confirmed",
                Transaction.business_use_override.is_(False),Transaction.occurred_on.between(data.effective_from,period_end))
            for transaction in db.scalars(query):
                ensure_open_period(db,user.id,transaction.business_id,transaction.occurred_on)
                if transaction.import_origin_key: raise HTTPException(409,"Linked statements require their correction workflow")
                before=wire(transaction)
                values={"business_id":transaction.business_id,"kind":transaction.kind,"category_id":id,
                    "amount_pence":transaction.amount_pence,"occurred_on":transaction.occurred_on,
                    "vehicle_id":transaction.vehicle_id,"business_use_percent":data.percent}
                percent,deduction,reasons=eligibility(db,user.id,values)
                transaction.business_use_percent,transaction.deductible_pence,transaction.eligibility_reason_codes=percent,deduction,reasons
                transaction.claim_status=derived_claim_status(transaction.kind,"claimable",percent,reasons)
                transaction.version+=1
                history(db,transaction,"policy_correction",before,data.reason)
                affected+=1
        mutation = history(db,item,"policy",policy_before,data.reason)
        return {**wire(item),"apply_to":data.apply_to,"affected_count":affected,"mutation_id":mutation}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/tax/rules", operation_id="T05")
def rules(tax_year: str, region: str, user: CurrentUser):
    return rule_set(tax_year,region)


@router.get("/tax/estimate", operation_id="T01",response_model=TaxEstimateRead)
def tax_estimate(tax_year: str, user: CurrentUser, db: SessionDep, as_of: date | None = None):
    lock_user(db,user.id)
    return estimate(db,user.id,tax_year,as_of)


@router.get("/tax/forecast", operation_id="T02")
def tax_forecast(tax_year: str, user: CurrentUser, db: SessionDep, scenario: str = "current_pace"):
    lock_user(db,user.id)
    return forecast(db,user.id,tax_year,scenario)


@router.get("/tax/deduction-comparison", operation_id="T03")
def comparison(tax_year: str, user: CurrentUser, db: SessionDep, trading_allowance_eligible: bool = False):
    lock_user(db,user.id)
    expenses = estimate(db,user.id,tax_year)
    if not trading_allowance_eligible:
        return {"expenses":expenses,"trading_allowance":None,"recommended_method":None,"saving_pence":None,
                "warnings":["Explicit eligibility declaration required; connected-party/partnership income may be excluded"]}
    allowance = estimate(db,user.id,tax_year,deduction_method="trading_allowance")
    return {"expenses":expenses,"trading_allowance":allowance,
            "recommended_method":"expenses" if expenses["total_pence"] <= allowance["total_pence"] else "trading_allowance",
            "saving_pence":abs(expenses["total_pence"]-allowance["total_pence"]),"warnings":["Declaration supplied by user; not an election"]}


@router.get("/tax/payment-timeline", operation_id="T04")
def timeline(tax_year: str, user: CurrentUser, db: SessionDep):
    tax_dates(tax_year)
    return payment_timeline(db,user.id,tax_year)


class AssessmentInput(Body):
    prior_year_liability_pence: NonnegativeMoney
    tax_paid_outside_sa_pence: NonnegativeMoney
    advance_payments_pence: NonnegativeMoney
    adjustments_pence: int = 0
    expected_version: Version | None = None


@router.put("/tax/prior-assessment")
def prior_assessment(tax_year: str, data: AssessmentInput, user: CurrentUser, db: SessionDep, request: Request, key: Key):
    def apply():
        tax_dates(tax_year)
        item=profile(db,user.id,"prior_assessment",tax_year)
        if item:
            check_version(item,data.expected_version)
            item.version+=1
        else: item=profile(db,user.id,"prior_assessment",tax_year,create=True)
        item.data=data.model_dump(exclude={"expected_version"})
        history(db,item,"prior_assessment")
        return {**item.data,"version":item.version}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


def pot_summary(db,owner,year,settings,limit=50,cursor=None):
    start,end=tax_dates(year)
    query=rows(db,PotEntry,owner).where(PotEntry.occurred_on.between(start,end))
    balance=sum(r.amount_pence for r in db.scalars(query) if not r.reversed)
    try: target=estimate(db,owner,year)["total_pence"]
    except HTTPException: target=None
    return {"balance_pence":balance,"target_pence":target,"gap_pence":max(0,target-balance) if target is not None else None,
            "entries":page(db,query,PotEntry,owner,settings,limit,cursor,PotEntry.occurred_on,{"year":year}),
            "is_bank_transfer":False}


@router.get("/tax-pot", operation_id="K01")
def pot(tax_year: str,user: CurrentUser,db: SessionDep,settings: SettingsDep,limit: Limit=50,cursor: str|None=None):
    lock_user(db,user.id)
    return pot_summary(db,user.id,tax_year,settings,limit,cursor)


@router.post("/tax-pot/entries", operation_id="K02",status_code=201)
def add_pot(data: PotInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    def apply():
        item=PotEntry(owner_id=user.id,**data.model_dump())
        db.add(item)
        history(db,item,"savings_log")
        return {"entry":wire(item),"summary":pot_summary(db,user.id,tax_year(data.occurred_on),settings)}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/tax-pot/entries/{id}/reversals", operation_id="K03")
def reverse_pot(id: UUID,data: Reversal,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    def apply():
        item=owned(db,PotEntry,user.id,id)
        mutation=exact_mutation(db,item,data)
        if item.reversed: raise HTTPException(409,"Savings entry already reversed")
        before=wire(item)
        item.reversed=True
        item.version+=1
        mutation.reversed_by=history(db,item,"reversal",before,data.reason)
        return {"entry":wire(item),"summary":pot_summary(db,user.id,tax_year(item.occurred_on),settings)}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/deadlines", operation_id="N04")
def dates(tax_year: str,user: CurrentUser):
    return deadlines(tax_year)
