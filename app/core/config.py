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

