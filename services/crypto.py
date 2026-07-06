"""
Symmetric encryption for secrets the app must be able to read back
later -- OAuth refresh tokens and app passwords for candidate-connected
email accounts. Uses Fernet (AES-128-CBC + HMAC via the `cryptography`
library), key sourced from ENCRYPTION_KEY, never stored in the DB or
committed to the repo -- same "no hardcoded/default secret" pattern as
JWT_SECRET_KEY in api/auth.py.

NOT for login passwords -- those are one-way hashed with bcrypt
(api/auth.py) and never need to be read back. This module is
specifically for secrets that must be decrypted at the moment of actual
use (e.g. calling Gmail's API on the candidate's behalf) and never
stored or logged in decrypted form otherwise.
"""
from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "ENCRYPTION_KEY is not set. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "and set it in your .env -- there is no default, on purpose, since a "
            "default key would make every deployment's encrypted secrets readable "
            "by anyone who read this file."
        )
    key_bytes = key.encode("utf-8") if isinstance(key, str) else key
    return Fernet(key_bytes)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as e:
        raise RuntimeError(
            "Failed to decrypt secret -- wrong ENCRYPTION_KEY, or the stored value was corrupted."
        ) from e
