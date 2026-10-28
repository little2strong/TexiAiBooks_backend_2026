from datetime import timedelta
from typing import Annotated
from uuid import UUID, NAMESPACE_URL, uuid5

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.documents import private_download
from app.api.ledger import Limit
from app.api.profiles import Key
from app.models.books import Export, Job, Notification, PrivateFile, Receipt, SupportRecord
from app.models.common import utc_now
from app.schemas.books import AccountantInput, Body, ExportInput, ReadAll, ReadState
from app.services.books import history, owned, page, rows, tax_dates, wire, write
from app.services.ledger import ledger_rows, mileage_total

router=APIRouter(tags=["notifications exports subscriptions support"])


def unread(db,owner):
    return db.scalar(select(func.count()).select_from(Notification).where(Notification.owner_id==owner,Notification.read_at.is_(None)))


@router.get("/notifications",operation_id="N01")
def notifications(user: CurrentUser,db: SessionDep,settings: SettingsDep,unread_only: bool=False,limit: Limit=50,cursor: str|None=None):
    query=rows(db,Notification,user.id)
    if unread_only: query=query.where(Notification.read_at.is_(None))
    return {**page(db,query,Notification,user.id,settings,limit,cursor,filters={"unread":unread_only}),"unread_count":unread(db,user.id)}


@router.patch("/notifications/{id}",operation_id="N02")
def read_notification(id: UUID,data: ReadState,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        row=owned(db,Notification,user.id,id)
        row.read_at=utc_now() if data.read else None
        return wire(row)
    return write(db,user,request,key,data.model_dump(),apply)


@router.post("/notifications/read-all",operation_id="N03")
def read_all(data: ReadAll,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        matching=list(db.scalars(rows(db,Notification,user.id).where(Notification.created_at<=data.through,Notification.read_at.is_(None))))
        for row in matching: row.read_at=utc_now()
        db.flush()
        return {"updated_count":len(matching),"unread_count":unread(db,user.id)}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


def export_wire(db,row):
    job=owned(db,Job,row.owner_id,row.job_id)
    return {"id":row.id,"tax_year":row.tax_year,"format":row.format,"include_photos":row.include_photos,
            "status":job.status,"job":wire(job),"expires_at":row.expires_at,
            "download_ready":job.status=="succeeded" and row.file_id is not None and row.expires_at>utc_now()}


@router.post("/exports",operation_id="E01",status_code=202)
def create_export(data: ExportInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    def apply():
        require_entitlement(db,user,settings,"exports")
        tax_dates(data.tax_year)
        records=ledger_rows(db,user.id,data.tax_year)
        snapshot=[{**wire(r),"record_type":"transaction"} for r in records]
        mileage=mileage_total(db,user.id,data.tax_year)
        if mileage["deduction_pence"]:
            _,year_end=tax_dates(data.tax_year)
            snapshot.append({"id":str(uuid5(NAMESPACE_URL,f"taxiaibooks:mileage-export:{user.id}:{data.tax_year}")),
                "kind":"expense","record_type":"derived_mileage_deduction","occurred_on":str(year_end),
                "amount_pence":mileage["deduction_pence"],"deductible_pence":mileage["deduction_pence"],
                "claim_status":"claimable","description":"Derived mileage deduction; not cash expenditure; miles="+mileage["business_miles"]})
        photos=[]
        if data.include_photos:
            for record in records:
                if record.receipt_id:
                    receipt=owned(db,Receipt,user.id,record.receipt_id)
                    file=owned(db,PrivateFile,user.id,receipt.file_id)
                    if file.scan_status!="clean": raise HTTPException(409,"Scan all receipt attachments before packaging photos")
                    photos.append(str(file.id))
        row=Export(owner_id=user.id,tax_year=data.tax_year,format=data.format,include_photos=data.include_photos,
            snapshot=snapshot,photo_ids=sorted(set(photos)),expires_at=utc_now()+timedelta(hours=settings.export_expire_hours))
        db.add(row)
        db.flush()
        job=Job(owner_id=user.id,kind="export",resource_id=row.id)
        db.add(job)
        db.flush()
        row.job_id=job.id
        return export_wire(db,row)
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/exports/{id}",operation_id="E02")
def export_detail(id: UUID,user: CurrentUser,db: SessionDep):
    return export_wire(db,owned(db,Export,user.id,id))


@router.get("/exports/{id}/download",operation_id="E03")
def download_export(id: UUID,user: CurrentUser,db: SessionDep):
    row=owned(db,Export,user.id,id)
    if row.expires_at<=utc_now(): raise HTTPException(410,"Export expired; generate a new snapshot")
    if not row.file_id or owned(db,Job,user.id,row.job_id).status!="succeeded": raise HTTPException(409,"Export is not ready")
    response=private_download(db,user.id,row.file_id)
    response.headers["Content-Disposition"]=f'attachment; filename="books-{row.tax_year}.{ "zip" if row.include_photos else row.format}"'
    return response


@router.post("/accountant-requests",operation_id="H01",status_code=201)
def accountant(data: AccountantInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    def apply():
        if data.recipient_reference not in settings.accountant_recipients:
            raise HTTPException(422,"Select a configured verified accountant recipient")
        if data.kind=="books_handoff" and not data.export_id: raise HTTPException(422,"Books handoff requires an export")
        if data.export_id:
            export=owned(db,Export,user.id,data.export_id)
            if not export_wire(db,export)["download_ready"]: raise HTTPException(409,"Export must be ready and unexpired")
        row=SupportRecord(owner_id=user.id,kind="accountant_request",data={**data.model_dump(mode="json"),
            "status":"requested","delivered":False})
        db.add(row)
        history(db,row,"consented_request")
        return {"id":row.id,**row.data,"created_at":row.created_at}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/accountant-requests/{id}",operation_id="H02")
def accountant_request(id: UUID,user: CurrentUser,db: SessionDep):
    row=owned(db,SupportRecord,user.id,id)
    if row.kind!="accountant_request": raise HTTPException(404,"Request not found")
    return {"id":row.id,**row.data,"created_at":row.created_at}


@router.get("/subscription-plans",operation_id="S01")
def plans(settings: SettingsDep,locale: str="en"):
    # Approved offers are external configuration; marketing fixture prices never become billing contracts.
    return settings.subscription_plans


def subscription_record(db,owner):
    return db.scalar(rows(db,SupportRecord,owner).where(SupportRecord.kind=="subscription").order_by(SupportRecord.created_at.desc()))


@router.get("/me/subscription",operation_id="S02")
def subscription(user: CurrentUser,db: SessionDep):
    row=subscription_record(db,user.id)
    if row is None: return {"status":"none","entitlements":[]}
    values={"id":row.id,**row.data}
    if values["status"]=="trialing" and __import__("datetime").datetime.fromisoformat(values["trial_end"])<=utc_now():
        values["status"]="trial_expired"
        values["entitlements"]=[]
    return values


def require_entitlement(db,user,settings,feature):
    requirement=settings.entitlement_requirements.get(feature)
    if requirement and requirement not in subscription(user,db).get("entitlements",[]):
        raise HTTPException(403,"Subscription entitlement required")


class TrialInput(Body):
    plan_id: UUID
    terms_version: str


@router.post("/me/subscription/trial",operation_id="S03",status_code=201)
def trial(data: TrialInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    def apply():
        plan=next((p for p in settings.subscription_plans if str(p["id"])==str(data.plan_id)),None)
        if plan is None: raise HTTPException(503,"Approved subscription plan is not configured")
        if plan["terms_version"]!=data.terms_version: raise HTTPException(409,"Plan terms changed")
        if subscription_record(db,user.id): raise HTTPException(409,"Trial already used or subscription exists")
        now=utc_now()
        row=SupportRecord(owner_id=user.id,kind="subscription",data={"plan":plan,"status":"trialing",
            "trial_start":now.isoformat(),"trial_end":(now+timedelta(days=plan["trial_days"])).isoformat(),
            "price_locked_pence":None,"entitlements":plan.get("entitlements",[]),"provider":None})
        db.add(row)
        history(db,row,"trial")
        return {"id":row.id,**row.data}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)
