"""Run Alembic upgrades from the API process (Vercel has no migrate replica).

Desktop/script installs already call ``run_packaged.migrate()`` before serve.
Vercel previously excluded ``alembic/**`` from the function bundle, so Neon
stayed at whatever revision was last applied out-of-band while models moved
forward — SELECT of ``invoice.buyer_registration_type`` then 500s after login.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

_lock = threading.Lock()
_auto_done = False


def backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def alembic_config():
    from alembic.config import Config

    root = backend_root()
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))
    return cfg


def file_head() -> str | None:
    try:
        from alembic.script import ScriptDirectory

        heads = ScriptDirectory.from_config(alembic_config()).get_heads()
        return heads[0] if heads else None
    except Exception:
        return None


def db_revision() -> str | None:
    from sqlalchemy import text

    from db import engine

    try:
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
            return row[0] if row else None
    except Exception:
        return None


def upgrade_to_head() -> dict[str, Any]:
    from alembic import command

    before = db_revision()
    command.upgrade(alembic_config(), "head")
    after = db_revision()
    return {"before": before, "after": after, "file_head": file_head()}


def auto_migrate_enabled() -> bool:
    raw = (os.environ.get("SCHEMA_AUTO_MIGRATE") or "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    from services.app_runtime import is_vercel

    return is_vercel()


def maybe_auto_upgrade() -> dict[str, Any] | None:
    """Once per process: upgrade when running on Vercel (or SCHEMA_AUTO_MIGRATE).

    No-op in local/dev ``create_all`` mode. Failures are logged, never raised,
    so a locked or pooler-blocked DDL cannot take the API down.
    """
    global _auto_done
    if not auto_migrate_enabled():
        return None
    with _lock:
        if _auto_done:
            return None
        _auto_done = True
        try:
            result = upgrade_to_head()
            print(
                f"[schema_migrate] {result.get('before')} -> {result.get('after')} "
                f"(file head {result.get('file_head')})",
                flush=True,
            )
            return result
        except Exception:
            import traceback

            traceback.print_exc()
            return None
