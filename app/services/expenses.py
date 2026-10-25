from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Expense
from app.models.common import utc_now
from app.schemas.expense import ExpenseCreate, ExpensePatch


def owned_expenses(owner_id: UUID):
    return select(Expense).where(Expense.owner_id == owner_id, Expense.deleted_at.is_(None))


def get_expense(session: Session, owner_id: UUID, expense_id: UUID) -> Expense:
    expense = session.scalar(owned_expenses(owner_id).where(Expense.id == expense_id))
    if expense is None:
        raise HTTPException(status_code=404, detail="Expense not found")
    return expense


def list_expenses(session: Session, owner_id: UUID, limit: int, offset: int) -> list[Expense]:
    statement = (
        owned_expenses(owner_id)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc(), Expense.id.desc())
        .limit(limit).offset(offset)
    )
    return list(session.scalars(statement))


def create_expense(session: Session, owner_id: UUID, data: ExpenseCreate) -> Expense:
    expense = Expense(owner_id=owner_id, **data.model_dump())
    session.add(expense)
    session.commit()
    session.refresh(expense)
    return expense


def update_expense(session: Session, owner_id: UUID, expense_id: UUID, data: ExpensePatch) -> Expense:
    expense = get_expense(session, owner_id, expense_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(expense, field, value)
    session.commit()
    session.refresh(expense)
    return expense


def delete_expense(session: Session, owner_id: UUID, expense_id: UUID) -> None:
    expense = get_expense(session, owner_id, expense_id)
    expense.deleted_at = utc_now()
    session.commit()

