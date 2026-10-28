"""Authenticated encryption with an external Fernet key ring (first key writes)."""
import json

from cryptography.fernet import Fernet, MultiFernet
from fastapi import HTTPException


def cipher(settings):
    if not settings.identifier_encryption_keys:
        raise HTTPException(503, "Identifier encryption keys are not configured")
    return MultiFernet([Fernet(key.get_secret_value().encode()) for key in settings.identifier_encryption_keys])


def encrypt(settings, value):
    return cipher(settings).encrypt(json.dumps(value).encode())


def decrypt(settings, value):
    return json.loads(cipher(settings).decrypt(value))
