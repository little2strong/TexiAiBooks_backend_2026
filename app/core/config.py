from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    postgres_db: str = "taxiaibooks"
    postgres_user: str = "taxi_user"
    postgres_password: SecretStr
    postgres_host: str = "127.0.0.1"
    postgres_port: int = Field(default=5433, ge=1, le=65535)
    jwt_secret_key: SecretStr
    access_token_expire_minutes: int = Field(default=15, ge=1, le=30)
    jwt_issuer: str = "taxiaibooks"
    jwt_audience: str = "taxiaibooks-api"
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    reset_token_expire_minutes: int = Field(default=20, ge=5, le=60)
    google_client_ids: list[str] = []
    apple_client_ids: list[str] = []
    smtp_host: str | None = None
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    password_reset_url: str | None = None
    identifier_encryption_keys: list[SecretStr] = []
    upload_max_bytes: int = Field(default=10_485_760, ge=1024, le=20_971_520)
    export_expire_hours: int = Field(default=24, ge=1, le=168)
    worker_poll_seconds: int = Field(default=3, ge=1, le=60)
    subscription_plans: list[dict] = []
    accountant_recipients: list[str] = []
    clamav_host: str | None = None
    clamav_port: int = Field(default=3310, ge=1, le=65535)
    phone_identity_hmac_key: SecretStr | None = Field(default=None, min_length=32)
    entitlement_requirements: dict[str,str] = {}

    @field_validator("identifier_encryption_keys")
    @classmethod
    def validate_encryption_keys(cls, keys):
        from cryptography.fernet import Fernet
        for key in keys:
            try:
                Fernet(key.get_secret_value().encode())
            except (ValueError, TypeError):
                raise ValueError("Encryption keys must be valid Fernet keys") from None
        return keys

    @field_validator("subscription_plans")
    @classmethod
    def validate_plans(cls, plans):
        from uuid import UUID
        seen=set()
        required={"id","code","price_pence","currency","interval","trial_days","cohort_label","terms_version"}
        for plan in plans:
            if not required <= plan.keys(): raise ValueError("Approved plans require all offer and terms fields")
            try: identifier=str(UUID(str(plan["id"])))
            except (ValueError,TypeError): raise ValueError("Plan ID must be a UUID") from None
            if identifier in seen: raise ValueError("Duplicate plan ID")
            seen.add(identifier)
            if plan["currency"]!="GBP" or plan["interval"]!="month": raise ValueError("Only monthly GBP offers are supported")
            if type(plan["price_pence"]) is not int or not 0<plan["price_pence"]<=1_000_000: raise ValueError("Invalid approved price")
            if type(plan["trial_days"]) is not int or not 1<=plan["trial_days"]<=120: raise ValueError("Invalid trial duration")
            if any(not isinstance(plan[name],str) or not 0<len(plan[name])<=100 for name in ("code","cohort_label","terms_version")):
                raise ValueError("Invalid plan metadata")
            if not isinstance(plan.get("entitlements",[]),list) or any(not isinstance(x,str) or len(x)>100 for x in plan.get("entitlements",[])):
                raise ValueError("Invalid entitlements")
        return plans

    @field_validator("postgres_password", "jwt_secret_key")
    @classmethod
    def validate_secrets(cls, value: SecretStr, info) -> SecretStr:
        secret = value.get_secret_value()
        minimum = 32 if info.field_name == "jwt_secret_key" else 16
        if len(secret) < minimum or secret.startswith("replace-with-"):
            raise ValueError(f"Use a random secret of at least {minimum} characters")
        return value

    @property
    def database_url(self) -> URL:
        # URL objects handle @, %, / and other credential characters safely.
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

