"""Field-level encryption for sensitive MongoDB fields.

Enabled only when FIELD_ENCRYPTION_KEY is set in the environment.
When disabled (key missing or cryptography package absent), all
functions are transparent no-ops that pass values through unchanged —
so the rest of the codebase works identically with or without encryption.

Strategy
--------
- name / email values: Fernet symmetric encryption (AES-128-CBC + HMAC-SHA256).
- email lookup:        HMAC-SHA256 digest stored as `emailHash` field so we can
                       query without decrypting every document ("searchable encryption").
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac

try:
    from cryptography.fernet import Fernet, InvalidToken as _InvalidToken
    _CRYPTO_OK = True
except ImportError:                        # cryptography not installed
    Fernet = None                          # type: ignore[misc,assignment]
    _InvalidToken = Exception              # type: ignore[misc,assignment]
    _CRYPTO_OK = False

from config import FIELD_ENCRYPTION_KEY as _KEY

_fernet_instance: "Fernet | None" = None


def _fernet() -> "Fernet | None":
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance
    if not _KEY or not _CRYPTO_OK:
        return None
    # Derive a stable 32-byte key from the env var and base64url-encode it for Fernet.
    raw = hashlib.sha256(_KEY.encode()).digest()
    _fernet_instance = Fernet(base64.urlsafe_b64encode(raw))
    return _fernet_instance


def is_enabled() -> bool:
    """True when field-level encryption is active."""
    return bool(_KEY) and _CRYPTO_OK


def encrypt(value: str) -> str:
    """Encrypt *value*. Returns plaintext unchanged when encryption is disabled."""
    f = _fernet()
    if f is None:
        return value
    return f.encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    """Decrypt *value*. Returns value unchanged when encryption is disabled.

    Backward-compatible: if decryption fails (e.g. value was stored as
    plaintext before encryption was enabled) the original value is returned.
    """
    f = _fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode()).decode()
    except (_InvalidToken, Exception):
        return value   # plaintext stored before encryption was enabled


def email_hash(email: str) -> str:
    """HMAC-SHA256 of the normalised email — used as a searchable index field.

    When encryption is disabled, returns the normalised email itself so that
    existing ``find_one({"email": ...})`` queries continue to work.
    """
    normalised = email.lower().strip()
    if not _KEY:
        return normalised
    key = hashlib.sha256(_KEY.encode()).digest()
    return _hmac.new(key, normalised.encode(), hashlib.sha256).hexdigest()
