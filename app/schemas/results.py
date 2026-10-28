"""Wire response schemas; services sanitize private columns before projection."""
from datetime import date, datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Result(BaseModel):
    model_config=ConfigDict(from_attributes=True,extra="allow")


T=TypeVar("T")


class Page(Result,Generic[T]):
    items: list[T]
    next_cursor: str|None
    has_more: bool


class VersionedResult(Result):
    id: UUID
    version: int
    created_at: datetime


class TransactionRead(VersionedResult):
    business_id: UUID
    kind: Literal["income","expense"]
    amount_pence: int
    currency: Literal["GBP"]
    occurred_on: date
    source_id: UUID|None
    category_id: UUID|None
    vehicle_id: UUID|None
    receipt_id: UUID|None
    description: str|None
    business_use_percent: str
    deductible_pence: int
    review_status: Literal["draft","confirmed","reversed"]
    claim_status: Literal["claimable","personal","excluded"]
    eligibility_reason_codes: list[str]
    mutation_id: UUID|None


class VehicleRead(VersionedResult):
    registration: str
    ownership: Literal["owned","rented","leased"]
    licence_class: str
    business_start_on: date
    claim_method: Literal["unset","mileage","actual"]
    method_locked: bool
    eligible_methods: list[str]
    eligibility_reasons: list[str]


class MileageRead(VersionedResult):
    business_id: UUID
    vehicle_id: UUID
    occurred_on: date
    business_miles: str
    private_miles: str
    start_odometer: str|None
    end_odometer: str|None
    purpose: str


class JobRead(VersionedResult):
    kind: str
    resource_id: UUID
    status: Literal["queued","processing","succeeded","failed"]
    attempts: int
    error_code: str|None
    retryable: bool
    finished_at: datetime|None


class ReceiptRead(VersionedResult):
    business_id: UUID
    vehicle_id: UUID|None
    processing_status: Literal["uploaded","queued","processing","ready","failed"]
    review_status: Literal["pending","confirmed","reversed"]
    claim_status: Literal["unknown","claimable","personal","excluded"]
    reviewed: dict
    extraction: dict|None
    transaction_id: UUID|None
    job: JobRead|None
    warnings: list[str]


class StatementRead(VersionedResult):
    business_id: UUID
    source_id: UUID
    period_start: date|None
    period_end: date|None
    payouts: list[dict]
    gross_pence: int
    fee_pence: int
    net_pence: int
    import_status: str
    processing_status: str
    job: JobRead|None


class MeRead(Result):
    id: UUID
    first_name: str|None
    last_name: str|None
    locale: str
    timezone: str
    preferences: dict
    onboarding_complete: bool
    phone_masked: str|None
    email_masked: str|None
    version: int
    created_at: datetime


class DashboardRead(Result):
    tax_year: str
    as_of: datetime
    income_pence: int
    deductible_expenses_pence: int
    profit_pence: int
    estimated_tax_pence: int|None
    business_miles: str
    pending_receipts: int
    unresolved_issues: int
    unread_notifications: int
    has_data: bool
    version: str


class TaxEstimateRead(Result):
    id: UUID
    tax_year: str
    as_of: date
    rule_set_id: UUID
    profile_version: int
    ledger_version: str
    income_pence: int
    expense_deduction_pence: int
    profit_pence: int
    personal_allowance_pence: int
    allowance_used_elsewhere_pence: int
    income_tax_pence: int
    class4_pence: int
    total_pence: int
    estimate_only: bool
    bands: list[dict]
    warnings: list[str]
    assumptions: list[str]


class AssistantSource(BaseModel):
    model_config=ConfigDict(extra="ignore")
    title: str=Field(min_length=1,max_length=200)
    url: str=Field(pattern=r"^https://[^/\s]+",max_length=2048)


class MessageRead(Result):
    id: UUID
    conversation_id: UUID
    role: Literal["user","assistant"]
    content: str=Field(max_length=12000)
    status: Literal["complete","failed"]
    created_at: datetime
    sources: list[AssistantSource]=Field(default_factory=list,max_length=20)


class MessagePair(Result):
    user_message: MessageRead
    assistant_message: MessageRead
