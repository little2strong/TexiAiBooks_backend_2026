from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, TypeAdapter, field_validator

email_adapter = TypeAdapter(EmailStr)


def normalize_email(value: str) -> str:
    # Product policy: treat the complete email address as case-insensitive.
    email = str(email_adapter.validate_python(value.strip())).lower()
    if len(email) > 254:
        raise ValueError("Email must be at most 254 characters")
    return email


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=8, max_length=128)]

    @field_validator("email", mode="before")
    @classmethod
    def normalize(cls, value):
        if not isinstance(value, str):
            raise ValueError("Email must be a string")
        return normalize_email(value)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int

