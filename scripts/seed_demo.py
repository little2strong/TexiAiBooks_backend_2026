"""Load the synthetic demo personas into a database whose name ends in _demo.

Refuses any other database, so it cannot touch development or production records.
Every person and figure here is invented. Run after `alembic upgrade head`:

    $env:POSTGRES_DB = 'taxiaibooks_demo'; python scripts/seed_demo.py --password <12+ chars>
"""
import argparse
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import password_hash
from app.db import build_engine
from app.models import User
from app.models.books import (Business, DriverDocument, Election, Mileage, PrivacyRequest, PrivateFile, Profile,
    Receipt, SupportRecord, TaxAdjustment, TaxReturn, Transaction, Vehicle)
from app.models.common import utc_now
from app.models.staff import AccountantHandoff, AiFeedback, DriverAssignment, StaffAccount, StaffAudit, StaffEntry, TaxRate
from app.services.books import catalog_id
from app.services.tax import estimate, rule_set
from app.services.vault import encrypt

UBER, BOLT, CASH = (catalog_id("source", code) for code in ("uber", "bolt", "cash"))
YEAR, PRIOR = "2026-27", "2025-26"
FONT = {' ': [0, 0, 0, 0, 0, 0, 0], '.': [0, 0, 0, 0, 0, 12, 12], '/': [1, 2, 2, 4, 8, 8, 16], '-': [0, 0, 0, 31, 0, 0, 0], '0': [14, 17, 19, 21, 25, 17, 14], '1': [4, 12, 4, 4, 4, 4, 14], '2': [14, 17, 1, 2, 4, 8, 31], '3': [30, 1, 1, 14, 1, 1, 30], '4': [2, 6, 10, 18, 31, 2, 2], '5': [31, 16, 30, 1, 1, 17, 14], '6': [6, 8, 16, 30, 17, 17, 14], '7': [31, 1, 2, 4, 8, 8, 8], '8': [14, 17, 17, 14, 17, 17, 14], '9': [14, 17, 17, 15, 1, 2, 12], 'A': [14, 17, 17, 31, 17, 17, 17], 'B': [30, 17, 17, 30, 17, 17, 30], 'C': [14, 17, 16, 16, 16, 17, 14], 'D': [30, 17, 17, 17, 17, 17, 30], 'E': [31, 16, 16, 30, 16, 16, 31], 'F': [31, 16, 16, 30, 16, 16, 16], 'G': [14, 17, 16, 23, 17, 17, 15], 'H': [17, 17, 17, 31, 17, 17, 17], 'I': [14, 4, 4, 4, 4, 4, 14], 'J': [7, 2, 2, 2, 2, 18, 12], 'K': [17, 18, 20, 24, 20, 18, 17], 'L': [16, 16, 16, 16, 16, 16, 31], 'M': [17, 27, 21, 21, 17, 17, 17], 'N': [17, 25, 21, 19, 17, 17, 17], 'O': [14, 17, 17, 17, 17, 17, 14], 'P': [30, 17, 17, 30, 16, 16, 16], 'Q': [14, 17, 17, 17, 21, 18, 13], 'R': [30, 17, 17, 30, 20, 18, 17], 'S': [15, 16, 16, 14, 1, 1, 30], 'T': [31, 4, 4, 4, 4, 4, 4], 'U': [17, 17, 17, 17, 17, 17, 14], 'V': [17, 17, 17, 17, 17, 10, 4], 'W': [17, 17, 17, 21, 21, 21, 10], 'X': [17, 17, 10, 4, 10, 17, 17], 'Y': [17, 17, 10, 4, 4, 4, 4], 'Z': [31, 1, 2, 4, 8, 16, 31]}
HANDOFF_PATHS = {"new": [], "in_review": ["in_review"], "waiting_on_driver": ["in_review", "waiting_on_driver"],
    "ready_to_file": ["in_review", "ready_to_file"], "filed": ["in_review", "ready_to_file", "filed"]}


def days_ago(days):
    return utc_now() - timedelta(days=days)


def receipt_image(merchant, day, pence):
    """Draw a readable receipt PNG using only the standard library."""
    lines = [merchant.upper(), "DEMO RECEIPT", "", f"DATE {day:%d/%m/%Y}", f"TOTAL GBP {pence / 100:.2f}", f"VAT GBP {pence / 600:.2f}", "", "PAID BY CARD", "THANK YOU"]
    scale, width, height = 3, 340, 40 + len(lines) * 34
    canvas = [bytearray(b"\xff" * width) for _ in range(height)]
    for number, line in enumerate(lines):
        for position, character in enumerate(line):
            for row, bits in enumerate(FONT.get(character, FONT[" "])):
                for column in range(5):
                    if bits >> (4 - column) & 1:
                        for y in range(scale):
                            for x in range(scale):
                                px, py = 20 + position * 6 * scale + column * scale + x, 20 + number * 34 + row * scale + y
                                if px < width and py < height:
                                    canvas[py][px] = 30

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + bytes(row) for row in canvas)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def staff(db, email, name, role, password):
    user = User(email=email, password_hash=password, display_name=name, created_at=days_ago(400))
    db.add(user)
    db.flush()
    row = StaffAccount(id=user.id, name=name, role=role, totp_secret=b"", last_totp_counter=-1)
    db.add(row)
    db.flush()
    return row


def driver(db, settings, email, first, last, password, joined, utr, ni, region="england_wales_ni", employments=(), accountant=None):
    user = User(email=email, password_hash=password, display_name=f"{first} {last}", created_at=days_ago(joined))
    db.add(user)
    db.flush()
    business = Business(owner_id=user.id, kind="self_employment", name="Taxi business")
    db.add(business)
    db.flush()
    db.add(Profile(owner_id=user.id, kind="me", scope="", data={"first_name": first, "last_name": last, "preferences": {"locale": "en", "timezone": "Europe/London", "reminder_deadlines": True}}))
    db.add(Profile(owner_id=user.id, kind="driver", scope="", data={"licence_type": "private_hire", "council_code": "TfL", "work_pattern": "full_time"}))
    identifiers = {key: value for key, value in (("utr", utr), ("ni_number", ni)) if value}
    masked = {**({"utr_masked": "******" + utr[-4:]} if utr else {}), **({"ni_masked": "*****" + ni[-4:]} if ni else {})}
    for year in (PRIOR, YEAR):
        db.add(Profile(owner_id=user.id, kind="tax", scope=year, identifiers=encrypt(settings, identifiers) if identifiers else None,
            data={"tax_year": year, "region": region, "has_paye_job": bool(employments), "employments": list(employments), **masked}))
    if accountant:
        db.add(DriverAssignment(driver_id=user.id, accountant_id=accountant.id))
    db.flush()
    return user, business


def income(db, user, business, day, pence, source, text="Weekly platform payout"):
    db.add(Transaction(owner_id=user.id, business_id=business.id, kind="income", amount_pence=pence, occurred_on=day, source_id=source,
        description=text, business_use_percent=Decimal(100), deductible_pence=0, review_status="confirmed", claim_status="claimable", eligibility_reason_codes=[]))


def weekly_income(db, user, business, start, weeks, pence, step=0, every=7):
    for week in range(weeks):
        income(db, user, business, start + timedelta(days=week * every), pence + week * step, UBER if week % 2 else BOLT)


def expense(db, user, business, day, pence, code, text, percent=100, vehicle=None, reasons=()):
    deductible = 0 if reasons else int(pence * percent / 100)
    db.add(Transaction(owner_id=user.id, business_id=business.id, kind="expense", amount_pence=pence, occurred_on=day, category_id=catalog_id("category", code),
        vehicle_id=vehicle.id if vehicle else None, description=text, business_use_percent=Decimal(percent), deductible_pence=deductible,
        review_status="confirmed", claim_status="excluded" if reasons else "claimable", eligibility_reason_codes=list(reasons)))


def add_vehicle(db, user, registration, make, model, method="mileage", start=date(2025, 4, 6)):
    row = Vehicle(owner_id=user.id, registration=registration, ownership="owned", licence_class="private_hire", business_start_on=start,
        details={"make": make, "model": model, "year": 2021, "colour": "Silver", "fuel": "hybrid"}, claim_method=method, method_locked=method == "mileage")
    db.add(row)
    db.flush()
    db.add(Election(owner_id=user.id, vehicle_id=row.id, effective_from=start, method=method, evidence={"acknowledgement_version": "hmrc-2026-10-27"}))
    return row


def trip(db, user, business, row, day, miles, purpose):
    db.add(Mileage(owner_id=user.id, business_id=business.id, vehicle_id=row.id, occurred_on=day, business_miles=Decimal(miles), private_miles=Decimal(0),
        purpose=purpose, evidence_hash=f"{row.id.hex[:20]}{day:%Y%m%d}{len(purpose):04d}"))


def receipt(db, user, business, merchant, pence, day, code, confidence, warnings=(), reviewed=False):
    content = receipt_image(merchant, day, pence)
    file = PrivateFile(owner_id=user.id, sha256=f"{abs(hash((str(user.id), merchant, str(day)))):064d}"[:64], mime_type="image/png", content=content, size_bytes=len(content), scan_status="clean")
    db.add(file)
    db.flush()
    row = Receipt(owner_id=user.id, file_id=file.id, business_id=business.id, processing_status="review_required",
        extraction={"merchant": merchant, "amount_pence": pence, "occurred_on": str(day), "vat_pence": pence // 6, "confidence": confidence,
            "warnings": list(warnings), "suggested_category_id": str(catalog_id("category", code)), "provider": "synthetic-demo"})
    if reviewed:
        row.review_status, row.claim_status = "confirmed", "claimable"
    db.add(row)
    db.flush()
    return row


def handoff(db, user, year, status, actor, age, kind="books_handoff"):
    request = SupportRecord(owner_id=user.id, kind="accountant_request", data={"kind": kind, "status": "requested", "delivered": False}, created_at=days_ago(age))
    db.add(request)
    db.flush()
    path = HANDOFF_PATHS[status]
    row = AccountantHandoff(id=request.id, driver_id=user.id, tax_year=year, status=status, version=len(path) + 1)
    db.add(row)
    db.flush()
    for index, step in enumerate(path):
        db.add(StaffAudit(actor_id=actor.id, driver_id=user.id, resource_id=row.id, action="handoff_updated", created_at=days_ago(age - index - 1),
            before={"status": (["new"] + path)[index]}, after={"status": step, "reason": "Synthetic demo progress"}))
    return row


def history(db, user, year, gross, paye=0, source="filed", rent=0):
    db.add(Profile(owner_id=user.id, kind="tax_history", scope=year, data={"gross_se_income_pence": gross, "gross_other_se_income_pence": 0,
        "gross_property_income_pence": rent, "paye_income_pence": paye, "source": source, "return_filed": "yes" if source == "filed" else "not_yet_due"}))


def prepared_return(db, user, actor, status, adjustment=None, reference=None, filer=None):
    """Build a return at a later stage through the same engine the panel uses."""
    row = TaxReturn(owner_id=user.id, tax_year=PRIOR, earlier_snapshots=[], review_version=0)
    db.add(row)
    db.flush()
    if adjustment:
        db.add(TaxAdjustment(owner_id=user.id, return_id=row.id, tax_year=PRIOR, created_by=actor.id, target="capital_allowances", amount_pence=adjustment, reason="Main pool allowance on the vehicle"))
    db.flush()
    if status == "in_preparation":
        return row
    calculation = estimate(db, user.id, PRIOR)
    row.review_version = 1
    row.snapshot = jsonable_encoder({"review_version": 1, "estimate": calculation, "rules": rule_set(PRIOR, "england_wales_ni", db), "created_at": days_ago(9), "created_by": actor.name})
    db.add(StaffAudit(actor_id=actor.id, driver_id=user.id, resource_id=row.id, action="tax_return_sent_for_signoff", created_at=days_ago(9), after={"review_version": 1, "reason": "Review complete"}))
    row.status = status
    if status in {"driver_approved", "filed"}:
        row.driver_decided_at = days_ago(6)
    if status == "filed":
        row.filing_reference, row.filed_at, row.filed_by = reference, days_ago(3), (filer or actor).id
        db.add(StaffAudit(actor_id=(filer or actor).id, driver_id=user.id, resource_id=row.id, action="tax_return_filed", created_at=days_ago(3), after={"filing_reference": reference, "reason": "Filed through practice software"}))
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password", required=True, help="Shared password for the synthetic staff and driver accounts")
    args = parser.parse_args()
    if len(args.password) < 12:
        parser.error("Use at least 12 characters")
    settings = get_settings()
    if not settings.postgres_db.endswith("_demo"):
        parser.error(f"Refusing to seed '{settings.postgres_db}': the database name must end in _demo")
    if not settings.identifier_encryption_keys:
        parser.error("IDENTIFIER_ENCRYPTION_KEYS must be set so demo UTRs can be encrypted")
    engine = build_engine(settings)
    hashed = password_hash.hash(args.password)
    try:
        with Session(engine) as db:
            if db.scalar(select(StaffAccount).limit(1)):
                parser.error("This demo database already has staff; create a fresh one to reseed")
            db.flush()
            admin = staff(db, "admin@taxiaibooks.example", "Arif Rahman", "admin", hashed)
            sarah = staff(db, "sarah@taxiaibooks.example", "Sarah Jones", "accountant", hashed)
            accountant = staff(db, "accountant@taxiaibooks.example", "Priya Shah", "accountant", hashed)
            south_accountant = staff(db, "accountant2@taxiaibooks.example", "Tom Evans", "accountant", hashed)

            # Ali Khan: the spec's PAYE persona. Two receipts and a platform dispute keep his return open.
            ali, ali_books = driver(db, settings, "ali.khan@driver.example", "Ali", "Khan", hashed, 210, "1234567890", "QQ123456C",
                employments=[{"employer": "ABC Ltd", "gross_annual_pay_pence": 2000000, "tax_paid_pence": 148600}], accountant=accountant)
            prius = add_vehicle(db, ali, "LK21ABC", "Toyota", "Prius")
            weekly_income(db, ali, ali_books, date(2025, 4, 14), 26, 45000, step=300, every=14)
            for week in range(26):
                trip(db, ali, ali_books, prius, date(2025, 4, 14) + timedelta(days=week * 14), "120.00", "Airport and city fares")
            expense(db, ali, ali_books, date(2025, 6, 2), 18500, "platform_fees", "Platform service fee")
            expense(db, ali, ali_books, date(2025, 8, 4), 9600, "operator_fees", "Radio circuit fee")
            expense(db, ali, ali_books, date(2025, 9, 2), 4800, "phone_data", "Phone plan, 80% business", percent=80)
            expense(db, ali, ali_books, date(2025, 9, 10), 6200, "fuel", "Fuel on a mileage-method vehicle", vehicle=prius, reasons=["covered_by_mileage"])
            weekly_income(db, ali, ali_books, date(2026, 4, 13), 20, 42000, step=450)
            for week in range(20):
                trip(db, ali, ali_books, prius, date(2026, 4, 13) + timedelta(days=week * 7), "95.50", "Weekly fares")
            history(db, ali, "2024-25", 1180000, 1900000)
            history(db, ali, PRIOR, 1245000, 2000000)
            prepared_return(db, ali, accountant, "in_preparation")
            handoff(db, ali, PRIOR, "in_review", accountant, 18)
            receipt(db, ali, ali_books, "Shell Heathrow", 5240, date(2026, 2, 3), "fuel", 0.93)
            receipt(db, ali, ali_books, "Q-Park", 1250, date(2026, 3, 9), "parking", 0.58, ["merchant_partly_legible"])
            db.add(DriverDocument(owner_id=ali.id, doc_type="insurance", reference="POL-20481", expires_on=date.today() + timedelta(days=12), vehicle_id=prius.id))
            db.add(DriverDocument(owner_id=ali.id, doc_type="mot", reference="MOT-7732", expires_on=date.today() - timedelta(days=4), vehicle_id=prius.id))
            db.add(DriverDocument(owner_id=ali.id, doc_type="phv_licence", reference="PHV-118204", expires_on=date.today() + timedelta(days=240)))
            db.add(StaffEntry(driver_id=ali.id, staff_id=accountant.id, kind="message", body="Hi Ali, can you upload your P60 for 2025-26?", created_at=days_ago(3)))
            db.add(StaffEntry(driver_id=ali.id, kind="message", body="Uploading it tonight, thanks.", created_at=days_ago(2)))
            db.add(StaffEntry(driver_id=ali.id, staff_id=accountant.id, kind="note", body="Check the second-job PAYE code before sign-off.", created_at=days_ago(1)))
            db.add(Profile(owner_id=ali.id, kind="platform_report", scope=f"{PRIOR}:bolt", data={"reported_gross_pence": 410000, "status": "disputed", "dispute_note": "Bolt total includes two refunded airport trips"}))

            # Mohammed Rahman: full-time PHV plus rent. Mandated for MTD, with a clean return ready for sign-off.
            mohammed, mohammed_books = driver(db, settings, "mohammed.rahman@driver.example", "Mohammed", "Rahman", hashed, 330, "2345678901", "QQ234567C", accountant=accountant)
            galaxy = add_vehicle(db, mohammed, "YD19XYZ", "Ford", "Galaxy", "actual")
            for week in range(50):
                income(db, mohammed, mohammed_books, date(2025, 4, 7) + timedelta(days=week * 7), 95000 + (week % 7) * 2500, UBER if week % 2 else BOLT)
            for code, pence, text in (("fuel", 42000, "Monthly fuel"), ("maintenance", 31000, "Service and tyres"), ("insurance", 21000, "Monthly insurance")):
                for month in range(1, 12):
                    expense(db, mohammed, mohammed_books, date(2025, 4, 20) + timedelta(days=month * 28), pence, code, text, percent=90, vehicle=galaxy)
            weekly_income(db, mohammed, mohammed_books, date(2026, 4, 13), 28, 98000)
            history(db, mohammed, "2024-25", 4600000, source="filed", rent=650000)
            history(db, mohammed, PRIOR, 5100000, source="estimate", rent=650000)
            prepared_return(db, mohammed, accountant, "in_preparation")
            handoff(db, mohammed, PRIOR, "ready_to_file", accountant, 26)
            receipt(db, mohammed, mohammed_books, "Kwik Fit", 18900, date(2026, 9, 20), "maintenance", 0.97)

            # Fatima Noor: Scottish taxpayer, waiting on documents.
            fatima, fatima_books = driver(db, settings, "fatima.noor@driver.example", "Fatima", "Noor", hashed, 150, "3456789012", None, region="scotland", accountant=sarah)
            weekly_income(db, fatima, fatima_books, date(2025, 9, 1), 28, 61000, step=200)
            weekly_income(db, fatima, fatima_books, date(2026, 4, 13), 28, 66000)
            history(db, fatima, PRIOR, 1820000, source="estimate")
            handoff(db, fatima, PRIOR, "waiting_on_driver", sarah, 12, "filing_question")
            db.add(StaffEntry(driver_id=fatima.id, staff_id=sarah.id, kind="message", body="Fatima, we still need your September bank statement.", created_at=days_ago(5)))

            # Daniel Reid: review sent, waiting for his sign-off.
            daniel, daniel_books = driver(db, settings, "daniel.reid@driver.example", "Daniel", "Reid", hashed, 300, "4567890123", "QQ345678C", accountant=accountant)
            weekly_income(db, daniel, daniel_books, date(2025, 4, 21), 40, 72000)
            expense(db, daniel, daniel_books, date(2025, 11, 3), 24000, "licensing", "Council licence renewal")
            prepared_return(db, daniel, accountant, "awaiting_driver")
            handoff(db, daniel, PRIOR, "in_review", accountant, 22)

            # Grace Bennett: signed off, so an admin can record the filing.
            grace, grace_books = driver(db, settings, "grace.bennett@driver.example", "Grace", "Bennett", hashed, 360, "5678901234", "QQ456789C", accountant=sarah)
            weekly_income(db, grace, grace_books, date(2025, 4, 14), 45, 81000)
            expense(db, grace, grace_books, date(2025, 7, 7), 15000, "cleaning", "Valeting")
            prepared_return(db, grace, sarah, "driver_approved")
            handoff(db, grace, PRIOR, "ready_to_file", sarah, 30)

            # Amina Yusuf: filed and locked, including a capital allowance adjustment and AI feedback.
            amina, amina_books = driver(db, settings, "amina.yusuf@driver.example", "Amina", "Yusuf", hashed, 380, "6789012345", "QQ567890C", accountant=south_accountant)
            weekly_income(db, amina, amina_books, date(2025, 4, 14), 48, 69000)
            expense(db, amina, amina_books, date(2025, 10, 6), 12000, "phone_data", "Phone and data")
            prepared_return(db, amina, south_accountant, "filed", adjustment=120000, reference="SA-2026-104482", filer=admin)
            handoff(db, amina, PRIOR, "filed", south_accountant, 44)
            reviewed = receipt(db, amina, amina_books, "BP Croydon", 6100, date(2025, 11, 20), "fuel", 0.71, reviewed=True)
            db.add(AiFeedback(receipt_id=reviewed.id, driver_id=amina.id, staff_id=south_accountant.id, verdict="corrected", corrections={"merchant": "BP Purley Way"}, reason="OCR read the wrong site name", created_at=days_ago(10)))

            # James Okafor: new and unassigned, so assignment and deletion have work to show.
            james, james_books = driver(db, settings, "james.okafor@driver.example", "James", "Okafor", hashed, 9, None, None)
            income(db, james, james_books, date(2026, 3, 5), 38000, CASH, "Rank takings")
            handoff(db, james, PRIOR, "new", admin, 2, "general_question")
            db.add(PrivacyRequest(owner_id=james.id, kind="deletion", detail="I have stopped driving. Please delete my account.", due_on=date.today() + timedelta(days=21)))
            db.add(PrivacyRequest(owner_id=ali.id, kind="export", detail="Please send me a copy of my data.", due_on=date.today() - timedelta(days=2), status="in_progress", handled_by=admin.id))
            db.add(TaxRate(tax_year="2027-28", region="uk", code="vat", value={"threshold_pence": 9000000}, status="draft",
                official_url="https://www.gov.uk/vat-registration/when-to-register", reason="Carry forward the threshold for next year", created_by=admin.id))
            db.commit()
        print("Demo personas loaded. Admin (/admin/login): admin@taxiaibooks.example. Accountants (/login): accountant@, accountant2@, sarah@taxiaibooks.example")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
