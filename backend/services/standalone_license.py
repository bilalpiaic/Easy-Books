"""Signed install license for standalone / on-premise Easy-Books copies.

A valid license in the **books data dir** (``.easy-books-license`` under
``~/.easy-books`` / ``EB_DATA_DIR``, never ``backend/``) unlocks the copy
after the 15-day trial. Tokens are Ed25519-signed:

    EB1.<base64url(json payload)>.<base64url(signature)>

Payload: ``v``, ``install_id``, ``email``, ``issued_at``, optional ``expires_at``.
The public key ships in this module so the **client install can verify**
a token. Minting tokens is **not** part of this product tree — field staff
use the private repo ``bilalpiaic/Easy-Books-license-issuer`` on their own
machine (seed ``EB_LICENSE_SIGNING_SEED``, never committed here). Tests
override the public key with ``EB_LICENSE_PUBKEY_HEX`` and call
``issue_token()`` with an ephemeral seed.

Signup with a real email does **not** license the install. ``EB_SKIP_DEMO_TRIAL=true``
remains a licensed override that skips the trial clock entirely.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from services.standalone_trial import books_data_dir, _format_dt, _parse_dt, _truthy

# Ed25519 public key (32-byte hex). Override with EB_LICENSE_PUBKEY_HEX in tests.
LICENSE_PUBKEY_HEX = "90523f715496512c8959efb045fc0bebbc25e784a8d0131a8ad6b73648f474df"
TOKEN_PREFIX = "EB1"
INSTALL_ID_NAME = ".install-id"
LICENSE_FILE_NAME = ".easy-books-license"


class LicenseError(ValueError):
    """Activation / verify failure. ``code`` is stable for API clients."""

    def __init__(self, message: str, code: str = "license_invalid"):
        super().__init__(message)
        self.code = code


def pubkey_hex() -> str:
    raw = (os.environ.get("EB_LICENSE_PUBKEY_HEX") or LICENSE_PUBKEY_HEX).strip().lower()
    return raw or LICENSE_PUBKEY_HEX


def signing_seed_hex() -> str | None:
    raw = (os.environ.get("EB_LICENSE_SIGNING_SEED") or "").strip().lower()
    return raw or None


def install_id_path() -> Path:
    return books_data_dir() / INSTALL_ID_NAME


def license_path() -> Path:
    return books_data_dir() / LICENSE_FILE_NAME


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * ((4 - len(text) % 4) % 4)
    try:
        return base64.urlsafe_b64decode((text + pad).encode("ascii"))
    except (ValueError, OSError) as exc:
        raise LicenseError("License token is not valid base64.", "license_malformed") from exc


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _write_once(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = payload.encode("utf-8")
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, encoded)
        finally:
            os.close(fd)
    except FileExistsError:
        return
    except OSError:
        return


def _write_replace(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = payload.encode("utf-8")
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, encoded)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _private_key(seed_hex: str) -> Ed25519PrivateKey:
    try:
        seed = bytes.fromhex(seed_hex.strip())
    except ValueError as exc:
        raise LicenseError("Signing seed is not valid hex.", "license_seed") from exc
    if len(seed) != 32:
        raise LicenseError("Signing seed must be 32 bytes (64 hex chars).", "license_seed")
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_key_from_seed(seed_hex: str) -> str:
    pub = _private_key(seed_hex).public_key()
    return pub.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def _public_key() -> Ed25519PublicKey:
    try:
        raw = bytes.fromhex(pubkey_hex())
    except ValueError as exc:
        raise LicenseError("License public key is not valid hex.", "license_pubkey") from exc
    if len(raw) != 32:
        raise LicenseError("License public key must be 32 bytes.", "license_pubkey")
    return Ed25519PublicKey.from_public_bytes(raw)


def read_install_id() -> str | None:
    try:
        text = install_id_path().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return text or None


def ensure_install_id() -> str:
    """Write-once UUID for this books data dir. Never rotates an existing id."""
    existing = read_install_id()
    if existing:
        return existing
    new_id = str(uuid.uuid4())
    _write_once(install_id_path(), new_id + "\n")
    return read_install_id() or new_id


def issue_token(
    *,
    install_id: str,
    email: str,
    seed_hex: str | None = None,
    expires_at: datetime | None = None,
    issued_at: datetime | None = None,
) -> str:
    """Staff issuer: sign a license token. Requires the private seed."""
    seed = (seed_hex or signing_seed_hex() or "").strip()
    if not seed:
        raise LicenseError(
            "Set EB_LICENSE_SIGNING_SEED to issue a license (staff only).",
            "license_seed",
        )
    iid = (install_id or "").strip()
    addr = (email or "").strip().lower()
    if not iid:
        raise LicenseError("install_id is required.", "license_malformed")
    if not addr or "@" not in addr:
        raise LicenseError("A valid email is required.", "license_email")
    issued = issued_at or _now()
    payload: dict[str, Any] = {
        "v": 1,
        "install_id": iid,
        "email": addr,
        "issued_at": _format_dt(issued),
    }
    if expires_at is not None:
        payload["expires_at"] = _format_dt(expires_at)
    raw = _canonical_payload(payload)
    sig = _private_key(seed).sign(raw)
    return f"{TOKEN_PREFIX}.{_b64url_encode(raw)}.{_b64url_encode(sig)}"


def parse_token(token: str) -> dict[str, Any]:
    """Verify the Ed25519 signature and return the payload dict."""
    text = (token or "").strip().replace("\r", "").replace("\n", "").replace(" ", "")
    parts = text.split(".")
    if len(parts) != 3 or parts[0] != TOKEN_PREFIX:
        raise LicenseError(
            "License token must look like EB1.<payload>.<signature>.",
            "license_malformed",
        )
    raw = _b64url_decode(parts[1])
    sig = _b64url_decode(parts[2])
    try:
        _public_key().verify(sig, raw)
    except InvalidSignature as exc:
        raise LicenseError("License signature is not valid.", "license_signature") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LicenseError("License payload is not valid JSON.", "license_malformed") from exc
    if not isinstance(payload, dict):
        raise LicenseError("License payload must be an object.", "license_malformed")
    if int(payload.get("v") or 0) != 1:
        raise LicenseError("Unsupported license version.", "license_version")
    iid = str(payload.get("install_id") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    if not iid or not email:
        raise LicenseError("License is missing install_id or email.", "license_malformed")
    payload["install_id"] = iid
    payload["email"] = email
    return payload


def _payload_expired(payload: dict[str, Any]) -> bool:
    raw = payload.get("expires_at")
    if not raw:
        return False
    ends = _parse_dt(str(raw))
    if ends is None:
        return False
    return _now() >= ends


def existing_user_emails() -> list[tuple[str, str]]:
    """``(email, role)`` from on-disk SQLite, if any. Empty when no DB yet."""
    try:
        from local_config import sqlite_path

        db_path = sqlite_path()
        if not Path(db_path).is_file():
            return []
        con = sqlite3.connect(db_path)
        try:
            rows = con.execute('SELECT email, role FROM "user"').fetchall()
        except sqlite3.Error:
            return []
        finally:
            con.close()
    except OSError:
        return []
    out: list[tuple[str, str]] = []
    for email, role in rows:
        addr = str(email or "").strip().lower()
        if addr:
            out.append((addr, str(role or "").strip().lower()))
    return out


def emails_from_users(users: list[Any] | None) -> list[tuple[str, str]]:
    if not users:
        return []
    out: list[tuple[str, str]] = []
    for user in users:
        addr = str(getattr(user, "email", "") or "").strip().lower()
        role = str(getattr(user, "role", "") or "").strip().lower()
        if addr:
            out.append((addr, role))
    return out


def _email_allowed(license_email: str, existing: list[tuple[str, str]] | None) -> bool:
    """If users exist, the license email must match one of them (owners first)."""
    if not existing:
        return True
    want = (license_email or "").strip().lower()
    owners = [e for e, role in existing if role == "owner"]
    if owners:
        return want in owners
    return want in {e for e, _ in existing}


def _email_mismatch_message(existing: list[tuple[str, str]]) -> str:
    owners = [e for e, role in existing if role == "owner"]
    if owners:
        return (
            "License email must match an owner account on this install "
            f"(found {', '.join(owners)})."
        )
    return "License email must match a user account on this install."


def activate_token(
    token: str,
    *,
    emails: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Verify, bind to this install id, and write ``.easy-books-license``."""
    payload = parse_token(token)
    iid = ensure_install_id()
    if payload["install_id"] != iid:
        raise LicenseError(
            "This license was issued for a different installation.",
            "license_install_id",
        )
    if _payload_expired(payload):
        raise LicenseError("This license has expired.", "license_expired")
    roster = emails if emails is not None else existing_user_emails()
    if not _email_allowed(payload["email"], roster):
        raise LicenseError(_email_mismatch_message(roster), "license_email")
    record = {
        "v": 1,
        "token": (token or "").strip().replace("\r", "").replace("\n", "").replace(" ", ""),
        "activated_at": _format_dt(_now()),
        "install_id": payload["install_id"],
        "email": payload["email"],
        "issued_at": payload.get("issued_at"),
        "expires_at": payload.get("expires_at"),
    }
    _write_replace(license_path(), json.dumps(record, indent=2) + "\n")
    return license_status()


def _read_license_file() -> dict[str, Any] | None:
    try:
        raw = license_path().read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def is_licensed() -> bool:
    """True when a currently-valid signed license is on disk for this install."""
    data = _read_license_file()
    if not data:
        return False
    token = str(data.get("token") or "")
    try:
        payload = parse_token(token)
    except LicenseError:
        return False
    iid = read_install_id()
    if not iid or payload["install_id"] != iid:
        return False
    if _payload_expired(payload):
        return False
    return True


def license_status() -> dict[str, Any]:
    """Public payload for GET /api/license/status (allowed while locked)."""
    from services.standalone_trial import demo_trial_applies, trial_info

    skip = _truthy("EB_SKIP_DEMO_TRIAL")
    standalone = demo_trial_applies() or skip
    licensed = is_licensed()
    if standalone or licensed:
        iid = ensure_install_id()
    else:
        iid = read_install_id()
    data = _read_license_file() if licensed else None
    payload = None
    if licensed and data:
        try:
            payload = parse_token(str(data.get("token") or ""))
        except LicenseError:
            payload = None
            licensed = False
    return {
        "install_id": iid,
        "licensed": licensed,
        "skip_env": skip,
        "standalone": standalone or licensed,
        "email": (payload or {}).get("email") if licensed else None,
        "issued_at": (payload or {}).get("issued_at") if licensed else None,
        "expires_at": (payload or {}).get("expires_at") if licensed else None,
        "activated_at": (data or {}).get("activated_at") if licensed else None,
        "data_dir": str(books_data_dir()),
        "trial": trial_info(),
    }
