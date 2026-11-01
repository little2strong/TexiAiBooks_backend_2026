"""Load the synthetic demo personas into a database whose name ends in _demo.

Refuses any other database, so it cannot touch development or production records.
Every person and figure here is invented. Run after `alembic upgrade head`:

    $env:POSTGRES_DB = 'taxiaibooks_demo'; python scripts/seed_demo.py --password <12+ chars>
"""
import argparse
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import password_hash
from app.db import build_engine
from app.models import User
from app.models.books import (Business, DriverDocument, Election, Mileage, Notification, PrivacyRequest, PrivateFile, Profile,
    Receipt, SupportRecord, TaxReturn, Transaction, Vehicle)
from app.models.common import utc_now
from app.models.staff import AccountantHandoff, AiFeedback, DriverAssignment, StaffAccount, StaffAudit, StaffEntry, StaffTeam, TaxRate
from app.services.books import catalog_id

# Smallest valid PNG, so the private evidence viewer has real bytes to show.
PIXEL = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d4944415478da6364f8cfc0000003010100c9fe92ef0000000049454e44ae426082")
UBER, BOLT, CASH = (catalog_id("source", code) for code in ("uber", "bolt", "cash"))
YEAR, PRIOR = "2026-27", "2025-26"


def staff(db, email, name, role, team, password):
    user = User(email=email, password_hash=password, display_name=name)
    db.add(user)
    db.flush()
    row = StaffAccount(id=user.id, name=name, role=role, team_id=team.id if team else None, totp_secret=b"", last_totp_counter=-1)
    db.add(row)
    db.flush()
    return row


def driver(db, email, first, last, password, region="england_wales_ni", employments=(), utr="******7890", accountant=None):
    user = User(email=email, password_hash=password, display_name=f"{first} {last}")
    db.add(user)
    db.flush()
    business = Business(owner_id=user.id, kind="self_employment", name="Taxi business")
    db.add(business)
    db.flush()
    db.add(Profile(owner_id=user.id, kind="me", scope="", data={"first_name": first, "last_name": last, "preferences": {"locale": "en", "timezone": "Europe/London", "reminder_deadlines": True}}))
    db.add(Profile(owner_id=user.id, kind="driver", scope="", data={"licence_type": "private_hire", "council_code": "TfL", "work_pattern": "full_time"}))
    for year in (PRIOR, YEAR):
        db.add(Profile(owner_id=user.id, kind="tax", scope=year, data={"tax_year": year, "region": region, "has_paye_job": bool(employments),
            "employments": list(employments), "utr_masked": utr}))
    if accountant:
        db.add(DriverAssignment(driver_id=user.id, accountant_id=accountant.id))
    db.flush()
    return user, business


def income(db, user, business, day, pence, source, text):
    db.add(Transaction(owner_id=user.id, business_id=business.id, kind="income", amount_pence=pence, occurred_on=day, source_id=source,
        description=text, business_use_percent=Decimal(100), deductible_pence=0, review_status="confirmed", claim_status="claimable", eligibility_reason_codes=[]))


def expense(db, user, business, day, pence, code, text, percent=100, vehicle=None, reasons=(), review="confirmed"):
    deductible = 0 if reasons else int(pence * percent / 100)
    db.add(Transaction(owner_id=user.id, business_id=business.id, kind="expense", amount_pence=pence, occurred_on=day, category_id=catalog_id("category", code),
        vehicle_id=vehicle.id if vehicle else None, description=text, business_use_percent=Decimal(percent), deductible_pence=deductible,
        review_status=review, claim_status="excluded" if reasons else "claimable", eligibility_reason_codes=list(reasons)))


def vehicle(db, user, registration, make, model, method="mileage", start=date(2025, 4, 6)):
    row = Vehicle(owner_id=user.id, registration=registration, ownership="owned", licence_class="private_hire", business_start_on=start,
        details={"make": make, "model": model, "year": 2021, "colour": "Silver", "fuel": "hybrid"}, claim_method=method, method_locked=method == "mileage")
    db.add(row)
    db.flush()
    db.add(Election(owner_id=user.id, vehicle_id=row.id, effective_from=start, method=method, evidence={"acknowledgement_version": "hmrc-2026-10-27"}))
    return row


def trip(db, user, business, row, day, miles, purpose):
    db.add(Mileage(owner_id=user.id, business_id=business.id, vehicle_id=row.id, occurred_on=day, business_miles=Decimal(miles), private_miles=Decimal(0),
        purpose=purpose, evidence_hash=f"{row.id.hex[:20]}{day:%Y%m%d}{len(purpose):04d}"))


def receipt(db, user, business, tag, merchant, pence, day, code, confidence, warnings=()):
    file = PrivateFile(owner_id=user.id, sha256=(tag * 64)[:64], mime_type="image/png", content=PIXEL, size_bytes=len(PIXEL), scan_status="clean")
    db.add(file)
    db.flush()
    row = Receipt(owner_id=user.id, file_id=file.id, business_id=business.id, processing_status="review_required",
        extraction={"merchant": merchant, "amount_pence": pence, "occurred_on": str(day), "vat_pence": pence // 6, "confidence": confidence,
            "warnings": list(warnings), "suggested_category_id": str(catalog_id("category", code)), "provider": "synthetic-demo"})
    db.add(row)
    db.flush()
    return row


def handoff(db, user, year, status, kind="books_handoff"):
    request = SupportRecord(owner_id=user.id, kind="accountant_request", data={"kind": kind, "status": "requested", "delivered": False})
    db.add(request)
    db.flush()
    row = AccountantHandoff(id=request.id, driver_id=user.id, tax_year=year, status=status, version=1)
    db.add(row)
    return row


def history(db, user, year, gross, paye=0, source="filed", rent=0):
    db.add(Profile(owner_id=user.id, kind="tax_history", scope=year, data={"gross_se_income_pence": gross, "gross_other_se_income_pence": 0,
        "gross_property_income_pence": rent, "paye_income_pence": paye, "source": source, "return_filed": "yes" if source == "filed" else "not_yet_due"}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password", required=True, help="Shared password for the synthetic staff accounts")
    args = parser.parse_args()
    if len(args.password) < 12:
        parser.error("Use at least 12 characters")
    settings = get_settings()
    if not settings.postgres_db.endswith("_demo"):
        parser.error(f"Refusing to seed '{settings.postgres_db}': the database name must end in _demo")
    engine = build_engine(settings)
    hashed = password_hash.hash(args.password)
    try:
        with Session(engine) as db:
            if db.scalar(select(StaffAccount).limit(1)):
                parser.error("This demo database already has staff; create a fresh one to reseed")
            north = StaffTeam(name="North London")
            south = StaffTeam(name="South London")
            db.add_all([north, south])
            db.flush()
            admin = staff(db, "admin@taxiaibooks.example", "Arif Rahman", "admin", None, hashed)
            senior = staff(db, "senior@taxiaibooks.example", "Sarah Jones", "senior_accountant", north, hashed)
            accountant = staff(db, "accountant@taxiaibooks.example", "Priya Shah", "accountant", north, hashed)
            staff(db, "accountant2@taxiaibooks.example", "Tom Evans", "accountant", south, hashed)
            staff(db, "support@taxiaibooks.example", "Lena Novak", "support", None, hashed)

            # Ali Khan: the spec's PAYE persona. Below every MTD threshold.
            ali, ali_books = driver(db, "ali.khan@driver.example", "Ali", "Khan", hashed, employments=[{"employer": "ABC Ltd", "gross_annual_pay_pence": 2000000, "tax_paid_pence": 148600}], accountant=accountant)
            prius = vehicle(db, ali, "LK21ABC", "Toyota", "Prius")
            for week in range(26):
                day = date(2025, 4, 14) + timedelta(days=week * 14)
                income(db, ali, ali_books, day, 45000 + week * 300, UBER if week % 3 else BOLT, "Weekly platform payout")
                trip(db, ali, ali_books, prius, day, "120.00", "Airport and city fares")
            expense(db, ali, ali_books, date(2025, 6, 2), 18500, "platform_fees", "Platform service fee")
            expense(db, ali, ali_books, date(2025, 9, 2), 4800, "phone_data", "Phone plan, 80% business", percent=80)
            expense(db, ali, ali_books, date(2025, 9, 10), 6200, "fuel", "Fuel on a mileage-method vehicle", vehicle=prius, reasons=["covered_by_mileage"])
            for week in range(20):
                day = date(2026, 4, 13) + timedelta(days=week * 7)
                income(db, ali, ali_books, day, 42000 + week * 450, UBER if week % 2 else BOLT, "Weekly platform payout")
                trip(db, ali, ali_books, prius, day, "95.50", "Weekly fares")
            history(db, ali, "2024-25", 1180000, 1900000)
            history(db, ali, PRIOR, 1245000, 2000000)
            db.add(TaxReturn(owner_id=ali.id, tax_year=PRIOR, earlier_snapshots=[], review_version=0))
            handoff(db, ali, PRIOR, "in_review")
            receipt(db, ali, ali_books, "a", "Shell Heathrow", 5240, date(2026, 10, 3), "fuel", 0.93)
            receipt(db, ali, ali_books, "b", "Q-Park", 1250, date(2026, 10, 9), "parking", 0.58, ["merchant_partly_legible"])
            db.add(DriverDocument(owner_id=ali.id, doc_type="insurance", reference="POL-20481", expires_on=date.today() + timedelta(days=12), vehicle_id=prius.id))
            db.add(DriverDocument(owner_id=ali.id, doc_type="mot", reference="MOT-7732", expires_on=date.today() - timedelta(days=4), vehicle_id=prius.id))
            db.add(DriverDocument(owner_id=ali.id, doc_type="phv_licence", reference="PHV-118204", expires_on=date.today() + timedelta(days=240)))
            db.add(StaffEntry(driver_id=ali.id, staff_id=accountant.id, kind="message", body="Hi Ali, can you upload your P60 for 2025-26?", created_at=utc_now() - timedelta(days=3)))
            db.add(StaffEntry(driver_id=ali.id, kind="message", body="Uploading it tonight, thanks.", created_at=utc_now() - timedelta(days=2)))
            db.add(StaffEntry(driver_id=ali.id, staff_id=accountant.id, kind="note", body="Check the second-job PAYE code before sign-off.", created_at=utc_now() - timedelta(days=1)))
            db.add(Profile(owner_id=ali.id, kind="platform_report", scope=f"{PRIOR}:bolt", data={"reported_gross_pence": 410000, "status": "disputed", "dispute_note": "Bolt total includes two refunded airport trips"}))

            # Mohammed Rahman: full-time PHV plus rent. Mandated for MTD.
            mohammed, mohammed_books = driver(db, "mohammed.rahman@driver.example", "Mohammed", "Rahman", hashed, accountant=accountant)
            galaxy = vehicle(db, mohammed, "YD19XYZ", "Ford", "Galaxy", "actual")
            for week in range(50):
                day = date(2025, 4, 7) + timedelta(days=week * 7)
                income(db, mohammed, mohammed_books, day, 95000 + (week % 7) * 2500, UBER if week % 2 else BOLT, "Weekly platform payout")
            for code, pence, text in (("fuel", 42000, "Monthly fuel"), ("maintenance", 31000, "Service and tyres"), ("insurance", 21000, "Monthly insurance")):
                for month in range(1, 12):
                    expense(db, mohammed, mohammed_books, date(2025, 4, 20) + timedelta(days=month * 28), pence, code, text, percent=90, vehicle=galaxy)
            for week in range(28):
                income(db, mohammed, mohammed_books, date(2026, 4, 13) + timedelta(days=week * 7), 98000, UBER, "Weekly platform payout")
            history(db, mohammed, "2024-25", 4600000, source="filed", rent=650000)
            history(db, mohammed, PRIOR, 5100000, source="estimate", rent=650000)
            handoff(db, mohammed, PRIOR, "ready_to_file")
            receipt(db, mohammed, mohammed_books, "c", "Kwik Fit", 18900, date(2026, 9, 20), "maintenance", 0.97)
            db.add(TaxReturn(owner_id=mohammed.id, tax_year=PRIOR, earlier_snapshots=[], review_version=0))

            # Fatima Noor: Scottish taxpayer waiting on documents.
            fatima, fatima_books = driver(db, "fatima.noor@driver.example", "Fatima", "Noor", hashed, region="scotland", utr="******4471", accountant=senior)
            for week in range(30):
                income(db, fatima, fatima_books, date(2026, 4, 13) + timedelta(days=week * 7), 61000 + week * 200, BOLT if week % 2 else CASH, "Weekly takings")
            handoff(db, fatima, YEAR, "waiting_on_driver", "filing_question")
            history(db, fatima, PRIOR, 2850000, source="estimate")

            # Unassigned new driver, so assignment and deletion flows have work to show.
            james, james_books = driver(db, "james.okafor@driver.example", "James", "Okafor", hashed, utr=None)
            income(db, james, james_books, date(2026, 10, 5), 38000, CASH, "Rank takings")
            handoff(db, james, YEAR, "new", "general_question")
            db.add(PrivacyRequest(owner_id=james.id, kind="deletion", detail="I have stopped driving. Please delete my account.", due_on=date.today() + timedelta(days=21)))
            db.add(PrivacyRequest(owner_id=ali.id, kind="export", detail="Please send me a copy of my data.", due_on=date.today() - timedelta(days=2), status="in_progress", handled_by=admin.id))
            db.add(TaxRate(tax_year="2027-28", region="uk", code="vat", value={"threshold_pence": 9000000}, status="draft",
                official_url="https://www.gov.uk/vat-registration/when-to-register", reason="Carry forward the threshold for next year", created_by=admin.id))
            db.add(StaffAudit(actor_id=admin.id, driver_id=ali.id, action="seed_demo_data", after={"note": "Synthetic demo records"}, created_at=utc_now()))
            db.commit()
        print("Demo personas loaded. Staff emails: admin@, senior@, accountant@, accountant2@, support@taxiaibooks.example")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
