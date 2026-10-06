"""Idempotent copy of logos, avatars, attachments, and PDFs into canonical keys.

Canonical layout (#426): ``tenants/{tenant_id}/{kind}/{filename}``.

Copies from:
- local ``uploads_dir()`` leftover paths (``{tid}/avatars/``, ``{tid}/pdfs/``,
  ``{tid}/{uuid}.ext`` logos, ``{tid}/{parent}/{id}/{file}`` attachments)
- Attachment rows whose ``file_path`` is not yet canonical (local or Supabase)

Does not delete source objects. Safe to re-run.

Usage::

    cd backend && PYTHONPATH=. uv run python -m scripts.migrate_storage
    PYTHONPATH=. uv run python -m scripts.migrate_storage --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlmodel import Session, select

from local_config import uploads_dir
from models import Attachment, Settings, User
from services.storage import download_file, object_key, upload_file


def _already_canonical(key: str) -> bool:
    return key.lstrip("/").startswith("tenants/")


def _infer(rel: Path) -> tuple[str, str] | None:
    parts = rel.parts
    if not parts or parts[0] == "tenants":
        return None
    tid = parts[0]
    if not tid.isdigit():
        return None
    if len(parts) >= 3 and parts[1] == "avatars":
        return "avatar", object_key(int(tid), "avatar", parts[-1])
    if len(parts) >= 3 and parts[1] == "pdfs":
        return "pdf", object_key(int(tid), "pdf", parts[-1])
    if len(parts) == 2:
        return "logo", object_key(int(tid), "logo", parts[1])
    if len(parts) >= 4:
        return "attachment", object_key(int(tid), "attachment", parts[-1])
    return None


def _copy_if_missing(src_bytes: bytes, dest_key: str, content_type: str, *, dry_run: bool) -> str:
    try:
        download_file(dest_key)
        return "exists"
    except FileNotFoundError:
        pass
    if dry_run:
        return "would_copy"
    upload_file(dest_key, src_bytes, content_type)
    return "copied"


def migrate_local_files(*, dry_run: bool) -> dict:
    root = uploads_dir()
    stats = {"scanned": 0, "copied": 0, "exists": 0, "skipped": 0}
    if not root.exists():
        return stats
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        stats["scanned"] += 1
        inferred = _infer(rel)
        if inferred is None:
            stats["skipped"] += 1
            continue
        _kind, dest = inferred
        mime = "application/octet-stream"
        if dest.endswith(".pdf"):
            mime = "application/pdf"
        elif dest.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
            mime = "image/png"
        action = _copy_if_missing(path.read_bytes(), dest, mime, dry_run=dry_run)
        if action == "exists":
            stats["exists"] += 1
        elif action in ("copied", "would_copy"):
            stats["copied"] += 1
    return stats


def migrate_db_rows(session: Session, *, dry_run: bool) -> dict:
    stats = {"attachments": 0, "logos": 0, "avatars": 0, "errors": 0}
    rows = session.exec(select(Attachment)).all()
    for att in rows:
        if _already_canonical(att.file_path):
            continue
        dest = object_key(att.tenant_id, "attachment", att.file_name or Path(att.file_path).name)
        try:
            data = download_file(att.file_path)
        except FileNotFoundError:
            stats["errors"] += 1
            continue
        action = _copy_if_missing(
            data, dest, att.mime_type or "application/octet-stream", dry_run=dry_run
        )
        if action in ("copied", "would_copy", "exists") and not dry_run:
            att.file_path = dest
            session.add(att)
            stats["attachments"] += 1
        elif action == "would_copy":
            stats["attachments"] += 1

    logos = session.exec(select(Settings).where(Settings.key == "logo_url")).all()
    for row in logos:
        url = row.value or ""
        if "/api/files/tenants/" in url:
            continue
        key = url.split("/api/files/", 1)[-1].split("?", 1)[0] if "/api/files/" in url else ""
        if not key:
            continue
        if _already_canonical(key):
            continue
        dest = object_key(row.tenant_id, "logo", Path(key).name)
        try:
            data = download_file(key)
        except FileNotFoundError:
            stats["errors"] += 1
            continue
        action = _copy_if_missing(data, dest, "image/png", dry_run=dry_run)
        if not dry_run and action in ("copied", "exists"):
            row.value = f"/api/files/{dest}"
            session.add(row)
            stats["logos"] += 1
        elif action == "would_copy":
            stats["logos"] += 1

    users = session.exec(select(User).where(User.avatar_url != None)).all()  # noqa: E711
    for user in users:
        url = user.avatar_url or ""
        if "/api/files/tenants/" in url:
            continue
        key = url.split("/api/files/", 1)[-1].split("?", 1)[0] if "/api/files/" in url else ""
        legacy = uploads_dir() / str(user.tenant_id) / "avatars"
        data = None
        src_name = None
        if key:
            try:
                data = download_file(key)
                src_name = Path(key).name
            except FileNotFoundError:
                data = None
        if data is None and legacy.exists():
            matches = list(legacy.glob(f"{user.id}.*"))
            if matches:
                data = matches[0].read_bytes()
                src_name = matches[0].name
        if not data or not src_name:
            continue
        dest = object_key(user.tenant_id, "avatar", src_name)
        action = _copy_if_missing(data, dest, "image/png", dry_run=dry_run)
        if not dry_run and action in ("copied", "exists"):
            user.avatar_url = f"/api/files/{dest}"
            session.add(user)
            stats["avatars"] += 1
        elif action == "would_copy":
            stats["avatars"] += 1

    if not dry_run:
        session.commit()
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from db import engine

    local_stats = migrate_local_files(dry_run=args.dry_run)
    print(f"[migrate_storage] local files: {local_stats}")
    with Session(engine) as session:
        db_stats = migrate_db_rows(session, dry_run=args.dry_run)
    print(f"[migrate_storage] db rows: {db_stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
