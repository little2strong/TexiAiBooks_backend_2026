"""Additive staff membership and audited accountant collaboration."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class StaffTeam(Base):
    __tablename__ = "staff_teams"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)


class StaffAccount(Base):
    __tablename__ = "staff_accounts"
    __table_args__ = (CheckConstraint("role IN ('accountant','senior_accountant','admin','support')", name="role_valid"),)
    id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(24))
    team_id: Mapped[UUID | None] = mapped_column(ForeignKey("staff_teams.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[bytes] = mapped_column(LargeBinary)
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
