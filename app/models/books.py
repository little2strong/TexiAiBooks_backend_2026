"""Bookkeeping entities. GBP amounts are pence; no provider secrets live here."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
                        Index, Integer, LargeBinary, Numeric, String, UniqueConstraint, Uuid, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Owned:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Profile(Owned, Base):
    __tablename__ = "book_profiles"
    __table_args__ = (UniqueConstraint("owner_id", "kind", "scope"),)
    kind: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(32), default="", server_default="")
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    identifiers: Mapped[bytes | None] = mapped_column(LargeBinary)


class Business(Owned, Base):
    __tablename__ = "businesses"
    __table_args__ = (UniqueConstraint("owner_id", "kind"),)
    kind: Mapped[str] = mapped_column(String(32), default="self_employment")
    name: Mapped[str] = mapped_column(String(100), default="Taxi business")


class Vehicle(Owned, Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("owner_id", "registration"),)
    registration: Mapped[str] = mapped_column(String(12))
    ownership: Mapped[str] = mapped_column(String(16))
    licence_class: Mapped[str] = mapped_column(String(24))
    business_start_on: Mapped[date] = mapped_column(Date)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    claim_method: Mapped[str] = mapped_column(String(16), default="unset")
    method_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Election(Owned, Base):
    __tablename__ = "vehicle_claim_elections"
    __table_args__ = (UniqueConstraint("vehicle_id", "effective_from"),)
    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    method: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[dict] = mapped_column(JSONB)


class Transaction(Owned, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_pence > 0", name="amount_positive"),
        CheckConstraint("currency = 'GBP'", name="currency_gbp"),
        CheckConstraint("business_use_percent BETWEEN 0 AND 100", name="share_valid"),
        CheckConstraint("deductible_pence BETWEEN 0 AND amount_pence", name="deduction_valid"),
        CheckConstraint("kind IN ('income','expense')", name="kind_valid"),
        CheckConstraint("review_status IN ('draft','confirmed','reversed')", name="review_valid"),
        CheckConstraint("claim_status IN ('claimable','personal','excluded')", name="claim_valid"),
        UniqueConstraint("owner_id", "import_origin_key"),
        Index("ix_transactions_owner_date", "owner_id", "occurred_on", "id"),
    )
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    amount_pence: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="GBP")
    occurred_on: Mapped[date] = mapped_column(Date)
    source_id: Mapped[UUID | None] = mapped_column(Uuid)
    category_id: Mapped[UUID | None] = mapped_column(Uuid)
    vehicle_id: Mapped[UUID | None] = mapped_column(ForeignKey("vehicles.id"))
    receipt_id: Mapped[UUID | None] = mapped_column(ForeignKey("receipts.id"), unique=True)
    legacy_expense_id: Mapped[UUID | None] = mapped_column(ForeignKey("expenses.id"), unique=True)
    payment_method: Mapped[str] = mapped_column(String(16), default="other")
    description: Mapped[str | None] = mapped_column(String(2000))
    no_receipt_reason: Mapped[str | None] = mapped_column(String(500))
    business_use_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=100)
    business_use_override: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    deductible_pence: Mapped[int] = mapped_column(BigInteger, default=0)
    review_status: Mapped[str] = mapped_column(String(16), default="confirmed")
    claim_status: Mapped[str] = mapped_column(String(16), default="claimable")
    eligibility_reason_codes: Mapped[list] = mapped_column(JSONB, default=list)
    import_origin_key: Mapped[str | None] = mapped_column(String(200))
    mutation_id: Mapped[UUID | None] = mapped_column(Uuid)


class Policy(Owned, Base):
    __tablename__ = "business_use_policies"
    __table_args__ = (UniqueConstraint("owner_id", "category_id", "effective_from"),
                      CheckConstraint("percent BETWEEN 0 AND 100", name="percent_valid"))
    category_id: Mapped[UUID] = mapped_column(Uuid)
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    effective_from: Mapped[date] = mapped_column(Date)
    reason: Mapped[str | None] = mapped_column(String(500))


class Mileage(Owned, Base):
    __tablename__ = "mileage_logs"
    __table_args__ = (CheckConstraint("business_miles >= 0 AND private_miles >= 0", name="miles_valid"),
        UniqueConstraint("owner_id", "vehicle_id", "occurred_on", "evidence_hash"))
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id"))
    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey("vehicles.id"), index=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    business_miles: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    private_miles: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    start_odometer: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    end_odometer: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    purpose: Mapped[str] = mapped_column(String(500))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    mutation_id: Mapped[UUID | None] = mapped_column(Uuid)


class Mutation(Owned, Base):
    __tablename__ = "book_mutations"
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(32))
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(String(500))
    reversed_by: Mapped[UUID | None] = mapped_column(Uuid)


class Idempotency(Owned, Base):
    __tablename__ = "book_idempotency"
    __table_args__ = (UniqueConstraint("owner_id", "request_key"),)
    request_key: Mapped[UUID] = mapped_column(Uuid)
    digest: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict | list | None] = mapped_column(JSONB)


class PrivateFile(Owned, Base):
    __tablename__ = "private_files"
    __table_args__ = (UniqueConstraint("owner_id", "sha256"),)
    sha256: Mapped[str] = mapped_column(String(64))
    mime_type: Mapped[str] = mapped_column(String(80))
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    scan_status: Mapped[str] = mapped_column(String(24), default="pending")


class Job(Owned, Base):
    __tablename__ = "processing_jobs"
    kind: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[UUID] = mapped_column(Uuid, index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    retryable: Mapped[bool] = mapped_column(Boolean, default=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Receipt(Owned, Base):
    __tablename__ = "receipts"
    file_id: Mapped[UUID] = mapped_column(ForeignKey("private_files.id"), unique=True)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id"))
    vehicle_id: Mapped[UUID | None] = mapped_column(ForeignKey("vehicles.id"))
    processing_status: Mapped[str] = mapped_column(String(16), default="queued")
    review_status: Mapped[str] = mapped_column(String(16), default="pending")
    claim_status: Mapped[str] = mapped_column(String(16), default="unknown")
    extraction: Mapped[dict | None] = mapped_column(JSONB)
    reviewed: Mapped[dict] = mapped_column(JSONB, default=dict)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("processing_jobs.id"))
    mutation_id: Mapped[UUID | None] = mapped_column(Uuid)


class Statement(Owned, Base):
    __tablename__ = "statements"
    file_id: Mapped[UUID] = mapped_column(ForeignKey("private_files.id"), unique=True)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id"))
    source_id: Mapped[UUID] = mapped_column(Uuid)
    processing_status: Mapped[str] = mapped_column(String(16), default="queued")
    import_status: Mapped[str] = mapped_column(String(16), default="preview")
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    payouts: Mapped[list] = mapped_column(JSONB, default=list)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("processing_jobs.id"))
    mutation_id: Mapped[UUID | None] = mapped_column(Uuid)


class Issue(Owned, Base):
    __tablename__ = "reconciliation_issues"
    statement_id: Mapped[UUID] = mapped_column(ForeignKey("statements.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="open")
    resolution: Mapped[dict | None] = mapped_column(JSONB)
    resolution_id: Mapped[UUID | None] = mapped_column(Uuid)


class PotEntry(Owned, Base):
    __tablename__ = "tax_pot_entries"
    __table_args__ = (CheckConstraint("amount_pence > 0", name="amount_positive"),)
    amount_pence: Mapped[int] = mapped_column(BigInteger)
    occurred_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(500))
    reversed: Mapped[bool] = mapped_column(Boolean, default=False)
    mutation_id: Mapped[UUID | None] = mapped_column(Uuid)


class Notification(Owned, Base):
    __tablename__ = "notifications"
    type: Mapped[str] = mapped_column(String(32))
    title_key: Mapped[str] = mapped_column(String(100))
    body_key: Mapped[str] = mapped_column(String(100))
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    resource_type: Mapped[str | None] = mapped_column(String(32))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Export(Owned, Base):
    __tablename__ = "exports"
    tax_year: Mapped[str] = mapped_column(String(7))
    format: Mapped[str] = mapped_column(String(8))
    include_photos: Mapped[bool] = mapped_column(Boolean)
    snapshot: Mapped[list] = mapped_column(JSONB)
    photo_ids: Mapped[list] = mapped_column(JSONB, default=list)
    job_id: Mapped[UUID | None] = mapped_column(ForeignKey("processing_jobs.id"))
    file_id: Mapped[UUID | None] = mapped_column(ForeignKey("private_files.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SupportRecord(Owned, Base):
    """Versioned integration envelopes, never canonical accounting amounts."""
    __tablename__ = "support_records"
    kind: Mapped[str] = mapped_column(String(32), index=True)
    data: Mapped[dict] = mapped_column(JSONB)


class PhoneIdentity(Owned, Base):
    __tablename__ = "phone_identities"
    phone_hash: Mapped[str] = mapped_column(String(64), unique=True)


class PhoneChallenge(Base):
    __tablename__ = "phone_login_challenges"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    phone_hash: Mapped[str] = mapped_column(String(64), index=True)
    destination: Mapped[bytes] = mapped_column(LargeBinary)
    purpose: Mapped[str] = mapped_column(String(16))
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resend_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
