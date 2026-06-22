"""add_module_meta_to_tenant

Revision ID: 9a704c7672d5
Revises: 0027_pra_buyer_fields
Create Date: 2026-06-22 22:29:56.904468

Adds module_meta JSON column to tenant for per-module billing metadata.
All FK/index noise from autogenerate is stripped — SQLite can't ADD CONSTRAINT.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '9a704c7672d5'
down_revision: Union[str, Sequence[str], None] = '0027_pra_buyer_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.add_column(
            sa.Column("module_meta", sqlmodel.sql.sqltypes.AutoString(),
                      nullable=False, server_default="{}")
        )


def downgrade() -> None:
    with op.batch_alter_table("tenant") as batch_op:
        batch_op.drop_column("module_meta")
