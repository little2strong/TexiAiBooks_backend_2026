"""Private PostgreSQL blob store and real processing adapters."""
import csv
from datetime import date
from decimal import Decimal
import hashlib
from io import StringIO, BytesIO
import json
import re
import socket
import struct
import zlib
from typing import Protocol
from uuid import UUID
import zipfile

from fastapi import HTTPException
from sqlalchemy import select

from app.models.books import Export, Issue, Job, Notification, PrivateFile, Receipt, Statement, SupportRecord, Transaction
from app.models.common import utc_now
from app.schemas.books import Money
from app.services.books import digest, owned, rows, wire
from app.services.sessions import lock_user


class ProcessingFailure(Exception):
    def __init__(self, code, retryable=True):
        self.code, self.retryable = code, retryable


class OCRProvider(Protocol):
    def extract(self, content: bytes, mime_type: str) -> dict: ...


class Scanner(Protocol):
    def scan(self, content: bytes) -> None: ...


class DisabledScanner:
    def scan(self, content):
        raise ProcessingFailure("scanner_not_configured")


class DisabledOCR:
    def extract(self, content, mime_type):
        raise ProcessingFailure("ocr_not_configured")


class ClamAVScanner:
    """ClamAV INSTREAM. A non-OK response is never treated as clean."""
    def __init__(self, host, port):
        self.host, self.port = host, port

    def scan(self, content):
        try:
            with socket.create_connection((self.host,self.port),timeout=15) as sock:
                sock.sendall(b"zINSTREAM\0")
                for offset in range(0,len(content),65536):
                    chunk=content[offset:offset+65536]
                    sock.sendall(struct.pack(">I",len(chunk))+chunk)
                sock.sendall(struct.pack(">I",0))
                response=b""
                while b"\0" not in response and len(response)<4096:
                    chunk=sock.recv(4096)
                    if not chunk: break
                    response+=chunk
            if not response.rstrip(b"\0\r\n").endswith(b": OK"):
                raise ProcessingFailure("malware_or_scan_rejected",False)
        except (OSError,TimeoutError):
            raise ProcessingFailure("scanner_unavailable") from None


def validate_file(content, supplied_mime, kind):
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime="image/png"
        try:
            offset=8
            found=set()
            while offset<len(content):
                length=struct.unpack(">I",content[offset:offset+4])[0]
                tag=content[offset+4:offset+8]
                data=content[offset+8:offset+8+length]
                crc=struct.unpack(">I",content[offset+8+length:offset+12+length])[0]
                if len(data)!=length or zlib.crc32(tag+data)!=crc: raise ValueError()
                if tag==b"IHDR":
                    width,height=struct.unpack(">II",data[:8])
                    if length!=13 or not 0<width*height<=40_000_000: raise ValueError()
                found.add(tag)
                offset+=12+length
                if tag==b"IEND": break
            if not {b"IHDR",b"IDAT",b"IEND"}<=found or offset!=len(content): raise ValueError()
        except (ValueError,struct.error,OverflowError):
            raise HTTPException(422,"Invalid or oversized PNG image") from None
    elif content.startswith(b"\xff\xd8\xff"):
        mime="image/jpeg"
        if len(content)<32 or not content.endswith(b"\xff\xd9"):
            raise HTTPException(422,"Invalid JPEG image")
    elif content.startswith(b"%PDF-"):
        mime="application/pdf"
        if len(content)<32 or b"%%EOF" not in content[-1024:]:
            raise HTTPException(422,"Invalid PDF document")
    else:
        try:
            text=content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422,"Unsupported file signature") from None
        if kind!="statement" or not text.startswith("period_start,period_end,occurred_on,gross_pence,fee_pence,net_pence,adjustment_pence"):
            raise HTTPException(422,"Unsupported file signature or CSV schema")
        mime="text/csv"
    if supplied_mime not in {mime,"application/octet-stream"}:
        raise HTTPException(422,"Content type does not match file signature")
    if kind=="statement" and mime not in {"application/pdf","text/csv"}:
        raise HTTPException(422,"Statements require PDF or canonical CSV")
    return mime


def store_file(db,owner,content,mime,scan_status="pending"):
    fingerprint=hashlib.sha256(content).hexdigest()
    item=db.scalar(rows(db,PrivateFile,owner).where(PrivateFile.sha256==fingerprint))
    if item is None:
        item=PrivateFile(owner_id=owner,sha256=fingerprint,mime_type=mime,content=content,
                         size_bytes=len(content),scan_status=scan_status)
        db.add(item)
        db.flush()
    return item


class CanonicalCSVParser:
    """Documented interchange format, not an alleged Uber/Bolt PDF parser."""
    version="canonical-csv-v1"
    def parse(self,content,mime_type):
        if mime_type!="text/csv": raise ProcessingFailure("unsupported_statement_format",False)
        try:
            reader=csv.DictReader(StringIO(content.decode("utf-8-sig")))
            expected={"period_start","period_end","occurred_on","gross_pence","fee_pence","net_pence","adjustment_pence","external_id"}
            if set(reader.fieldnames or [])!=expected: raise ValueError()
            payouts=[]
            seen=set()
            for index,row in enumerate(reader):
                if index>=10000 or None in row: raise ValueError()
                start,end,occurred=[date.fromisoformat(row[k]) for k in ("period_start","period_end","occurred_on")]
                if not start<=occurred<=end: raise ValueError()
                amounts={k:int(row[k]) for k in ("gross_pence","fee_pence","net_pence","adjustment_pence")}
                if any(re.fullmatch(r"-?[0-9]{1,13}",row[k]) is None for k in amounts): raise ValueError()
                if amounts["gross_pence"]<=0 or amounts["fee_pence"]<0 or amounts["adjustment_pence"]!=0:
                    raise ProcessingFailure("unsupported_adjustment_or_refund",False)
                if amounts["gross_pence"]>9_000_000_000_000 or amounts["fee_pence"]>9_000_000_000_000:
                    raise ValueError()
                if amounts["net_pence"]!=amounts["gross_pence"]-amounts["fee_pence"]: raise ValueError()
                external_id=row["external_id"].strip()
                if not external_id or len(external_id)>100 or external_id in seen: raise ValueError()
                seen.add(external_id)
                payouts.append({"id":external_id,"period_start":str(start),"period_end":str(end),
                    "occurred_on":str(occurred),**amounts,"parser_version":self.version})
            if not payouts: raise ValueError()
            return payouts
        except (ValueError,KeyError,UnicodeDecodeError,csv.Error,TypeError):
            raise ProcessingFailure("invalid_statement_data",False) from None


def receipt_wire(db,row):
    values={**(row.extraction or {}),**row.reviewed}
    transaction=db.scalar(rows(db,Transaction,row.owner_id).where(Transaction.receipt_id==row.id))
    job=owned(db,Job,row.owner_id,row.job_id) if row.job_id else None
    return {**wire(row),**values,"transaction_id":transaction.id if transaction else None,
        "deductible_pence":transaction.deductible_pence if transaction and transaction.review_status=="confirmed" else None,
        "job":wire(job) if job else None,"warnings":values.get("warnings",[]),
        "raw_extraction":row.extraction}


def statement_wire(db,row):
    return {**wire(row),"gross_pence":sum(p["gross_pence"] for p in row.payouts),
        "fee_pence":sum(p["fee_pence"] for p in row.payouts),"net_pence":sum(p["net_pence"] for p in row.payouts),
        "warnings":[],"duplicate":False,"job":wire(owned(db,Job,row.owner_id,row.job_id)) if row.job_id else None}


def sync_receipt_draft(db,resource):
    if resource.review_status=="confirmed": return
    values={**(resource.extraction or {}),**resource.reviewed}
    if not values.get("amount_pence") or not values.get("occurred_on"): return
    from app.services.books import CATEGORIES,history
    tx=db.scalar(rows(db,Transaction,resource.owner_id).where(Transaction.receipt_id==resource.id))
    before=wire(tx) if tx else None
    if tx is None:
        tx=Transaction(owner_id=resource.owner_id,business_id=resource.business_id,kind="expense",receipt_id=resource.id)
        db.add(tx)
    else:
        if tx.review_status=="confirmed": raise HTTPException(409,"Confirmed posting cannot become a draft implicitly")
        tx.version+=1
    category=values.get("category_id") or values.get("suggested_category_id")
    category=UUID(category) if category else None
    tx.category_id=category if category in CATEGORIES else None
    tx.amount_pence=values["amount_pence"]
    tx.occurred_on=date.fromisoformat(values["occurred_on"])
    tx.description=values.get("merchant")
    tx.vehicle_id=resource.vehicle_id
    tx.currency="GBP"
    tx.review_status="draft"
    tx.claim_status=values.get("claim_status","claimable")
    tx.deductible_pence=0
    tx.business_use_percent=Decimal(values.get("business_use_percent","100"))
    tx.business_use_override="business_use_percent" in resource.reviewed
    history(db,tx,"receipt_draft",before)


def csv_export(snapshot):
    out=StringIO(newline="")
    fields=["id","record_type","kind","occurred_on","amount_pence","deductible_pence","claim_status","description"]
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction="ignore")
    writer.writeheader()
    for item in snapshot:
        safe=dict(item)
        text=safe.get("description") or ""
        if text.lstrip().startswith(("=","+","-","@","\t","\r")): text="'"+text
        safe["description"]=text
        writer.writerow(safe)
    return out.getvalue().encode("utf-8-sig")


def pdf_export(snapshot,year):
    """Minimal multipage PDF accounting table, no untrusted executable content."""
    lines=[f"TaxiAiBooks {year} - confirmed books (not a tax return)",
           "Date        Kind     Gross pence   Deductible pence"]
    lines += [f"{r['occurred_on']}  {r['kind']:7} {r['amount_pence']:12} {r['deductible_pence']:16}" for r in snapshot]
    chunks=[lines[i:i+45] for i in range(0,len(lines),45)]
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"",b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>"]
    kids=[]
    for chunk in chunks:
        page_id=len(objects)+1
        stream_id=page_id+1
        kids.append(f"{page_id} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {stream_id} 0 R >>".encode())
        commands=[b"BT /F1 9 Tf 40 750 Td 15 TL"]
        for line in chunk:
            escaped=line.replace("\\","\\\\").replace("(","\\(").replace(")","\\)")
            commands.append(f"({escaped}) Tj T*".encode("ascii","replace"))
        commands.append(b"ET")
        stream=b"\n".join(commands)
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode()+stream+b"\nendstream")
    objects[1]=f"<< /Type /Pages /Count {len(kids)} /Kids [{' '.join(kids)}] >>".encode()
    result=bytearray(b"%PDF-1.4\n")
    offsets=[0]
    for index,obj in enumerate(objects,1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode()+obj+b"\nendobj\n")
    xref=len(result)
    result.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]: result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(result)


def process_one(factory,scanner=None,ocr=None,parser=None):
    scanner,ocr,parser=scanner or DisabledScanner(),ocr or DisabledOCR(),parser or CanonicalCSVParser()
    with factory() as db:
        candidate=db.scalar(select(Job).where(Job.status=="queued").order_by(Job.created_at,Job.id).limit(1))
        if candidate is None: return False
        lock_user(db,candidate.owner_id)
        job=db.scalar(select(Job).where(Job.id==candidate.id,Job.status=="queued").with_for_update(skip_locked=True)
                      .execution_options(populate_existing=True))
        if job is None: return True
        job.status="processing"
        job.attempts+=1
        job.version+=1
        resource=None
        try:
            with db.begin_nested():
                if job.kind in {"receipt_ocr","statement_parse"}:
                    model=Receipt if job.kind=="receipt_ocr" else Statement
                    resource=owned(db,model,job.owner_id,job.resource_id)
                    file=owned(db,PrivateFile,job.owner_id,resource.file_id)
                    scanner.scan(file.content)
                    file.scan_status="clean"
                    if job.kind=="receipt_ocr":
                        extraction=ocr.extract(file.content,file.mime_type)
                        # Persist only the validated extraction contract, never arbitrary provider payloads.
                        from app.schemas.books import ReceiptExtraction
                        extraction=ReceiptExtraction(**extraction).model_dump(mode="json",exclude_none=True)
                        resource.extraction=extraction
                        db.add(SupportRecord(owner_id=job.owner_id,kind="receipt_extraction",data={
                            "receipt_id":str(resource.id),"job_id":str(job.id),"attempt":job.attempts,
                            "engine_version":getattr(ocr,"version","unreported"),"fields":extraction}))
                        resource.processing_status="ready"
                        sync_receipt_draft(db,resource)
                    else:
                        payouts=parser.parse(file.content,file.mime_type)
                        resource.payouts=payouts
                        resource.period_start=min(date.fromisoformat(p["period_start"]) for p in payouts)
                        resource.period_end=max(date.fromisoformat(p["period_end"]) for p in payouts)
                        resource.processing_status="ready"
                    resource.version+=1
                elif job.kind=="private_scan":
                    file=owned(db,PrivateFile,job.owner_id,job.resource_id)
                    scanner.scan(file.content)
                    file.scan_status="clean"
                elif job.kind=="export":
                    resource=owned(db,Export,job.owner_id,job.resource_id)
                    content=csv_export(resource.snapshot) if resource.format=="csv" else pdf_export(resource.snapshot,resource.tax_year)
                    mime="text/csv" if resource.format=="csv" else "application/pdf"
                    if resource.include_photos:
                        output=BytesIO()
                        with zipfile.ZipFile(output,"w",zipfile.ZIP_DEFLATED) as archive:
                            archive.writestr("books."+resource.format,content)
                            for photo_id in resource.photo_ids:
                                file=owned(db,PrivateFile,job.owner_id,UUID(photo_id))
                                if file.scan_status!="clean": raise ProcessingFailure("receipt_scan_incomplete")
                                extension={"image/png":"png","image/jpeg":"jpg","application/pdf":"pdf"}[file.mime_type]
                                archive.writestr(f"receipts/{file.id}.{extension}",file.content)
                        content,mime=output.getvalue(),"application/zip"
                    resource.file_id=store_file(db,job.owner_id,content,mime,"generated").id
                else: raise ProcessingFailure("unsupported_job",False)
                db.flush()
            job.status="succeeded"
            job.error_code=None
            job.retryable=False
        except Exception as exc:
            # Never persist raw provider errors, identifiers or extracted document text in error fields.
            job.status="failed"
            job.error_code=exc.code if isinstance(exc,ProcessingFailure) else "processing_failed"
            job.retryable=exc.retryable if isinstance(exc,ProcessingFailure) else True
            if resource and hasattr(resource,"processing_status"):
                resource.processing_status="failed"
                resource.version+=1
        job.finished_at=utc_now()
        db.add(Notification(owner_id=job.owner_id,type="job",title_key="job."+job.status,
            body_key="job.result",params={"job_id":str(job.id),"error_code":job.error_code},
            resource_type=job.kind,resource_id=job.resource_id))
        db.commit()
        return True
