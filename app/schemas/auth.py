from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID
import re

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from app.schemas.user import normalize_email

Password = Annotated[SecretStr, Field(min_length=8, max_length=128)]
OpaqueToken = Annotated[SecretStr, Field(min_length=32, max_length=512)]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RefreshRequest(StrictBody):
    refresh_token: OpaqueToken


class ChangePassword(StrictBody):
    current_password: Password
    new_password: Password


class Reauthenticate(StrictBody):
    password: Password


class ForgotPassword(StrictBody):
    email: str = Field(max_length=254)
    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        return normalize_email(value)


class ResetPassword(StrictBody):
    token: OpaqueToken
    new_password: Password


class SessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    device_name: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class ProviderChallenge(StrictBody):
    provider: Literal["google", "apple"]


class ProviderLogin(StrictBody):
    id_token: Annotated[SecretStr, Field(min_length=20, max_length=16384)]
    challenge_id: UUID
    device_name: str = Field(default="Mobile device", min_length=1, max_length=100)


class OTPSend(StrictBody):
    phone: str = Field(pattern=r"^\+[1-9][0-9]{7,14}$")


class OTPVerify(StrictBody):
    challenge_id: UUID
    code: Annotated[SecretStr, Field(min_length=6, max_length=6)]

    @field_validator("code")
    @classmethod
    def digits_only(cls, value: SecretStr):
        if re.fullmatch(r"[0-9]{6}", value.get_secret_value()) is None:
            raise ValueError("Code must contain six ASCII digits")
        return value
