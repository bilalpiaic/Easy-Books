"""Idempotent seal of Settings KV secrets as ``enc:v1:`` (#428).

Walks ``SECRET_SETTINGS_KEYS`` (AI keys, WhatsApp token, PRA/ZATCA/Peppol/
MTD/MyInvois secrets). Plaintext values are encrypted. Rows already prefixed
``enc:v1:`` are skipped. Legacy unprefixed Fernet (JWT-derived) is re-wrapped
onto ``DATA_ENCRYPTION_KEY`` when that env var is set.

Usage::

    cd backend && PYTHONPATH=. uv run python -m scripts.encrypt_settings
    PYTHONPATH=. uv run python -m scripts.encrypt_settings --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

from sqlmodel import Session, select

from models import Settings
from routers.settings import SECRET_SETTINGS_KEYS
from services.crypto_secrets import PREFIX, decrypt_secret, seal_setting


def _needs_seal(value: str | None) -> str | None:
    """Return ciphertext to write, or None if the row is already sealed."""
    if not value:
        return None
    if value.startswith(PREFIX):
        return None
    try:
        plain = decrypt_secret(value)
    except ValueError:
        return seal_setting(value)
    if (os.environ.get("DATA_ENCRYPTION_KEY") or "").strip():
        sealed = seal_setting(plain)
        return sealed if sealed != value else None
    return None


def encrypt_settings_rows(session: Session, *, dry_run: bool = False) -> dict:
    stats = {"scanned": 0, "sealed": 0, "skipped": 0}
    rows = session.exec(
        select(Settings).where(Settings.key.in_(list(SECRET_SETTINGS_KEYS)))
    ).all()
    for row in rows:
        stats["scanned"] += 1
        new = _needs_seal(row.value)
        if new is None:
            stats["skipped"] += 1
            continue
        stats["sealed"] += 1
        if not dry_run:
            row.value = new
            session.add(row)
    if not dry_run:
        session.commit()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    from db import engine

    with Session(engine) as session:
        stats = encrypt_settings_rows(session, dry_run=args.dry_run)
    print(f"[encrypt_settings] {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
