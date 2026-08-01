"""UAE VAT e-invoice log table

Revision ID: 0049_uae_einvoice_log
Revises: 0048_hc_patient_email_lab_publish
Create Date: 2026-08-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0049_uae_einvoice_log"
down_revision: Union[str, Sequence[str], None] = "0048_hc_patient_email_lab_publish"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "uaeeinvoicelog"):
        op.create_table(
            "uaeeinvoicelog",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("tenant_id", sa.Integer(), nullable=False, index=True),
            sa.Column("invoice_id", sa.Integer(), nullable=False, index=True),
            sa.Column("attempt_at", sa.DateTime(), nullable=False),
            sa.Column("endpoint", sa.String(), nullable=False),
            sa.Column("request_json", sa.String(), nullable=False),
            sa.Column("response_uuid", sa.String(), nullable=True),
            sa.Column("response_json", sa.String(), nullable=True),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("error_message", sa.String(), nullable=True),
            sa.Column("sandbox", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "uaeeinvoicelog"):
        op.drop_table("uaeeinvoicelog")
