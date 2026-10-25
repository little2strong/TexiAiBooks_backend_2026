from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.common import Timestamps


class Expense(Timestamps, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount_pence > 0", name="amount_positive"),
        CheckConstraint("currency = 'GBP'", name="currency_gbp"),
        CheckConstraint(
            "category IN ('fuel', 'maintenance', 'insurance', 'licensing', 'parking', 'other')",
            name="category_valid",
        ),
        Index("ix_expenses_owner_date", "owner_id", "expense_date", "created_at", "id",
              postgresql_where=text("deleted_at IS NULL")),
        Index("ix_expenses_owner_id", "owner_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    amount_pence: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="GBP")
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(2000))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

