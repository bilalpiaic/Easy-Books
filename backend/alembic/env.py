"""
Alembic migration environment.

Pulls the DB URL from $DATABASE_URL (same precedence as the app) so the same
migrations apply to SQLite (dev) and Postgres (prod) without code changes.
Targets SQLModel.metadata so future `alembic revision --autogenerate` picks
up new tables and columns added in models.py.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the backend package importable so we can pull in SQLModel metadata.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import SQLModel
import models  # noqa: F401 — registers every table on SQLModel.metadata

config = context.config

# Resolve DATABASE_URL the same way db.py does — including the Heroku-style
# `postgres://` → `postgresql://` rewrite that some Postgres providers still emit.
db_url = os.environ.get("DATABASE_URL") or "sqlite:///database.db"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
