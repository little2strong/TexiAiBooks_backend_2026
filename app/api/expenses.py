from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.expense import ExpenseCreate, ExpensePage, ExpensePatch, ExpenseRead
from app.services import expenses

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", response_model=ExpenseRead, status_code=201)
def create(data: ExpenseCreate, user: CurrentUser, session: SessionDep):
    return expenses.create_expense(session, user.id, data)


@router.get("", response_model=ExpensePage)
def list_own(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
):
    return ExpensePage(
        items=expenses.list_expenses(session, user.id, limit, offset), limit=limit, offset=offset
    )


@router.get("/{expense_id}", response_model=ExpenseRead)
def detail(expense_id: UUID, user: CurrentUser, session: SessionDep):
    return expenses.get_expense(session, user.id, expense_id)


@router.patch("/{expense_id}", response_model=ExpenseRead)
def update(expense_id: UUID, data: ExpensePatch, user: CurrentUser, session: SessionDep):
    return expenses.update_expense(session, user.id, expense_id, data)


@router.delete("/{expense_id}", status_code=204)
def delete(expense_id: UUID, user: CurrentUser, session: SessionDep):
    expenses.delete_expense(session, user.id, expense_id)
    return Response(status_code=204)

