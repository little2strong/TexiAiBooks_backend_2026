from datetime import date, datetime
from decimal import Decimal
import re
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

Money = Annotated[int, Field(strict=True, gt=0, le=9_000_000_000_000)]
NonnegativeMoney = Annotated[int, Field(strict=True, ge=0, le=9_000_000_000_000)]
Version = Annotated[int, Field(strict=True, ge=1)]
Year = Annotated[str, Field(pattern=r"^20[0-9]{2}-[0-9]{2}$")]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Versioned(Body):
    expected_version: Version


class DecimalBody(Body):
    @field_validator("*", mode="before")
    @classmethod
    def decimal_strings(cls, value, info):
        if info.field_name in {"business_use_percent", "percent", "business_miles", "private_miles", "start_odometer", "end_odometer"}:
            if value is not None and (not isinstance(value, str) or re.fullmatch(r"[0-9]{1,10}(\.[0-9]{1,2})?", value) is None):
                raise ValueError("Use a nonnegative decimal string with at most two decimal places")
        return value


class Preferences(Body):
    reminder_after_shift: bool = False
    reminder_weekly: bool = False
    reminder_deadlines: bool = False
    preferred_weekday: Annotated[int, Field(strict=True, ge=0, le=6)] | None = None
    locale: Literal["en", "ur", "bn", "pa", "pl", "ro", "ar"] = "en"
    timezone: str = "Europe/London"

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError("Unknown timezone") from None
        return value


class MePatch(Versioned):
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    preferences: Preferences | None = None

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set - {"expected_version"}:
            raise ValueError("Empty patch")
        if "preferences" in self.model_fields_set and self.preferences is None:
            raise ValueError("Preferences cannot be null")
        if self.model_fields_set=={"expected_version","preferences"} and not self.preferences.model_fields_set:
            raise ValueError("Empty preference patch")
        return self


class OnboardingPatch(Versioned):
    current_step: Annotated[int, Field(strict=True, ge=1, le=9)] | None = None
    completed_steps: list[Annotated[int, Field(strict=True, ge=1, le=9)]] | None = Field(default=None, max_length=9)
    skipped_fields: list[str] | None = Field(default=None, max_length=20)
    complete: bool = False

    @model_validator(mode="after")
    def nonempty(self):
        if not self.model_fields_set-{"expected_version"}: raise ValueError("Empty progress patch")
        if self.completed_steps is not None and len(set(self.completed_steps))!=len(self.completed_steps):
            raise ValueError("Duplicate completed steps")
        return self


class DriverInput(Body):
    licence_type: Literal["private_hire", "hackney"]
    council_code: str = Field(min_length=1, max_length=100)
    work_pattern: Literal["alongside_job", "full_time"]
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    expected_version: Version | None = None


class Employment(Body):
    id: UUID | None = None
    employer_name: str = Field(min_length=1, max_length=150)
    gross_annual_pay_pence: NonnegativeMoney
    tax_paid_pence: NonnegativeMoney
    tax_code: str | None = Field(default=None, max_length=20)
    student_loan_paid_pence: NonnegativeMoney = 0


class TaxProfileInput(Body):
    tax_year: Year
    region: Literal["england_wales_ni", "scotland"]
    has_paye_job: bool
    employments: list[Employment] = Field(default_factory=list, max_length=20)
    property_income_pence: NonnegativeMoney | None = None
    interest_pence: NonnegativeMoney | None = None
    student_loan_plan: Literal["none", "plan1", "plan2", "plan4", "plan5", "postgraduate"] | None = None
    marriage_allowance_status: Literal["none", "transferor", "recipient"] | None = None
    marriage_allowance_eligible: bool = False
    class4_exempt: bool = False
    utr: SecretStr | None = None
    ni_number: SecretStr | None = None
    expected_version: Version | None = None

    @field_validator("utr", "ni_number")
    @classmethod
    def identifiers_valid(cls, value, info):
        if value is None:
            return value
        raw = re.sub(r"\s", "", value.get_secret_value()).upper()
        if info.field_name == "utr":
            valid = re.fullmatch(r"[0-9]{10}", raw)
        else:
            valid = re.fullmatch(r"[A-CEGHJ-PR-TW-Z][A-CEGHJ-NPR-TW-Z][0-9]{6}[A-D]", raw)
            valid = valid and raw[:2] not in {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}
        if not valid:
            raise ValueError("Invalid tax identifier format")
        return SecretStr(raw)

    @model_validator(mode="after")
    def employment_consistency(self):
        if self.has_paye_job != bool(self.employments):
            raise ValueError("PAYE flag must match supplied employment inputs")
        return self


class VehicleInput(Body):
    registration: str = Field(min_length=2, max_length=12)
    ownership: Literal["owned", "rented", "leased"]
    licence_class: Literal["private_hire", "hackney", "goods", "motorcycle"]
    make: str | None = Field(default=None, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    year: Annotated[int, Field(strict=True, ge=1900, le=2100)] | None = None
    colour: str | None = Field(default=None, max_length=40)
    fuel: str | None = Field(default=None, max_length=40)
    business_start_on: date

    @field_validator("registration")
    @classmethod
    def normalize_registration(cls, value):
        value = value.replace(" ", "").upper()
        if re.fullmatch(r"[A-Z0-9]{2,10}", value) is None:
            raise ValueError("Invalid registration")
        return value


class ElectionInput(Versioned):
    method: Literal["mileage", "actual"]
    effective_from: date
    prior_capital_allowances: bool
    prior_vehicle_expense_claim: bool
    acknowledgement_version: str = Field(min_length=1, max_length=80)


class VehicleLookup(Body):
    registration: str=Field(min_length=2,max_length=12)

    @field_validator("registration")
    @classmethod
    def plate(cls,value):
        return VehicleInput.normalize_registration(value)


class TransactionInput(DecimalBody):
    kind: Literal["income", "expense"]
    amount_pence: Money
    currency: Literal["GBP"] = "GBP"
    occurred_on: date
    business_id: UUID
    source_id: UUID | None = None
    category_id: UUID | None = None
    vehicle_id: UUID | None = None
    receipt_id: UUID | None = None
    payment_method: Literal["cash", "card_bank", "other"] = "other"
    description: str | None = Field(default=None, max_length=2000)
    no_receipt_reason: str | None = Field(default=None, max_length=500)
    business_use_percent: Annotated[Decimal, Field(ge=0, le=100)] | None = None

    @model_validator(mode="after")
    def required_reference(self):
        if self.kind == "income" and self.source_id is None:
            raise ValueError("Income requires source_id")
        if self.kind == "expense" and self.category_id is None:
            raise ValueError("Expense requires category_id")
        return self


class TransactionPatch(DecimalBody):
    expected_version: Version
    amount_pence: Money | None = None
    occurred_on: date | None = None
    source_id: UUID | None = None
    category_id: UUID | None = None
    vehicle_id: UUID | None = None
    payment_method: Literal["cash", "card_bank", "other"] | None = None
    description: str | None = Field(default=None, max_length=2000)
    no_receipt_reason: str | None = Field(default=None, max_length=500)
    business_use_percent: Annotated[Decimal, Field(ge=0, le=100)] | None = None

    @model_validator(mode="after")
    def nonempty(self):
        fields = self.model_fields_set - {"expected_version"}
        if not fields:
            raise ValueError("Empty patch")
        for key in fields - {"vehicle_id", "description", "no_receipt_reason"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        return self


class Reversal(Versioned):
    mutation_id: UUID
    reason: str = Field(min_length=1, max_length=500)


class MileageInput(DecimalBody):
    business_id: UUID
    vehicle_id: UUID
    occurred_on: date
    start_odometer: Annotated[Decimal, Field(ge=0, le=9999999999)] | None = None
    end_odometer: Annotated[Decimal, Field(ge=0, le=9999999999)] | None = None
    business_miles: Annotated[Decimal, Field(gt=0, le=9999999999)]
    private_miles: Annotated[Decimal, Field(ge=0, le=9999999999)] = Decimal(0)
    purpose: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def odometers(self):
        if (self.start_odometer is None) != (self.end_odometer is None):
            raise ValueError("Supply both odometers or neither")
        if self.start_odometer is not None and self.end_odometer - self.start_odometer != self.business_miles + self.private_miles:
            raise ValueError("Odometer distance must equal business plus private miles")
        return self


class MileagePatch(DecimalBody):
    expected_version: Version
    occurred_on: date | None = None
    start_odometer: Annotated[Decimal,Field(ge=0,le=9999999999)] | None = None
    end_odometer: Annotated[Decimal,Field(ge=0,le=9999999999)] | None = None
    business_miles: Annotated[Decimal,Field(gt=0,le=9999999999)] | None = None
    private_miles: Annotated[Decimal,Field(ge=0,le=9999999999)] | None = None
    purpose: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def nonempty(self):
        fields=self.model_fields_set-{"expected_version"}
        if not fields: raise ValueError("Empty patch")
        if any(getattr(self,key) is None for key in fields-{"start_odometer","end_odometer"}):
            raise ValueError("Mileage values cannot be null")
        return self


class PolicyInput(DecimalBody):
    percent: Annotated[Decimal, Field(ge=0, le=100)]
    effective_from: date
    apply_to: Literal["future_only", "selected_open_period"] = "future_only"
    reason: str | None = Field(default=None, max_length=500)
    expected_version: Annotated[int, Field(strict=True, ge=0)]


class ReceiptPatch(DecimalBody):
    expected_version: Version
    merchant: str | None = Field(default=None, max_length=200)
    occurred_on: date | None = None
    amount_pence: Money | None = None
    vat_pence: NonnegativeMoney | None = None
    category_id: UUID | None = None
    business_use_percent: Annotated[Decimal, Field(ge=0, le=100)] | None = None
    claim_status: Literal["claimable", "personal", "excluded"] | None = None


class ReceiptExtraction(Body):
    merchant: str|None=Field(default=None,max_length=200)
    occurred_on: date|None=None
    amount_pence: Money|None=None
    vat_pence: NonnegativeMoney|None=None
    currency: Literal["GBP"]="GBP"
    suggested_category_id: UUID|None=None
    confidence: Annotated[Decimal,Field(ge=0,le=1,max_digits=5,decimal_places=4)]|None=None
    warnings: list[Annotated[str,Field(max_length=200)]]=Field(default_factory=list,max_length=20)

    @model_validator(mode="after")
    def vat_valid(self):
        if self.vat_pence is not None and self.amount_pence is not None and self.vat_pence>self.amount_pence:
            raise ValueError("Extracted VAT exceeds total")
        return self


class Confirmation(DecimalBody):
    expected_version: Version
    claim_status: Literal["claimable", "personal", "excluded"]
    category_id: UUID
    business_use_percent: Annotated[Decimal, Field(ge=0, le=100)]


class SourcesInput(Body):
    source_ids: list[UUID] = Field(max_length=100)


class PotInput(Body):
    amount_pence: Money
    occurred_on: date
    note: str | None = Field(default=None, max_length=500)


class ResolveInput(Versioned):
    action: Literal["add_missing", "link_existing"]
    transaction_id: UUID | None = None
    amount_pence: Money | None = None
    fee_pence: NonnegativeMoney | None = None
    occurred_on: date | None = None
    note: str | None = Field(default=None, max_length=500)


class ExportInput(Body):
    tax_year: Year
    format: Literal["csv", "pdf"]
    include_photos: bool = False


class AccountantInput(Body):
    kind: Literal["books_handoff", "marriage_allowance", "filing_question"]
    export_id: UUID | None = None
    recipient_reference: str = Field(min_length=1, max_length=200)
    message: str | None = Field(default=None, max_length=2000)
    consent_version: str = Field(min_length=1, max_length=100)


class ReadState(Body):
    read: bool


class ReadAll(Body):
    through: datetime

    @field_validator("through")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamp must include timezone")
        return value


class LoginChallengeInput(Body):
    phone: str
    purpose: Literal["sign_up", "sign_in"]

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value):
        value = re.sub(r"[\s()-]", "", value)
        if value.startswith("07"):
            value = "+44" + value[1:]
        if not re.fullmatch(r"\+447[0-9]{9}", value):
            raise ValueError("Use a UK mobile number")
        return value


class LoginCode(Body):
    code: SecretStr

    @field_validator("code")
    @classmethod
    def valid_code(cls, value):
        if not re.fullmatch(r"[0-9]{6}", value.get_secret_value()):
            raise ValueError("Code must contain six ASCII digits")
        return value
