"""weighbridge stock-form links — wb_doc_link

Revision ID: 0090_wb_doc_link
Revises: 0089_pra_di_v112
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0090_wb_doc_link"
down_revision: Union[str, Sequence[str], None] = "0089_pra_di_v112"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "wb_doc_link"):
        return
    op.create_table(
        "wb_doc_link",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tenant_id", sa.Integer, nullable=False, index=True),
        sa.Column("ticket_id", sa.Integer, nullable=False, index=True),
        sa.Column("doc_type", sa.String, nullable=False, index=True),
        sa.Column("doc_id", sa.Integer, nullable=False, index=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=True),
        sa.UniqueConstraint("tenant_id", "ticket_id", "doc_type", "doc_id", name="uq_wb_doc_link"),
    )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "wb_doc_link"):
        op.drop_table("wb_doc_link")
