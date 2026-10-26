"""Delivery adapters never log or return recovery secrets or OTPs."""

from email.message import EmailMessage
import smtplib
import ssl
from typing import Protocol
from urllib.parse import urlsplit

from fastapi import HTTPException

from app.core.config import Settings


class ResetDelivery(Protocol):
    enabled: bool

    def send_reset(self, email: str, token: str) -> None: ...


class SMSDelivery(Protocol):
    enabled: bool

    def send_code(self, phone: str, code: str) -> None: ...


class DisabledSMS:
    enabled = False

    def send_code(self, phone: str, code: str) -> None:
        raise RuntimeError("SMS provider is not configured")


class SMTPResetDelivery:
    def __init__(self, settings: Settings):
        self.settings = settings
        url = urlsplit(settings.password_reset_url or "")
        self.enabled = bool(settings.smtp_host and settings.smtp_from and url.scheme == "https"
                            and url.netloc and not url.fragment)

    def send_reset(self, email: str, token: str) -> None:
        if not self.enabled:
            raise RuntimeError("Password reset delivery is not configured")
        settings = self.settings
        message = EmailMessage()
        message["From"] = settings.smtp_from
        message["To"] = email
        message["Subject"] = "Reset your TaxiAiBooks password"
        # Fragment keeps the token out of ordinary web-server URL/query logs.
        message.set_content(f"Reset your password: {settings.password_reset_url}#token={token}\n"
                            f"Expires in {settings.reset_token_expire_minutes} minutes. Ignore if not requested.")
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10,
                              context=ssl.create_default_context()) as smtp:
            if settings.smtp_username:
                smtp.login(settings.smtp_username,
                           settings.smtp_password.get_secret_value() if settings.smtp_password else "")
            smtp.send_message(message)


def require_delivery(adapter):
    if not adapter.enabled:
        raise HTTPException(503, "Delivery provider is not configured")
