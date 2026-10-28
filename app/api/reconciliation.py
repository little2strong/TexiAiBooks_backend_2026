from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select,or_

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.ledger import Limit
from app.api.profiles import Key
from app.models.books import Issue, Statement, Transaction
from app.schemas.books import Reversal, TransactionInput, Versioned
from app.services.books import catalog_id, check_version, exact_mutation, history, owned, page, rows, tax_dates, wire, write
from app.services.ledger import new_transaction,ensure_open_period

router=APIRouter(tags=["reconciliation"])


class ResolutionInput(Versioned):
    mode: Literal["add_missing","link_existing"]
    transaction_ids: list[UUID]=[]
    new_transactions: list[TransactionInput]=[]
    evidence_note: str|None=None


class ResolutionReversal(Reversal):
    resolution_id: UUID


def candidates(db,issue,statement):
    return list(db.scalars(rows(db,Transaction,issue.owner_id).where(Transaction.business_id==statement.business_id,
        Transaction.source_id==statement.source_id,Transaction.review_status=="confirmed",
        or_(Transaction.kind=="income",(Transaction.kind=="expense")&(Transaction.category_id==catalog_id("category","platform_fees"))),
        Transaction.occurred_on.between(statement.period_start,statement.period_end))))


def sums(records):
    gross=sum(r.amount_pence for r in records if r.kind=="income")
    fee=sum(r.amount_pence for r in records if r.kind=="expense" and r.category_id==catalog_id("category","platform_fees"))
    return gross,fee


def issue_wire(db,issue):
    statement=owned(db,Statement,issue.owner_id,issue.statement_id)
    matching=candidates(db,issue,statement)
    if issue.resolution:
        ids={r.id for r in matching}
        for effect in issue.resolution["effects"]:
            item=owned(db,Transaction,issue.owner_id,UUID(effect["id"]))
            if item.id not in ids and item.review_status=="confirmed": matching.append(item)
    recorded_gross,recorded_fee=sums(matching)
    statement_gross=sum(p["gross_pence"] for p in statement.payouts)
    statement_fee=sum(p["fee_pence"] for p in statement.payouts)
    return {**wire(issue),"source_id":statement.source_id,"business_id":statement.business_id,
        "period_start":statement.period_start,"period_end":statement.period_end,
        "statement_gross_pence":statement_gross,"recorded_gross_pence":recorded_gross,
        "difference_pence":statement_gross-recorded_gross,"statement_fee_pence":statement_fee,
        "recorded_fee_pence":recorded_fee,"fee_difference_pence":statement_fee-recorded_fee,
        "candidate_transactions":[wire(r) for r in matching]}


@router.get("/reconciliations",operation_id="Q01")
def issues(tax_year: str,user: CurrentUser,db: SessionDep,settings: SettingsDep,source_id: UUID|None=None,
    status: Literal["open","resolved"]|None=None,limit: Limit=50,cursor: str|None=None):
    start,end=tax_dates(tax_year)
    query=rows(db,Issue,user.id).join(Statement,Statement.id==Issue.statement_id).where(
        Statement.period_start<=end,Statement.period_end>=start)
    if source_id: query=query.where(Statement.source_id==source_id)
    if status: query=query.where(Issue.status==status)
    return page(db,query,Issue,user.id,settings,limit,cursor,filters={"year":tax_year,"source":source_id,"status":status},
                serializer=lambda r:issue_wire(db,r))


@router.get("/reconciliations/{id}",operation_id="Q02")
def issue(id: UUID,user: CurrentUser,db: SessionDep):
    return issue_wire(db,owned(db,Issue,user.id,id))


@router.post("/reconciliations/{id}/resolutions",operation_id="Q03")
def resolve(id: UUID,data: ResolutionInput,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        issue=owned(db,Issue,user.id,id)
        check_version(issue,data.expected_version)
        if issue.status!="open": raise HTTPException(409,"Issue already resolved")
        statement=owned(db,Statement,user.id,issue.statement_id)
        matching=candidates(db,issue,statement)
        original_ids={r.id for r in matching}
        additions=[]
        resolution_id=uuid4()
        if data.mode=="add_missing":
            if not data.new_transactions or data.transaction_ids: raise HTTPException(422,"Supply new transactions only")
            for tx_input in data.new_transactions:
                if tx_input.business_id!=statement.business_id or tx_input.source_id!=statement.source_id or not statement.period_start<=tx_input.occurred_on<=statement.period_end:
                    raise HTTPException(422,"Resolution transaction must match statement business, source and period")
                if tx_input.kind=="expense" and tx_input.category_id!=catalog_id("category","platform_fees"):
                    raise HTTPException(422,"Only platform fees may reconcile this statement")
                tx=new_transaction(db,user.id,tx_input,origin=f"resolution:{resolution_id}:{len(additions)}")
                additions.append(tx)
        else:
            if not data.transaction_ids or data.new_transactions: raise HTTPException(422,"Supply existing transaction IDs only")
            if len(set(data.transaction_ids))!=len(data.transaction_ids): raise HTTPException(422,"Duplicate linked transaction")
            for tx_id in data.transaction_ids:
                tx=owned(db,Transaction,user.id,tx_id)
                if tx.business_id!=statement.business_id or tx.source_id!=statement.source_id or tx.review_status!="confirmed" or tx.import_origin_key:
                    raise HTTPException(422,"Existing record must be unlinked confirmed money for the same business/source")
                if tx.kind=="expense" and tx.category_id!=catalog_id("category","platform_fees"):
                    raise HTTPException(422,"Only gross income and platform fees may be linked")
                if tx.id not in original_ids: matching.append(tx)
        all_rows=matching+additions
        gross,fee=sums(all_rows)
        if gross!=sum(p["gross_pence"] for p in statement.payouts) or fee!=sum(p["fee_pence"] for p in statement.payouts):
            raise HTTPException(409,"Resolution does not reconcile actual gross and fees")
        effects=[]
        for tx in all_rows:
            ensure_open_period(db,user.id,tx.business_id,tx.occurred_on)
            if tx.import_origin_key and tx not in additions: raise HTTPException(409,"Candidate already linked to another accounting origin")
            before=wire(tx)
            original=tx.import_origin_key
            if tx not in additions:
                tx.import_origin_key=f"resolution:{resolution_id}:{tx.id}"
                tx.version+=1
                history(db,tx,"reconciliation_link",before)
            effects.append({"id":str(tx.id),"version":tx.version,"created":tx in additions,"previous_origin":original})
        before=wire(issue)
        issue.resolution={"mode":data.mode,"effects":effects,"evidence_note":data.evidence_note}
        issue.resolution_id=resolution_id
        issue.status="resolved"
        issue.version+=1
        mutation=history(db,issue,"resolution",before)
        return {"issue":issue_wire(db,issue),"resolution_id":resolution_id,"mutation_id":mutation}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/reconciliations/{id}/reversals",operation_id="Q04")
def reverse(id: UUID,data: ResolutionReversal,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        issue=owned(db,Issue,user.id,id)
        action=exact_mutation(db,issue,data)
        if issue.status!="resolved" or issue.resolution_id!=data.resolution_id: raise HTTPException(409,"Resolution does not match")
        for effect in issue.resolution["effects"]:
            tx=owned(db,Transaction,user.id,UUID(effect["id"]))
            ensure_open_period(db,user.id,tx.business_id,tx.occurred_on)
            if tx.version!=effect["version"]: raise HTTPException(409,"Resolution posting changed")
            before=wire(tx)
            if effect["created"]: tx.review_status="reversed"
            else: tx.import_origin_key=effect["previous_origin"]
            tx.version+=1
            history(db,tx,"resolution_reversal",before,data.reason)
        before=wire(issue)
        issue.status="open"
        issue.resolution=None
        issue.resolution_id=None
        issue.version+=1
        action.reversed_by=history(db,issue,"reversal",before,data.reason)
        return issue_wire(db,issue)
    return write(db,user,request,key,data.model_dump(mode="json"),apply)
