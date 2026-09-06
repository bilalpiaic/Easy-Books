"""Tenant custom fields (x.*) on documents

Revision ID: 0080_custom_fields
Revises: 0079_app_update_notices
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0080_custom_fields"
down_revision: Union[str, Sequence[str], None] = "0079_app_update_notices"
branch_labels = None
depends_on = None

_DOC_TABLES = ("invoice", "bill", "customer", "product", "vendor")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not bind.dialect.has_table(bind, "custom_field_def"):
        op.create_table(
            "custom_field_def",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("entity", sa.String(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("label", sa.String(), nullable=False),
            sa.Column("type", sa.String(), nullable=False, server_default="text"),
            sa.Column("enum_values", sa.JSON(), nullable=True),
            sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("show_on_form", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("show_on_print", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("show_on_list", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("archived_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "tenant_id", "entity", "key",
                name="uq_custom_field_def_tenant_entity_key",
            ),
        )
        op.create_index("ix_custom_field_def_tenant_id", "custom_field_def", ["tenant_id"])
        op.create_index(
            "ix_custom_field_def_tenant_entity",
            "custom_field_def",
            ["tenant_id", "entity"],
        )
        op.create_index("ix_custom_field_def_archived_at", "custom_field_def", ["archived_at"])
        # Unique (tenant, entity, key) is created with the table; SQLite cannot
        # ADD CONSTRAINT via ALTER. App-level tenant checks enforce integrity.

    for table in _DOC_TABLES:
        if not bind.dialect.has_table(bind, table):
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "custom_fields" in cols:
            continue
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column(
                    "custom_fields",
                    sa.JSON(),
                    nullable=False,
                    server_default="{}",
                )
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in _DOC_TABLES:
        if not bind.dialect.has_table(bind, table):
            continue
        cols = {c["name"] for c in insp.get_columns(table)}
        if "custom_fields" not in cols:
            continue
        with op.batch_alter_table(table) as batch:
            batch.drop_column("custom_fields")
    if bind.dialect.has_table(bind, "custom_field_def"):
        op.drop_table("custom_field_def")
