"""Durable per-business remote submission outcomes.

A crash or timeout after the durable 'submitting' marker becomes unknown and
requires provider reconciliation. This code never retries an uncertain send.
"""
from uuid import UUID
from datetime import datetime,timedelta

from sqlalchemy import select

from app.models.books import SupportRecord
from app.models.common import utc_now
from app.services.books import owned, profile, rows
from app.services.sessions import lock_user
from app.services.vault import decrypt


def process_mtd_once(factory,settings,adapter):
    recover_uncertain_submissions(factory)
    if adapter is None or not adapter.recognition_enabled: return False
    with factory() as db:
        candidate=db.scalar(select(SupportRecord).where(SupportRecord.kind=="mtd_update",
            SupportRecord.data["status"].astext=="queued").order_by(SupportRecord.created_at).limit(1))
        if candidate is None: return False
        owner,id=candidate.owner_id,candidate.id
        lock_user(db,owner)
        db.refresh(candidate)
        if candidate.data["status"]!="queued": return True
        preview=owned(db,SupportRecord,owner,UUID(candidate.data["preview_id"]))
        snapshots=preview.data["businesses"]
        connection=profile(db,owner,"mtd_connection")
        tokens=decrypt(settings,connection.identifiers)
        candidate.data={**candidate.data,"status":"submitting","submitted_at":utc_now().isoformat()}
        candidate.version+=1
        db.commit()
    results=[]
    for snapshot in snapshots:
        # Intent committed before calling a remote endpoint; process loss leaves a
        # visible submitting state, never a queued record that can be resent.
        try:
            result=adapter.submit(tokens,snapshot["provider_obligation"],snapshot)
            if result.get("status") not in {"accepted","rejected","unknown"}: raise ValueError()
            if result["status"]=="accepted" and not result.get("provider_reference"): raise ValueError()
            safe={"business_id":snapshot["business_id"],"status":result["status"],
                "provider_reference":result.get("provider_reference"),
                "accepted_at":utc_now().isoformat() if result["status"]=="accepted" else None,
                "error_code":result.get("error_code")}
        except Exception:
            safe={"business_id":snapshot["business_id"],"status":"unknown","provider_reference":None,
                  "accepted_at":None,"error_code":"remote_outcome_unknown"}
        results.append(safe)
        with factory() as db:
            lock_user(db,owner)
            row=owned(db,SupportRecord,owner,id)
            statuses={r["status"] for r in results}
            complete=len(results)==len(snapshots)
            status=("accepted" if statuses=={"accepted"} else "partial" if "accepted" in statuses else
                    "unknown" if "unknown" in statuses else "rejected") if complete else "submitting"
            row.data={**row.data,"status":status,"business_results":list(results),
                "confirmation_available":any(r["status"]=="accepted" for r in results)}
            row.version+=1
            db.commit()
    return True


def recover_uncertain_submissions(factory):
    """A lost worker cannot establish whether HMRC received its request."""
    with factory() as db:
        candidates=list(db.scalars(select(SupportRecord).where(SupportRecord.kind=="mtd_update",
            SupportRecord.data["status"].astext=="submitting")))
        for row in candidates:
            if datetime.fromisoformat(row.data["submitted_at"])+timedelta(minutes=5)>utc_now(): continue
            lock_user(db,row.owner_id)
            db.refresh(row)
            if row.data["status"]!="submitting": continue
            preview=owned(db,SupportRecord,row.owner_id,UUID(row.data["preview_id"]))
            results=list(row.data["business_results"])
            completed={r["business_id"] for r in results}
            for snapshot in preview.data["businesses"]:
                if snapshot["business_id"] not in completed:
                    results.append({"business_id":snapshot["business_id"],"status":"unknown","provider_reference":None,
                        "accepted_at":None,"error_code":"worker_lost_remote_outcome_unknown"})
            row.data={**row.data,"business_results":results,"status":"partial" if any(r["status"]=="accepted" for r in results) else "unknown"}
            row.version+=1
            db.commit()


def reconcile_outcomes(db,owner,row,tokens,adapter):
    from fastapi import HTTPException
    if row.data["status"] not in {"unknown","partial"}: raise HTTPException(409,"Update has no uncertain results to reconcile")
    preview=owned(db,SupportRecord,owner,UUID(row.data["preview_id"]))
    snapshots={s["business_id"]:s for s in preview.data["businesses"]}
    results=[]
    for item in row.data["business_results"]:
        if item["status"]!="unknown":
            results.append(item)
            continue
        snapshot=snapshots[item["business_id"]]
        try:
            result=adapter.reconcile(tokens,snapshot["provider_obligation"],snapshot)
            if result.get("status") not in {"accepted","rejected","unknown"}: raise ValueError()
            if result["status"]=="accepted" and not result.get("provider_reference"): raise ValueError()
        except Exception:
            raise HTTPException(503,"Provider reconciliation unavailable; outcome remains uncertain") from None
        results.append({"business_id":item["business_id"],"status":result["status"],
            "provider_reference":result.get("provider_reference"),"error_code":result.get("error_code"),
            "accepted_at":utc_now().isoformat() if result["status"]=="accepted" else None})
    statuses={r["status"] for r in results}
    state="accepted" if statuses=={"accepted"} else "partial" if "accepted" in statuses else "unknown" if "unknown" in statuses else "rejected"
    row.data={**row.data,"business_results":results,"status":state,"confirmation_available":"accepted" in statuses}
    row.version+=1
