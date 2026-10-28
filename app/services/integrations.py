"""Provider boundaries. Implementations must be installed explicitly at startup.

Tests inject controlled adapters. None of these interfaces is a real provider
implementation or evidence of production recognition, delivery or acceptance.
"""
from typing import Protocol

from fastapi import HTTPException


class HMRCProvider(Protocol):
    recognition_enabled: bool
    def authorization_url(self, state: str, return_route: str) -> str: ...
    def exchange(self, code: str) -> dict: ...
    def businesses(self, tokens: dict) -> list[dict]: ...
    def obligations(self, tokens: dict, tax_year: str) -> list[dict]: ...
    def submit(self, tokens: dict, business: dict, snapshot: dict) -> dict: ...
    def reconcile(self, tokens: dict, business: dict, snapshot: dict) -> dict: ...


class BillingProvider(Protocol):
    def verify_event(self, body: bytes, headers: dict) -> dict: ...
    def checkout(self, owner_id: str, plan: dict, return_route: str, idempotency_key: str) -> dict: ...
    def cancel(self, subscription: dict, reason: str | None, idempotency_key: str) -> dict: ...


class AssistantProvider(Protocol):
    def respond(self, messages: list[dict], context: list[dict], locale: str) -> dict: ...


def provider(request, name):
    value=getattr(request.app.state,name,None)
    if value is None: raise HTTPException(503,f"{name.replace('_',' ')} is not configured")
    return value


def safe_call(operation, *args):
    try: return operation(*args)
    except HTTPException as exc:
        raise HTTPException(exc.status_code,"Provider request rejected") from None
    except Exception: raise HTTPException(503,"External provider unavailable") from None
