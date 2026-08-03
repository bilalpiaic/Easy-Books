"""Saudi ZATCA e-invoice fields + submission log (#264).

Revision ID: 0063_sa_zatca
Revises: 0062_intercompany
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0063_sa_zatca"
down_revision: Union[str, Sequence[str], None] = "0062_intercompany"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        if "zatca_status" not in inv_cols:
            batch.add_column(sa.Column("zatca_status", sa.String(), nullable=True))
        if "zatca_uuid" not in inv_cols:
            batch.add_column(sa.Column("zatca_uuid", sa.String(), nullable=True))
        if "zatca_hash" not in inv_cols:
            batch.add_column(sa.Column("zatca_hash", sa.String(), nullable=True))
        if "zatca_qr" not in inv_cols:
            batch.add_column(sa.Column("zatca_qr", sa.String(), nullable=True))
        if "zatca_submitted_at" not in inv_cols:
            batch.add_column(sa.Column("zatca_submitted_at", sa.DateTime(), nullable=True))

    if not bind.dialect.has_table(bind, "zatcasubmissionlog"):
        op.create_table(
            "zatcasubmissionlog",
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
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "zatcasubmissionlog"):
        op.drop_table("zatcasubmissionlog")

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        for col in ("zatca_submitted_at", "zatca_qr", "zatca_hash", "zatca_uuid", "zatca_status"):
            if col in inv_cols:
                batch.drop_column(col)
