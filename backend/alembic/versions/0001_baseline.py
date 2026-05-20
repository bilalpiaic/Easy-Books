"""baseline — create all tables from current SQLModel metadata

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-19

This baseline materialises the current schema (P0 — Decimal money, COGS, JE
CHECK constraint, InventoryLayer, etc.) in one shot rather than reconstructing
the history from before Alembic was adopted.

For brand-new databases: `alembic upgrade head` creates every table.
For existing dev databases already populated by SQLModel.metadata.create_all
on startup: run `alembic stamp head` once so Alembic considers this revision
applied without re-creating tables.
"""
from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel

import models  # noqa: F401 — registers tables on SQLModel.metadata


revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent: create_all is a no-op on tables that already exist.
    SQLModel.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    SQLModel.metadata.drop_all(bind=op.get_bind())
