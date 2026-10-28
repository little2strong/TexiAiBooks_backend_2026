from datetime import date, timedelta
import hmac
import secrets
from typing import Literal
from uuid import UUID, NAMESPACE_URL, uuid4, uuid5

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field
from sqlalchemy import select, text

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.api.ledger import Limit
from app.api.profiles import Key
from app.api.support import subscription_record, require_entitlement
from app.core.security import hash_secret
from app.models.books import Business, Profile, SupportRecord, Transaction
from app.models.common import utc_now
from app.schemas.books import Body, NonnegativeMoney, Versioned
from app.services.auth_security import rate_limit
from app.services.books import digest, history, owned, page, profile, rows, tax_dates, wire, write
from app.services.integrations import provider, safe_call
from app.services.ledger import ledger_rows, mileage_total, totals
from app.services.sessions import lock_user
from app.services.tax import rule_set
from app.services.vault import decrypt, encrypt
from app.schemas.results import MessageRead, MessagePair, Page

router=APIRouter(tags=["external integrations"])


class Checkout(Body):
    plan_id: UUID
    return_route: Literal["subscription"]


class Cancellation(Body):
    reason: str|None=Field(default=None,max_length=500)


@router.post("/me/subscription/checkout",operation_id="S05")
def checkout(data: Checkout,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    adapter=provider(request,"billing_provider")
    def apply():
        plan=next((p for p in settings.subscription_plans if str(p["id"])==str(data.plan_id)),None)
        if plan is None: raise HTTPException(422,"Unknown approved plan")
        return safe_call(adapter.checkout,str(user.id),plan,data.return_route,str(key))
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/me/subscription/cancellation",operation_id="S06")
def cancel(data: Cancellation,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    adapter=provider(request,"billing_provider")
    def apply():
        row=subscription_record(db,user.id)
        if not row: raise HTTPException(404,"Subscription not found")
        result=safe_call(adapter.cancel,row.data,data.reason,str(key))
        if result.get("status") not in {"cancelled","active"}: raise HTTPException(503,"Invalid provider cancellation outcome")
        outcome={key:value for key,value in result.items() if key in {"status","renew_at","cancel_at_period_end"}}
        row.data={**row.data,**outcome,"entitlements":[] if result["status"]=="cancelled" else row.data.get("entitlements",[])}
        row.version+=1
        history(db,row,"provider_cancellation")
        return {"id":row.id,**row.data}
    return write(db,user,request,key,data.model_dump(),apply)


@router.post("/billing/webhooks/{provider_name}",operation_id="S04")
async def billing_event(provider_name: str,request: Request,db: SessionDep):
    adapter=provider(request,"billing_provider")
    event=safe_call(adapter.verify_event,await request.body(),dict(request.headers))
    # Signature/provider-specific verification occurs before any data access or acknowledgement.
    required={"event_id","owner_id","status","provider","subscription_reference","sequence"}
    if not required<=event.keys() or event["provider"]!=provider_name or event["status"] not in {"active","past_due","cancelled"}:
        raise HTTPException(422,"Invalid verified billing event")
    try:
        owner=UUID(event["owner_id"])
        sequence=int(event["sequence"])
        if sequence<0: raise ValueError()
    except (ValueError,TypeError): raise HTTPException(422,"Invalid verified billing event") from None
    from app.models import User
    if db.get(User,owner) is None: raise HTTPException(422,"Unknown billing customer")
    lock_user(db,owner)
    previous=db.scalar(rows(db,SupportRecord,owner).where(SupportRecord.kind=="billing_event",SupportRecord.data["event_id"].astext==event["event_id"]))
    if previous: return {"received":True}
    row=subscription_record(db,owner)
    if row is None: raise HTTPException(409,"No server-approved subscription exists")
    if sequence>row.data.get("provider_sequence",-1):
        entitlements=row.data["plan"].get("entitlements",[]) if event["status"]=="active" else []
        row.data={**row.data,"status":event["status"],"entitlements":entitlements,"provider":provider_name,
            "subscription_reference":event["subscription_reference"],"provider_sequence":sequence}
        row.version+=1
    db.add(SupportRecord(owner_id=owner,kind="billing_event",data={"event_id":event["event_id"],"provider":provider_name}))
    db.commit()
    return {"received":True}


def support(db,owner,id,kind):
    row=owned(db,SupportRecord,owner,id)
    if row.kind!=kind: raise HTTPException(404,"Resource not found")
    return row


class ConversationInput(Body):
    locale: Literal["en","ur","bn","pa","pl","ro","ar"]="en"
    context_resource_ids: list[UUID]=Field(default_factory=list,max_length=50)
    consent_version: str=Field(min_length=1,max_length=100)


class MessageInput(Body):
    content: str=Field(min_length=1,max_length=4000)
    client_message_id: UUID


@router.post("/assistant/conversations",operation_id="B01",status_code=201)
def conversation(data: ConversationInput,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        for id in data.context_resource_ids: owned(db,Transaction,user.id,id)
        row=SupportRecord(owner_id=user.id,kind="conversation",data=data.model_dump(mode="json"))
        db.add(row)
        db.flush()
        return {"id":row.id,"locale":data.locale,"created_at":row.created_at}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.post("/assistant/conversations/{id}/messages",operation_id="B02",response_model=MessagePair)
def message(id: UUID,data: MessageInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    adapter=provider(request,"assistant_provider")
    rate_limit(db,settings,request,"assistant",str(user.id),target_limit=20,ip_limit=60)
    def apply():
        conversation=support(db,user.id,id,"conversation")
        require_entitlement(db,user,settings,"assistant")
        existing=db.scalar(rows(db,SupportRecord,user.id).where(SupportRecord.kind=="message",
            SupportRecord.data["conversation_id"].astext==str(id),SupportRecord.data["client_message_id"].astext==str(data.client_message_id)))
        if existing:
            if existing.data["content"]!=data.content: raise HTTPException(409,"Client message ID reused with changed content")
            return existing.data["result"]
        # Context is limited to these explicitly consented ledger records, never tax identifiers.
        context=[]
        for resource_id in conversation.data["context_resource_ids"]:
            tx=owned(db,Transaction,user.id,UUID(resource_id))
            context.append({k:wire(tx)[k] for k in ("id","kind","occurred_on","amount_pence","deductible_pence")})
        previous=list(db.scalars(rows(db,SupportRecord,user.id).where(SupportRecord.kind=="message",
            SupportRecord.data["conversation_id"].astext==str(id)).order_by(SupportRecord.created_at.desc()).limit(20)))
        prompts=[{"role":"user","content":r.data["content"]} for r in reversed(previous)]+[{"role":"user","content":data.content}]
        try:
            response=adapter.respond(prompts,context,conversation.data["locale"])
            if not isinstance(response.get("content"),str) or not response["content"]: raise ValueError()
            answer={"id":str(uuid4()),"conversation_id":str(id),"role":"assistant","content":response["content"],
                    "sources":response.get("sources",[]),"status":"complete","created_at":utc_now().isoformat()}
            answer=MessageRead(**answer).model_dump(mode="json")
        except Exception:
            answer={"id":str(uuid4()),"conversation_id":str(id),"role":"assistant","content":"",
                    "sources":[],"status":"failed","created_at":utc_now().isoformat(),"error_code":"assistant_unavailable"}
        row=SupportRecord(owner_id=user.id,kind="message",data={"conversation_id":str(id),"content":data.content,
            "client_message_id":str(data.client_message_id)})
        db.add(row)
        db.flush()
        result={"user_message":{"id":str(row.id),"conversation_id":str(id),"role":"user","content":data.content,"status":"complete"},
                "assistant_message":answer}
        result["user_message"]["created_at"]=row.created_at.isoformat()
        row.data={**row.data,"result":result}
        return result
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/assistant/conversations/{id}/messages",operation_id="B03",response_model=Page[MessagePair])
def messages(id: UUID,user: CurrentUser,db: SessionDep,settings: SettingsDep,limit: Limit=50,cursor: str|None=None):
    support(db,user.id,id,"conversation")
    query=rows(db,SupportRecord,user.id).where(SupportRecord.kind=="message",SupportRecord.data["conversation_id"].astext==str(id))
    return page(db,query,SupportRecord,user.id,settings,limit,cursor,filters={"conversation":id},serializer=lambda r:r.data["result"])


@router.get("/mtd/eligibility",operation_id="U01")
def eligibility(tax_year: str,user: CurrentUser,db: SessionDep,request: Request):
    start,end=tax_dates(tax_year)
    qualifying=f"{start.year-2}-{(start.year-1)%100:02d}"
    evidence=profile(db,user.id,"mtd_qualifying",qualifying)
    adapter=getattr(request.app.state,"hmrc_provider",None)
    threshold={2026:5000000,2027:3000000,2028:2000000}.get(start.year)
    return {"status":("exempt" if evidence.data.get("exempt") else "eligible" if evidence.data["income_pence"]>threshold else "not_required")
            if evidence and threshold else "unknown", "qualifying_tax_year":qualifying,
        "qualifying_income_pence":evidence.data["income_pence"] if evidence else None,"start_on":start,
        "reasons":["user_reported_qualifying_income"] if evidence else ["prior_qualifying_income_and_exemption_evidence_required"],
        "rule_set_id":str(uuid5(NAMESPACE_URL,"taxiaibooks:mtd:2026-10-27.1")),
        "official_url":"https://www.gov.uk/guidance/find-out-if-and-when-you-need-to-use-making-tax-digital-for-income-tax",
        "verified_at":"2026-10-27T00:00:00Z", "connection_status":"connected" if profile(db,user.id,"mtd_connection") else "disconnected",
        "recognition_enabled":bool(adapter and adapter.recognition_enabled)}


class QualifyingInput(Body):
    income_pence: NonnegativeMoney
    exempt: bool=False
    evidence_reference: str=Field(min_length=1,max_length=200)


@router.put("/mtd/qualifying-income")
def qualifying_income(tax_year: str,data: QualifyingInput,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        tax_dates(tax_year)
        row=profile(db,user.id,"mtd_qualifying",tax_year,create=True)
        row.data=data.model_dump()
        row.version+=1
        return {**row.data,"version":row.version}
    return write(db,user,request,key,data.model_dump(),apply)


class AuthorizationInput(Body):
    return_route: Literal["mtd"]


@router.post("/mtd/authorizations",operation_id="U02")
def authorize(data: AuthorizationInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    adapter=provider(request,"hmrc_provider")
    def apply():
        state=secrets.token_urlsafe(32)
        expires=utc_now()+timedelta(minutes=5)
        url=safe_call(adapter.authorization_url,state,data.return_route)
        row=SupportRecord(owner_id=user.id,kind="mtd_oauth",data={"state_hash":hash_secret("mtd_state:"+state,settings),
            "expires_at":expires.isoformat(),"used":False})
        db.add(row)
        return {"authorization_url":url,"state_expires_at":expires}
    # URLs can contain OAuth state, but never provider tokens; idempotency replay is private.
    return write(db,user,request,key,data.model_dump(),apply)


@router.get("/mtd/oauth/callback",operation_id="U03")
def oauth_callback(code: str,state: str,db: SessionDep,settings: SettingsDep,request: Request):
    adapter=provider(request,"hmrc_provider")
    state_hash=hash_secret("mtd_state:"+state,settings)
    record=db.scalar(select(SupportRecord).where(SupportRecord.kind=="mtd_oauth",SupportRecord.data["state_hash"].astext==state_hash))
    if not record: raise HTTPException(400,"Invalid OAuth state")
    lock_user(db,record.owner_id)
    db.refresh(record)
    from datetime import datetime
    if record.data["used"] or datetime.fromisoformat(record.data["expires_at"])<=utc_now(): raise HTTPException(400,"Invalid OAuth state")
    tokens=safe_call(adapter.exchange,code)
    row=profile(db,record.owner_id,"mtd_connection",create=True)
    row.identifiers=encrypt(settings,tokens)
    row.data={"status":"connected"}
    record.data={**record.data,"used":True}
    db.commit()
    return {"connection_status":"connected"}


def connection(db,owner,settings):
    row=profile(db,owner,"mtd_connection")
    if not row or not row.identifiers: raise HTTPException(409,"Connect HMRC first")
    return decrypt(settings,row.identifiers)


@router.get("/mtd/businesses",operation_id="U04")
def businesses(user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request):
    adapter=provider(request,"hmrc_provider")
    verified=safe_call(adapter.businesses,connection(db,user.id,settings))
    # Provider must map verified external businesses onto owner-local IDs; never create property books from UI fixtures.
    result=[]
    for item in verified:
        business=owned(db,Business,user.id,UUID(item["business_id"]))
        result.append({"id":business.id,"type":business.kind,"name":business.name,
                       "provider_business_id_masked":str(item["provider_id"])[-4:].rjust(8,"*")})
    return result


@router.get("/mtd/obligations",operation_id="U05")
def obligations(tax_year: str,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,business_id: UUID|None=None):
    tax_dates(tax_year)
    adapter=provider(request,"hmrc_provider")
    data=safe_call(adapter.obligations,connection(db,user.id,settings),tax_year)
    lock_user(db,user.id)
    result=[]
    for item in data:
        business=owned(db,Business,user.id,UUID(item["business_id"]))
        if business_id and business.id!=business_id: continue
        start,end=date.fromisoformat(item["period_start"]),date.fromisoformat(item["period_end"])
        if end<start: raise HTTPException(503,"Invalid provider obligation dates")
        row=db.scalar(rows(db,SupportRecord,user.id).where(SupportRecord.kind=="mtd_obligation",SupportRecord.data["provider_id"].astext==item["id"]))
        if row is None:
            row=SupportRecord(owner_id=user.id,kind="mtd_obligation",data={})
            db.add(row)
            db.flush()
        row.data={**item,"provider_id":item["id"],"id":str(row.id),"tax_year":tax_year,"provider_verified":True}
        result.append({k:v for k,v in row.data.items() if k!="provider_id"})
    db.commit()
    return result


class PreviewInput(Body):
    obligation_ids: list[UUID]=Field(min_length=1,max_length=20)


@router.post("/mtd/previews",operation_id="U06",status_code=201)
def preview(data: PreviewInput,user: CurrentUser,db: SessionDep,request: Request,key: Key):
    def apply():
        if len(set(data.obligation_ids))!=len(data.obligation_ids): raise HTTPException(422,"Duplicate obligation")
        snapshots=[]
        for id in data.obligation_ids:
            obligation=support(db,user.id,id,"mtd_obligation")
            value=obligation.data
            if not value.get("provider_verified") or value["status"]!="open": raise HTTPException(409,"Obligation is not verified/open")
            business=owned(db,Business,user.id,UUID(value["business_id"]))
            start,end=date.fromisoformat(value["period_start"]),date.fromisoformat(value["period_end"])
            records=ledger_rows(db,user.id,value["tax_year"],as_of=end,business_id=business.id)
            quarter=[r for r in records if start<=r.occurred_on<=end]
            ytd_mileage=mileage_total(db,user.id,value["tax_year"],as_of=end,business_id=business.id)["deduction_pence"]
            earlier_mileage=mileage_total(db,user.id,value["tax_year"],as_of=start-timedelta(days=1),business_id=business.id)["deduction_pence"]
            snapshots.append({"business_id":str(business.id),"obligation_id":str(id),"tax_year":value["tax_year"],
                "quarter_income_pence":sum(r.amount_pence for r in quarter if r.kind=="income"),
                "quarter_expenses_pence":sum(r.deductible_pence for r in quarter if r.kind=="expense")+ytd_mileage-earlier_mileage,
                "ytd_income_pence":sum(r.amount_pence for r in records if r.kind=="income" and r.occurred_on<=end),
                "ytd_expenses_pence":sum(r.deductible_pence for r in records if r.kind=="expense" and r.occurred_on<=end)+ytd_mileage,
                "ledger_version":totals(db,user.id,value["tax_year"])["ledger_version"],"provider_obligation":value})
        adapter=getattr(request.app.state,"hmrc_provider",None)
        years={snapshot["tax_year"] for snapshot in snapshots}
        if len(years)!=1: raise HTTPException(422,"Preview obligations must belong to one tax year")
        if len({snapshot["business_id"] for snapshot in snapshots})!=len(snapshots):
            raise HTTPException(422,"Select one obligation per business for each preview")
        payload={"obligation_ids":list(map(str,data.obligation_ids)),"businesses":snapshots,"snapshot_hash":digest(snapshots),
            "ledger_version":digest([s["ledger_version"] for s in snapshots]),
            "warnings":["Quarterly preview excludes unimplemented capital allowances and final declaration"],
            "can_submit":bool(adapter and adapter.recognition_enabled and eligibility(next(iter(years)),user,db,request)["status"]=="eligible")}
        row=SupportRecord(owner_id=user.id,kind="mtd_preview",data=payload)
        db.add(row)
        db.flush()
        public={**payload,"businesses":[{k:v for k,v in snapshot.items() if k!="provider_obligation"} for snapshot in snapshots]}
        return {"id":row.id,**public}
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


class UpdateInput(Body):
    preview_id: UUID
    snapshot_hash: str=Field(min_length=64,max_length=64)
    consent_version: str=Field(min_length=1,max_length=100)


@router.post("/mtd/updates",operation_id="U07",status_code=202)
def submit(data: UpdateInput,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    adapter=provider(request,"hmrc_provider")
    if not adapter.recognition_enabled: raise HTTPException(503,"HMRC recognition/production submission is disabled")
    def apply():
        preview=support(db,user.id,data.preview_id,"mtd_preview")
        value=preview.data
        if not value.get("can_submit"): raise HTTPException(409,"Create a fresh submittable preview after prerequisites are ready")
        if not hmac.compare_digest(value["snapshot_hash"],data.snapshot_hash): raise HTTPException(409,"Snapshot hash mismatch")
        previous=db.scalar(rows(db,SupportRecord,user.id).where(SupportRecord.kind=="mtd_update",SupportRecord.data["preview_id"].astext==str(preview.id)))
        if previous: raise HTTPException(409,"Preview already submitted; inspect its outcomes before any retry")
        for snapshot in value["businesses"]:
            if eligibility(snapshot["tax_year"],user,db,request)["status"]!="eligible":
                raise HTTPException(409,"Qualifying-income evidence is required for this supported MTD workflow")
            obligation=support(db,user.id,UUID(snapshot["obligation_id"]),"mtd_obligation")
            if obligation.data["status"]!="open": raise HTTPException(409,"Obligation is no longer open")
            if totals(db,user.id,snapshot["tax_year"])["ledger_version"]!=snapshot["ledger_version"]:
                raise HTTPException(409,"Books changed; create a fresh preview")
        tokens=connection(db,user.id,settings)
        row=SupportRecord(owner_id=user.id,kind="mtd_update",data={"preview_id":str(preview.id),"status":"queued",
            "submitted_at":None,"business_results":[],"consent_version":data.consent_version,
            "tax_year":value["businesses"][0]["tax_year"],"confirmation_available":False})
        db.add(row)
        db.flush()
        # Submission is a durable outbox. A configured integration worker processes it;
        # HTTP handlers never make irreversible remote writes inside a DB transaction.
        return update_wire(row)
    return write(db,user,request,key,data.model_dump(mode="json"),apply)


@router.get("/mtd/updates",operation_id="U10")
def updates(tax_year: str,user: CurrentUser,db: SessionDep,settings: SettingsDep,limit: Limit=50,cursor: str|None=None):
    tax_dates(tax_year)
    query=rows(db,SupportRecord,user.id).where(SupportRecord.kind=="mtd_update",SupportRecord.data["tax_year"].astext==tax_year)
    return page(db,query,SupportRecord,user.id,settings,limit,cursor,filters={"year":tax_year,"type":"mtd"},serializer=update_wire)


@router.get("/mtd/updates/{id}",operation_id="U08")
def update_detail(id: UUID,user: CurrentUser,db: SessionDep):
    row=support(db,user.id,id,"mtd_update")
    return update_wire(row)


def update_wire(row):
    results=[]
    for item in row.data["business_results"]:
        reference=item.get("provider_reference")
        results.append({**{k:v for k,v in item.items() if k!="provider_reference"},
            "provider_reference_masked":"****"+reference[-4:] if reference else None})
    return {"id":row.id,"version":row.version,**row.data,"business_results":results}


@router.post("/mtd/updates/{id}/reconciliation")
def reconcile_update(id: UUID,data: Versioned,user: CurrentUser,db: SessionDep,settings: SettingsDep,request: Request,key: Key):
    adapter=provider(request,"hmrc_provider")
    def apply():
        from app.services.books import check_version
        from app.services.mtd import reconcile_outcomes
        row=support(db,user.id,id,"mtd_update")
        check_version(row,data.expected_version)
        reconcile_outcomes(db,user.id,row,connection(db,user.id,settings),adapter)
        return update_wire(row)
    return write(db,user,request,key,data.model_dump(),apply)


@router.get("/mtd/updates/{id}/confirmation",operation_id="U09")
def confirmation(id: UUID,user: CurrentUser,db: SessionDep):
    row=support(db,user.id,id,"mtd_update")
    accepted=[r for r in row.data["business_results"] if r["status"]=="accepted" and r.get("provider_reference")]
    if not accepted: raise HTTPException(409,"No actual accepted acknowledgement is stored")
    return {"business_references":[{"business_id":r["business_id"],"provider_reference":r["provider_reference"],
                                  "accepted_at":r["accepted_at"]} for r in accepted],"status":row.data["status"]}
