"""UK MTD VAT + Malaysia MyInvois invoice fields + submission logs (#306).

Revision ID: 0087_uk_mtd_my_invois
Revises: 0086_weighbridge
Create Date: 2026-09-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0087_uk_mtd_my_invois"
down_revision: Union[str, Sequence[str], None] = "0086_weighbridge"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        if "uk_mtd_status" not in inv_cols:
            batch.add_column(sa.Column("uk_mtd_status", sa.String(), nullable=True))
        if "uk_mtd_period" not in inv_cols:
            batch.add_column(sa.Column("uk_mtd_period", sa.String(), nullable=True))
        if "uk_mtd_correlation_id" not in inv_cols:
            batch.add_column(sa.Column("uk_mtd_correlation_id", sa.String(), nullable=True))
        if "uk_mtd_submitted_at" not in inv_cols:
            batch.add_column(sa.Column("uk_mtd_submitted_at", sa.DateTime(), nullable=True))
        if "my_invois_status" not in inv_cols:
            batch.add_column(sa.Column("my_invois_status", sa.String(), nullable=True))
        if "my_invois_uuid" not in inv_cols:
            batch.add_column(sa.Column("my_invois_uuid", sa.String(), nullable=True))
        if "my_invois_submitted_at" not in inv_cols:
            batch.add_column(sa.Column("my_invois_submitted_at", sa.DateTime(), nullable=True))

    if not bind.dialect.has_table(bind, "ukmtdsubmissionlog"):
        op.create_table(
            "ukmtdsubmissionlog",
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
            sa.Column("period_key", sa.String(), nullable=True),
        )

    if not bind.dialect.has_table(bind, "myinvoissubmissionlog"):
        op.create_table(
            "myinvoissubmissionlog",
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
            sa.Column("uuid", sa.String(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "myinvoissubmissionlog"):
        op.drop_table("myinvoissubmissionlog")
    if bind.dialect.has_table(bind, "ukmtdsubmissionlog"):
        op.drop_table("ukmtdsubmissionlog")

    inv_cols = {c["name"] for c in sa.inspect(bind).get_columns("invoice")}
    with op.batch_alter_table("invoice") as batch:
        for col in (
            "my_invois_submitted_at", "my_invois_uuid", "my_invois_status",
            "uk_mtd_submitted_at", "uk_mtd_correlation_id", "uk_mtd_period", "uk_mtd_status",
        ):
            if col in inv_cols:
                batch.drop_column(col)
