from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

AmountPence = Annotated[int, Field(strict=True, gt=0, le=2_147_483_647)]
Category = Literal["fuel", "maintenance", "insurance", "licensing", "parking", "other"]
Note = Annotated[str, Field(strict=True, max_length=2000)]


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_pence: AmountPence
    currency: Literal["GBP"] = "GBP"
    category: Category
    expense_date: date
    note: Note | None = None


class ExpensePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_pence: AmountPence | None = None
    currency: Literal["GBP"] | None = None
    category: Category | None = None
    expense_date: date | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        for field in self.model_fields_set - {"note"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    amount_pence: int
    currency: Literal["GBP"]
    category: Category
    expense_date: date
    note: str | None
    created_at: datetime
    updated_at: datetime


class ExpensePage(BaseModel):
    items: list[ExpenseRead]
    limit: int
    offset: int

