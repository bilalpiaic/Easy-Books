"""Tenant form schema hide/show/required overlay

Revision ID: 0081_form_schema
Revises: 0080_custom_fields
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0081_form_schema"
down_revision: Union[str, Sequence[str], None] = "0080_custom_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "form_schema"):
        return
    op.create_table(
        "form_schema",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False, server_default="*"),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("tenant_id", "entity", "role"),
    )
    op.create_index("ix_form_schema_tenant_id", "form_schema", ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "form_schema"):
        op.drop_table("form_schema")
