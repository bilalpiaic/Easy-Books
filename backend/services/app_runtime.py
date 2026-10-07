"""Process role and host-runtime flags (#424 / #425).

No models imports — safe from db.py and alembic/env.py.
"""
from __future__ import annotations

import os


def is_vercel() -> bool:
    return os.environ.get("VERCEL", "").strip().lower() in ("1", "true", "yes", "on")


def _flag(name: str, default: bool | None = None) -> bool | None:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def app_role() -> str:
    """api | migrate | worker. Empty means compose/desktop default (API + migrate)."""
    return (os.environ.get("APP_ROLE") or "").strip().lower()


def postgres_pool_kwargs() -> dict:
    """QueuePool settings. Vercel stays 1+0; everything else defaults ~5/5."""
    if is_vercel():
        return {"pool_size": 1, "max_overflow": 0}
    return {
        "pool_size": int(os.environ.get("DB_POOL_SIZE") or 5),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW") or 5),
        "pool_timeout": float(os.environ.get("DB_POOL_TIMEOUT") or 30),
        "pool_recycle": int(os.environ.get("DB_POOL_RECYCLE") or 1800),
    }


def _normalize_pg_url(url: str) -> str:
    """Pin the SQLAlchemy driver to psycopg2 (the package we ship).

    SQLAlchemy 2 maps bare ``postgresql://`` to the psycopg3 dialect
    (``sqlalchemy.dialects.postgresql.psycopg``). We depend on
    ``psycopg2-binary``, so an unpinned Neon/Vercel URL crashes the
    serverless function at import with ``ModuleNotFoundError: psycopg``.
    Explicit ``+psycopg2`` / ``+psycopg`` / ``+asyncpg`` schemes are left
    alone. sslmode still defaults to ``require`` for managed Postgres.
    """
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql") and "sslmode" not in url:
        sslmode = (os.environ.get("DB_SSLMODE") or "require").strip() or "require"
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode={sslmode}"
    return url


def _neon_direct_from_pooler(url: str) -> str:
    """Neon pooled hostnames are ``ep-…-pooler.region.aws.neon.tech``.

    DDL (Alembic) is unreliable through the transaction pooler; strip the
    suffix when ``DATABASE_URL_DIRECT`` is unset so Vercel can still migrate.
    """
    if "-pooler." in url:
        return url.replace("-pooler.", ".", 1)
    return url


def resolve_database_url(*, for_alembic: bool = False) -> str | None:
    """App uses DATABASE_URL (may be a pooler). Alembic prefers DATABASE_URL_DIRECT."""
    raw = ""
    if for_alembic:
        raw = (os.environ.get("DATABASE_URL_DIRECT") or "").strip()
        if not raw:
            raw = _neon_direct_from_pooler(
                (os.environ.get("DATABASE_URL") or "").strip()
            )
    else:
        raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        return None
    return _normalize_pg_url(raw)


def allow_create_all_bootstrap() -> bool:
    """True when lifespan may call SQLModel.create_all.

    Production must use SCHEMA_BOOTSTRAP=alembic (#424).
    """
    mode = (os.environ.get("SCHEMA_BOOTSTRAP") or "create_all").strip().lower()
    if mode != "create_all":
        return False
    from services.security_policy import is_production
    if is_production():
        raise RuntimeError(
            "SCHEMA_BOOTSTRAP=create_all is not allowed in production. "
            "Set SCHEMA_BOOTSTRAP=alembic and run APP_ROLE=migrate "
            "(alembic upgrade head) before starting API replicas."
        )
    return True


def run_background_jobs() -> bool:
    """#425 — API replicas default off when APP_ROLE=api; worker/desktop on.

    RUN_BACKGROUND_JOBS and RUN_SCHEDULERS are aliases. Vercel defaults off.
    """
    explicit = _flag("RUN_BACKGROUND_JOBS")
    if explicit is None:
        explicit = _flag("RUN_SCHEDULERS")
    if explicit is not None:
        return explicit
    if is_vercel():
        return False
    role = app_role()
    if role == "api":
        return False
    if role == "migrate":
        return False
    return True


def run_in_process_schedulers() -> bool:
    """True when this API process should host overdue/webhook/bank loops.

    Desktop without Redis keeps in-process loops. Compose/SaaS with REDIS_URL
    leaves crons to the ARQ worker so two API replicas do not double-send.
    """
    if not run_background_jobs():
        return False
    if (os.environ.get("REDIS_URL") or "").strip():
        return False
    return True


def self_update_enabled() -> bool:
    """git-pull updater is desktop/script only (#428). Off in production SaaS."""
    explicit = _flag("ENABLE_SELF_UPDATE")
    if explicit is not None:
        return explicit
    from services.security_policy import is_production
    if is_production():
        return False
    if app_role():
        return False
    return True
