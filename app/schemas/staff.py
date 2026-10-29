from typing import Literal
from uuid import UUID

from pydantic import EmailStr, Field, SecretStr, field_validator
from app.schemas.books import Body, Versioned


class StaffLogin(Body):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)


class StaffIdentity(Body):
    id: UUID
    name: str
    email: EmailStr | None
    role: Literal["accountant", "senior_accountant", "admin", "support"]
    team_id: UUID | None


class StaffLoginResult(Body):
    access_token: str
    expires_in: int
    staff: StaffIdentity


class TableQuery(Body):
    page: int = Field(default=1, ge=1, le=10000)
    page_size: int = Field(default=25, ge=1, le=100)
    sort: str = Field(default="created_at", max_length=50)
    order: Literal["asc", "desc"] = "desc"
    search: str = Field(default="", max_length=254)
    filters: dict[str, str] = Field(default_factory=dict, max_length=10)

    @field_validator("filters")
    @classmethod
    def valid_filters(cls, values):
        for name, value in values.items():
            if len(value) > 254:
                raise ValueError("Filter values must contain at most 254 characters")
            if name.endswith("_id"):
                UUID(value)
        return values


class YearInput(Body):
    tax_year: str = Field(pattern=r"^20\d{2}-\d{2}$")


class AssignmentInput(Body):
    ids: list[UUID] = Field(min_length=1, max_length=100)
    accountant_id: UUID
    versions: dict[str, int]
    reason: str = Field(min_length=3, max_length=500)


class HandoffPatch(Versioned):
    status: Literal["new", "in_review", "waiting_on_driver", "ready_to_file", "filed"]
    reason: str = Field(min_length=3, max_length=500)
    filing_reference: str | None = Field(default=None, min_length=3, max_length=200)


class RevealInput(YearInput):
    field: Literal["utr", "ni_number"]
    reason: str = Field(min_length=5, max_length=500)


class EntryInput(Body):
    body: str = Field(min_length=1, max_length=8000)
    kind: Literal["note", "ticket"] = "note"


class ReviewInput(Versioned):
    decision: Literal["approve", "reject"]
    category_id: UUID
    business_use_percent: str = Field(pattern=r"^(100(\.0{1,2})?|[0-9]{1,2}(\.[0-9]{1,2})?)$")
    reason: str = Field(min_length=3, max_length=500)


class ViewSearch(Body):
    resource: str = Field(min_length=1, max_length=64)


class ViewInput(ViewSearch):
    name: str = Field(min_length=1, max_length=100)
    query: TableQuery


class ExportInput(Body):
    resource: str = Field(min_length=1, max_length=64)
    driver_id: UUID | None = None
    query: TableQuery
