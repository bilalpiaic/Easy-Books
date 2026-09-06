"""Tenant print-template clones

Revision ID: 0082_print_templates
Revises: 0081_form_schema
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0082_print_templates"
down_revision: Union[str, Sequence[str], None] = "0081_form_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "print_template"):
        return
    op.create_table(
        "print_template",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("html", sa.Text(), nullable=True),
        sa.Column("is_builtin_override", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_extension_id", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "entity", "key",
            name="uq_print_template_tenant_entity_key",
        ),
    )
    op.create_index("ix_print_template_tenant_id", "print_template", ["tenant_id"])
    op.create_index(
        "ix_print_template_tenant_entity",
        "print_template",
        ["tenant_id", "entity"],
    )
    op.create_index(
        "ix_print_template_source_extension_id",
        "print_template",
        ["source_extension_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "print_template"):
        op.drop_table("print_template")
