"""source_extension_id on custom_field_def (#376)

Revision ID: 0083_field_source_extension
Revises: 0082_print_templates
Create Date: 2026-09-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0083_field_source_extension"
down_revision: Union[str, Sequence[str], None] = "0082_print_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "custom_field_def"):
        return
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("custom_field_def")}
    if "source_extension_id" in cols:
        return
    with op.batch_alter_table("custom_field_def") as batch:
        batch.add_column(sa.Column("source_extension_id", sa.String(), nullable=True))
    op.create_index(
        "ix_custom_field_def_source_extension_id",
        "custom_field_def",
        ["source_extension_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "custom_field_def"):
        return
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("custom_field_def")}
    if "source_extension_id" not in cols:
        return
    op.drop_index("ix_custom_field_def_source_extension_id", table_name="custom_field_def")
    with op.batch_alter_table("custom_field_def") as batch:
        batch.drop_column("source_extension_id")
