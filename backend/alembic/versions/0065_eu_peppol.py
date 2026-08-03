"""Peppol / EU VAT e-invoice fields + submission log (#266).

Revision ID: 0065_eu_peppol
Revises: 0064_in_gst
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0065_eu_peppol"
down_revision: Union[str, Sequence[str], None] = "0064_in_gst"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        if "peppol_status" not in inv_cols:
            batch.add_column(sa.Column("peppol_status", sa.String(), nullable=True))
        if "peppol_document_id" not in inv_cols:
            batch.add_column(sa.Column("peppol_document_id", sa.String(), nullable=True))
        if "peppol_submitted_at" not in inv_cols:
            batch.add_column(sa.Column("peppol_submitted_at", sa.DateTime(), nullable=True))

    if not bind.dialect.has_table(bind, "peppolsubmissionlog"):
        op.create_table(
            "peppolsubmissionlog",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("invoice_id", sa.Integer(), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("request_payload", sa.String(), nullable=False),
            sa.Column("response_payload", sa.String(), nullable=True),
            sa.Column("status", sa.String(), nullable=False, server_default="error"),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("endpoint", sa.String(), nullable=True),
            sa.Column("error_message", sa.String(), nullable=True),
            sa.Column("sandbox", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("document_id", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "peppolsubmissionlog"):
        op.drop_table("peppolsubmissionlog")

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        for col in ("peppol_submitted_at", "peppol_document_id", "peppol_status"):
            if col in inv_cols:
                batch.drop_column(col)
