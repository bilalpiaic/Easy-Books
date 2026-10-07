"""Fernet helpers for TOTP, Plaid, and Settings KV secrets (#118 / #428).

Primary key is ``DATA_ENCRYPTION_KEY`` (Fernet or any passphrase hashed to
one). ``DATA_ENCRYPTION_PREVIOUS_KEYS`` is a comma-separated rotation list.
Legacy JWT-derived tokens still decrypt until re-encrypted.
New ciphertext is stored as ``enc:v1:<fernet>``.
"""
from __future__ import annotations

import base64
import hashlib
import os

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from auth import SECRET_KEY

PREFIX = "enc:v1:"


def _fernet_from_material(raw: str) -> Fernet:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("empty key material")
    try:
        return Fernet(raw.encode() if isinstance(raw, str) else raw)
    except Exception:
        digest = hashlib.sha256(raw.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def _jwt_fernet() -> Fernet:
    digest = hashlib.sha256((SECRET_KEY or "").encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _fernet_list() -> list[Fernet]:
    keys: list[Fernet] = []
    primary = (os.environ.get("DATA_ENCRYPTION_KEY") or "").strip()
    if primary:
        keys.append(_fernet_from_material(primary))
    prev = (os.environ.get("DATA_ENCRYPTION_PREVIOUS_KEYS") or "").strip()
    for part in prev.split(","):
        part = part.strip()
        if part:
            keys.append(_fernet_from_material(part))
    keys.append(_jwt_fernet())
    return keys


def _primary() -> Fernet:
    return _fernet_list()[0]


def encrypt_secret(plain: str) -> str:
    token = _primary().encrypt(plain.encode()).decode()
    return PREFIX + token


def decrypt_secret(token: str) -> str:
    raw = token
    if token.startswith(PREFIX):
        raw = token[len(PREFIX):]
    multi = MultiFernet(_fernet_list())
    try:
        return multi.decrypt(raw.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("unable to decrypt secret") from exc


def reveal_setting(value: str | None) -> str | None:
    """Decrypt ``enc:v1:`` settings; plaintext otherwise."""
    if not value:
        return value
    if value.startswith(PREFIX):
        return decrypt_secret(value)
    return value


def seal_setting(plain: str) -> str:
    """Encrypt a settings secret. Empty stays empty."""
    if not plain:
        return plain
    if plain.startswith(PREFIX):
        return plain
    return encrypt_secret(plain)
