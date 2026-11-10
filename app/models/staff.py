"""Additive staff membership and audited accountant collaboration."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, LargeBinary, String, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


STAFF_ROLES = ("admin", "accountant")


class StaffAccount(Base):
    __tablename__ = "staff_accounts"
    __table_args__ = (CheckConstraint("role IN ('accountant','admin')", name="role_valid"),)
    id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(24))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Legacy columns retained for existing databases; password login does not use them.
    totp_secret: Mapped[bytes] = mapped_column(LargeBinary, default=b"")
    last_totp_counter: Mapped[int] = mapped_column(Integer, default=-1)


class DriverAssignment(Base):
    __tablename__ = "driver_assignments"
    driver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    accountant_id: Mapped[UUID] = mapped_column(ForeignKey("staff_accounts.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AccountantHandoff(Base):
    __tablename__ = "accountant_handoffs"
    __table_args__ = (CheckConstraint("status IN ('new','in_review','waiting_on_driver','ready_to_file','filed')", name="status_valid"),)
    id: Mapped[UUID] = mapped_column(ForeignKey("support_records.id"), primary_key=True)
    driver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    tax_year: Mapped[str | None] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(24), default="new")
    filing_reference: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)


class StaffEntry(Base):
    __tablename__ = "staff_entries"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    driver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    staff_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_accounts.id"))
    kind: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(String(8000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StaffAudit(Base):
    __tablename__ = "staff_audit"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("staff_accounts.id"), index=True)
    driver_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StaffView(Base):
    __tablename__ = "staff_views"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff_accounts.id"), index=True)
    resource: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(100))
    query: Mapped[dict] = mapped_column(JSONB)


class TaxRate(Base):
    """Admin-managed overlay on the built-in rule registry; only active rows apply."""
    __tablename__ = "tax_rates"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved','active','retired')", name="status_valid"),
        CheckConstraint("region IN ('england_wales_ni','scotland','uk')", name="region_valid"),
        Index("uq_tax_rates_active", "tax_year", "region", "code", unique=True, postgresql_where=text("status = 'active'")),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tax_year: Mapped[str] = mapped_column(String(7))
    region: Mapped[str] = mapped_column(String(24))
    code: Mapped[str] = mapped_column(String(32))
    value: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    official_url: Mapped[str] = mapped_column(String(500))
    reason: Mapped[str] = mapped_column(String(500))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("staff_accounts.id"))
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("staff_accounts.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiFeedback(Base):
    __tablename__ = "ai_feedback"
    __table_args__ = (CheckConstraint("verdict IN ('accepted','corrected','rejected')", name="verdict_valid"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    receipt_id: Mapped[UUID] = mapped_column(ForeignKey("receipts.id"), index=True)
    driver_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    staff_id: Mapped[UUID] = mapped_column(ForeignKey("staff_accounts.id"))
    verdict: Mapped[str] = mapped_column(String(16))
    corrections: Mapped[dict] = mapped_column(JSONB, default=dict)
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
