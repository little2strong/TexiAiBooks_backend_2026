import ssl

import pytest

from app.services.delivery import SMTPResetDelivery


@pytest.mark.parametrize("url", [None, "http://app.example/reset", "https://app.example/reset#existing"])
def test_reset_delivery_requires_https_without_fragment(settings, url):
    settings.smtp_host = "smtp.example.com"
    settings.smtp_from = "accounts@example.com"
    settings.password_reset_url = url
    assert not SMTPResetDelivery(settings).enabled


def test_smtp_adapter_uses_verified_tls_and_fragment_without_real_network(settings, monkeypatch):
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout, context):
            captured.update(host=host, port=port, timeout=timeout, context=context)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, username, password):
            captured["auth"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr("app.services.delivery.smtplib.SMTP_SSL", FakeSMTP)
    settings.smtp_host = "smtp.example.com"
    settings.smtp_from = "accounts@example.com"
    settings.smtp_username = "smtp-account"
    settings.smtp_password = settings.jwt_secret_key.__class__("test-smtp-password")
    settings.password_reset_url = "https://app.example/reset"
    adapter = SMTPResetDelivery(settings)
    assert adapter.enabled
    adapter.send_reset("driver@example.com", "test-reset-secret")
    assert captured["port"] == 465 and captured["timeout"] == 10
    assert captured["context"].verify_mode == ssl.CERT_REQUIRED and captured["context"].check_hostname
    assert captured["auth"] == ("smtp-account", "test-smtp-password")
    message = captured["message"]
    assert message["To"] == "driver@example.com"
    assert "https://app.example/reset#token=test-reset-secret" in message.get_content()
