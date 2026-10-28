from datetime import date
from decimal import Decimal
import hashlib
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import func, select, or_

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.ledger import Limit
from app.api.profiles import Key
from app.api.reports import dashboard_response
from app.models.books import Business, Issue, Job, PrivateFile, Receipt, Statement, Transaction, Vehicle
from app.schemas.books import (Body, Confirmation, ReceiptPatch, Reversal, TransactionInput, Versioned)
from app.services.books import (CATEGORIES, SOURCES, catalog_id, check_version, exact_mutation, history,
                                owned, page, rows, tax_dates, tax_year, wire, write)
from app.services.files import receipt_wire, statement_wire, store_file, validate_file, sync_receipt_draft
from app.services.ledger import eligibility, new_transaction, ensure_open_period, derived_claim_status
from app.schemas.results import JobRead, ReceiptRead, StatementRead

router=APIRouter(tags=["receipts and statements"])


def upload_content(file,settings,kind):
    content=file.file.read(settings.upload_max_bytes+1)
    if not content or len(content)>settings.upload_max_bytes:
        raise HTTPException(413,"File is empty or exceeds upload limit")
    return content,validate_file(content,file.content_type,kind)


@router.post("/receipts",operation_id="C01",status_code=202)
def upload_receipt(user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key,
    file: Annotated[UploadFile,File()],business_id: Annotated[UUID,Form()],vehicle_id: Annotated[UUID|None,Form()]=None):
    content,mime=upload_content(file,settings,"receipt")
    def apply():
        owned(db,Business,user.id,business_id)
        if vehicle_id: owned(db,Vehicle,user.id,vehicle_id)
        stored=store_file(db,user.id,content,mime)
        if db.scalar(rows(db,Receipt,user.id).where(Receipt.file_id==stored.id)):
            raise HTTPException(409,"Receipt file already uploaded")
        receipt=Receipt(owner_id=user.id,business_id=business_id,vehicle_id=vehicle_id,file_id=stored.id)
        db.add(receipt)
        db.flush()
        job=Job(owner_id=user.id,kind="receipt_ocr",resource_id=receipt.id)
        db.add(job)
        db.flush()
        receipt.job_id=job.id
        return {"receipt":receipt_wire(db,receipt),"job":wire(job)}
    return write(db,user,request,key,{"sha256":hashlib.sha256(content).hexdigest(),"business_id":str(business_id),"vehicle_id":str(vehicle_id)},apply)


@router.get("/jobs/{id}",response_model=JobRead)
def job_detail(id: UUID,user: CurrentUser,db: SessionDep):
    return wire(owned(db,Job,user.id,id))


@router.get("/receipts",operation_id="C02")
def receipts(tax_year: str,user: CurrentUser,db: SessionDep,settings: SettingsDep,
    review_status: Literal["pending","confirmed","reversed"]|None=None,
    claim_status: Literal["claimable","personal","excluded","unknown"]|None=None,
    limit: Limit=50,cursor: str|None=None):
    tax_dates(tax_year)
    # Undated/incomplete evidence belongs in every requested year's review queue.
    from app.services.tax import today
    query=rows(db,Receipt,user.id)
    start,end=tax_dates(tax_year)
    date_value=func.coalesce(Receipt.reviewed["occurred_on"].astext,Receipt.extraction["occurred_on"].astext)
    from sqlalchemy import or_
    year_query=query.where(or_(date_value.is_(None),date_value.between(str(start),str(end))))
    filtered=year_query
    if review_status: filtered=filtered.where(Receipt.review_status==review_status)
    if claim_status: filtered=filtered.where(Receipt.claim_status==claim_status)
    def count(*conditions):
        return db.scalar(select(func.count()).select_from(year_query.where(*conditions).subquery()))
    return {**page(db,filtered,Receipt,user.id,settings,limit,cursor,filters={"year":tax_year,"review":review_status,"claim":claim_status},
        serializer=lambda r:receipt_wire(db,r)),"counts":{"all":count(),
        "pending":count(Receipt.review_status!="confirmed"),
        "counted":count(Receipt.review_status=="confirmed",Receipt.claim_status=="claimable"),
        "not_claimed":count(Receipt.review_status=="confirmed",Receipt.claim_status!="claimable")}}


@router.get("/receipts/{id}",operation_id="C03",response_model=ReceiptRead)
def receipt(id: UUID,user: CurrentUser,db: SessionDep):
    return receipt_wire(db,owned(db,Receipt,user.id,id))


@router.patch("/receipts/{id}",operation_id="C04")
def review(id: UUID,data: ReceiptPatch,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Receipt,user.id,id)
        check_version(row,data.expected_version)
        if row.review_status=="confirmed": raise HTTPException(409,"Reverse confirmation before reviewing corrections")
        values=data.model_dump(mode="json",exclude_unset=True,exclude={"expected_version"})
        if not values: raise HTTPException(422,"Empty review")
        for name in ("merchant","occurred_on","amount_pence","category_id","business_use_percent","claim_status"):
            if name in values and values[name] is None: raise HTTPException(422,"Reviewed fields cannot be null")
        merged={**(row.extraction or {}),**row.reviewed,**values}
        if merged.get("vat_pence") is not None and merged.get("amount_pence") is not None and merged["vat_pence"]>merged["amount_pence"]:
            raise HTTPException(422,"VAT cannot exceed total")
        if values.get("category_id") and UUID(values["category_id"]) not in CATEGORIES: raise HTTPException(422,"Unknown category")
        before=wire(row)
        row.reviewed={**row.reviewed,**values}
        row.version+=1
        history(db,row,"review",before)
        sync_receipt_draft(db,row)
        return receipt_wire(db,row)
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/receipts/{id}/confirmations",operation_id="C05")
def confirm(id: UUID,data: Confirmation,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Receipt,user.id,id)
        check_version(row,data.expected_version)
        if row.review_status=="confirmed": raise HTTPException(409,"Receipt already confirmed")
        values={**(row.extraction or {}),**row.reviewed}
        if not values.get("amount_pence") or not values.get("occurred_on"):
            raise HTTPException(422,"Review actual amount and date before confirming")
        before=wire(row)
        tx_data=TransactionInput(kind="expense",amount_pence=values["amount_pence"],occurred_on=values["occurred_on"],
            business_id=row.business_id,category_id=data.category_id,vehicle_id=row.vehicle_id,
            description=values.get("merchant"),business_use_percent=str(data.business_use_percent))
        ensure_open_period(db,user.id,row.business_id,tx_data.occurred_on)
        tx=db.scalar(rows(db,Transaction,user.id).where(Transaction.receipt_id==id))
        if tx:
            if tx.review_status=="confirmed": raise HTTPException(409,"Receipt posting already confirmed")
            percent,deduction,reasons=eligibility(db,user.id,tx_data.model_dump(),data.claim_status)
            for name,value in tx_data.model_dump(exclude={"receipt_id"}).items(): setattr(tx,name,value)
            tx.business_use_percent,tx.deductible_pence,tx.eligibility_reason_codes=percent,deduction,reasons
            tx.claim_status,tx.review_status=derived_claim_status("expense",data.claim_status,percent,reasons),"confirmed"
            tx.business_use_override=True
            tx.version+=1
            history(db,tx,"receipt_confirmation")
        else:
            tx=new_transaction(db,user.id,tx_data,claim_status=data.claim_status,receipt_id=id)
        row.reviewed={**values,"category_id":str(data.category_id),"business_use_percent":str(data.business_use_percent)}
        row.claim_status,row.review_status=tx.claim_status,"confirmed"
        row.version+=1
        mutation=history(db,row,"confirmation",before)
        # Bind reversal to the exact ledger version created by this confirmation.
        from app.models.books import Mutation
        action=db.get(Mutation,mutation)
        action.after={**action.after,"posting_id":str(tx.id),"posting_version":tx.version}
        return {"receipt":receipt_wire(db,row),"transaction":wire(tx),"mutation_id":mutation,
                "dashboard":dashboard_response(db,user.id,tax_year(date.fromisoformat(values["occurred_on"])))}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/receipts/{id}/reversals",operation_id="C06")
def reverse_receipt(id: UUID,data: Reversal,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Receipt,user.id,id)
        action=exact_mutation(db,row,data)
        if action.action!="confirmation" or row.review_status!="confirmed": raise HTTPException(409,"Reverse a confirmation mutation")
        tx=owned(db,Transaction,user.id,UUID(action.after["posting_id"]))
        ensure_open_period(db,user.id,tx.business_id,tx.occurred_on)
        if tx.version!=action.after["posting_version"] or tx.review_status!="confirmed": raise HTTPException(409,"Ledger changed after confirmation")
        before=wire(row)
        tx.review_status="reversed"
        tx.version+=1
        history(db,tx,"receipt_reversal",reason=data.reason)
        row.review_status="reversed"
        row.version+=1
        action.reversed_by=history(db,row,"reversal",before,data.reason)
        return {"receipt":receipt_wire(db,row),"transaction":wire(tx),
                "dashboard":dashboard_response(db,user.id,tax_year(tx.occurred_on))}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


def private_download(db,owner,file_id):
    item=owned(db,PrivateFile,owner,file_id)
    if item.scan_status not in {"clean","generated"}: raise HTTPException(409,"File is quarantined until scanning succeeds")
    return Response(item.content,media_type=item.mime_type,headers={"Cache-Control":"no-store",
        "Content-Disposition":'attachment; filename="document"',"X-Content-Type-Options":"nosniff"})


@router.get("/receipts/{id}/content",operation_id="C07")
def receipt_content(id: UUID,user: CurrentUser,db: SessionDep):
    return private_download(db,user.id,owned(db,Receipt,user.id,id).file_id)


@router.post("/receipts/{id}/ocr-retries",operation_id="C08",status_code=202)
def retry_ocr(id: UUID,data: Versioned,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Receipt,user.id,id)
        check_version(row,data.expected_version)
        job=owned(db,Job,user.id,row.job_id)
        if row.review_status=="confirmed" or job.status!="failed" or not job.retryable or job.attempts>=5:
            raise HTTPException(409,"OCR job cannot be retried")
        job.status="queued"
        job.version+=1
        job.finished_at=None
        job.error_code=None
        row.processing_status="queued"
        row.version+=1
        return {"receipt":receipt_wire(db,row),"job":wire(job)}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/jobs/{id}/retries",status_code=202)
def retry_job(id: UUID,data: Versioned,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        job=owned(db,Job,user.id,id)
        check_version(job,data.expected_version)
        if job.status!="failed" or not job.retryable or job.attempts>=5: raise HTTPException(409,"Job cannot be retried")
        if job.kind in {"receipt_ocr","statement_parse"}:
            model=Receipt if job.kind=="receipt_ocr" else Statement
            row=owned(db,model,user.id,job.resource_id)
            if (isinstance(row,Receipt) and row.review_status=="confirmed") or (isinstance(row,Statement) and row.import_status=="imported"):
                raise HTTPException(409,"Posted resources cannot be reprocessed")
            row.processing_status="queued"
            row.version+=1
        job.status="queued"
        job.version+=1
        job.finished_at=None
        job.error_code=None
        return wire(job)
    return write(db,user,request,key,data.model_dump(),apply)


@router.post("/statements",operation_id="D01",status_code=202)
def upload_statement(user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key,
    file: Annotated[UploadFile,File()],source_id: Annotated[UUID,Form()],business_id: Annotated[UUID,Form()]):
    content,mime=upload_content(file,settings,"statement")
    def apply():
        owned(db,Business,user.id,business_id)
        if source_id not in SOURCES: raise HTTPException(422,"Unknown source")
        stored=store_file(db,user.id,content,mime)
        if db.scalar(rows(db,Statement,user.id).where(Statement.file_id==stored.id)): raise HTTPException(409,"Statement file already uploaded")
        row=Statement(owner_id=user.id,business_id=business_id,source_id=source_id,file_id=stored.id)
        db.add(row)
        db.flush()
        job=Job(owner_id=user.id,kind="statement_parse",resource_id=row.id)
        db.add(job)
        db.flush()
        row.job_id=job.id
        return {"statement":statement_wire(db,row),"job":wire(job)}
    return write(db,user,request,key,{"sha256":hashlib.sha256(content).hexdigest(),"source":str(source_id),"business":str(business_id)},apply)


@router.get("/statements",operation_id="D02")
def statements(tax_year: str,user: CurrentUser,db: SessionDep,settings: SettingsDep,source_id: UUID|None=None,
               limit: Limit=50,cursor: str|None=None):
    start,end=tax_dates(tax_year)
    from sqlalchemy import or_
    query=rows(db,Statement,user.id).where(or_(Statement.period_start.is_(None),
        (Statement.period_start<=end)&(Statement.period_end>=start)))
    if source_id: query=query.where(Statement.source_id==source_id)
    return page(db,query,Statement,user.id,settings,limit,cursor,filters={"year":tax_year,"source":source_id},serializer=lambda r:statement_wire(db,r))


@router.get("/statements/{id}",operation_id="D03",response_model=StatementRead)
def statement(id: UUID,user: CurrentUser,db: SessionDep):
    return statement_wire(db,owned(db,Statement,user.id,id))


class ImportInput(Versioned):
    acknowledged_warning_codes: list[str]=[]


@router.post("/statements/{id}/imports",operation_id="D04")
def import_statement(id: UUID,data: ImportInput,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Statement,user.id,id)
        check_version(row,data.expected_version)
        if row.processing_status!="ready" or row.import_status not in {"preview","reversed"}: raise HTTPException(409,"Statement is not an importable preview")
        overlap=db.scalar(rows(db,Statement,user.id).where(Statement.id!=id,Statement.source_id==row.source_id,
            Statement.business_id==row.business_id,Statement.import_status=="imported",Statement.period_start<=row.period_end,
            Statement.period_end>=row.period_start))
        if overlap: raise HTTPException(409,"Statement overlaps an imported period")
        # Existing manual income is reconciled instead of posting a second copy.
        candidates=list(db.scalars(rows(db,Transaction,user.id).where(Transaction.business_id==row.business_id,
            Transaction.source_id==row.source_id,
            or_(Transaction.kind=="income",(Transaction.kind=="expense")&(Transaction.category_id==catalog_id("category","platform_fees"))),
            Transaction.review_status=="confirmed",
            Transaction.occurred_on.between(row.period_start,row.period_end))))
        posted=[]
        if candidates:
            issue=db.scalar(rows(db,Issue,user.id).where(Issue.statement_id==id))
            if issue is None:
                issue=Issue(owner_id=user.id,statement_id=id)
                db.add(issue)
            else:
                issue.status="open"
                issue.version+=1
        else:
            for payout in row.payouts:
                occurred=date.fromisoformat(payout["occurred_on"])
                for kind,amount,category in [("income",payout["gross_pence"],None),("expense",payout["fee_pence"],catalog_id("category","platform_fees"))]:
                    if amount==0: continue
                    origin=f"{row.source_id}:{payout['id']}:{kind}"
                    if db.scalar(rows(db,Transaction,user.id).where(Transaction.import_origin_key==origin)):
                        raise HTTPException(409,"Payout row already imported")
                    tx=new_transaction(db,user.id,TransactionInput(kind=kind,amount_pence=amount,occurred_on=occurred,
                        business_id=row.business_id,source_id=row.source_id,category_id=category,description="Statement "+payout["id"]),origin=origin)
                    posted.append(wire(tx))
        row.import_status="imported"
        row.version+=1
        mutation=history(db,row,"statement_import")
        from app.models.books import Mutation
        action=db.get(Mutation,mutation)
        action.after={**action.after,"posting_effects":[{"id":r["id"],"version":r["version"]} for r in posted]}
        return {"statement":statement_wire(db,row),"transactions":posted,"reconciliation_required":bool(candidates)}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/statements/{id}/reversals")
def reverse_statement_import(id: UUID,data: Reversal,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Statement,user.id,id)
        action=exact_mutation(db,row,data)
        if action.action!="statement_import" or row.import_status!="imported": raise HTTPException(409,"Reverse the exact statement import action")
        issue=db.scalar(rows(db,Issue,user.id).where(Issue.statement_id==id))
        if issue and issue.status=="resolved": raise HTTPException(409,"Reverse the reconciliation resolution before reversing its import")
        for effect in action.after.get("posting_effects",[]):
            tx=owned(db,Transaction,user.id,UUID(effect["id"]))
            check_version(tx,effect["version"])
            ensure_open_period(db,user.id,tx.business_id,tx.occurred_on)
            before=wire(tx)
            tx.review_status="reversed"
            tx.import_origin_key="reversed:"+str(tx.id)
            tx.version+=1
            history(db,tx,"statement_import_reversal",before,data.reason)
        before=wire(row)
        row.import_status="reversed"
        row.version+=1
        if issue: issue.status="cancelled"
        action.reversed_by=history(db,row,"import_reversal",before,data.reason)
        return statement_wire(db,row)
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/statements/{id}/content",operation_id="D05")
def statement_content(id: UUID,user: CurrentUser,db: SessionDep):
    return private_download(db,user.id,owned(db,Statement,user.id,id).file_id)
