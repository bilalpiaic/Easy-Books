"""Payment FX fields + invoice/bill carrying_rate (#215, #216)

Revision ID: 0042_payment_fx
Revises: 0041_wave_bcd
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0042_payment_fx"
down_revision: Union[str, Sequence[str], None] = "0041_wave_bcd"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    for table in ("invoice", "bill"):
        cols = {c["name"] for c in insp.get_columns(table)}
        if "carrying_rate" not in cols:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("carrying_rate", sa.Numeric(18, 4), nullable=True))

    for table in ("paymentreceived", "billpayment"):
        cols = {c["name"] for c in insp.get_columns(table)}
        with op.batch_alter_table(table) as batch:
            if "currency" not in cols:
                batch.add_column(sa.Column("currency", sa.String(), nullable=True))
            if "exchange_rate" not in cols:
                batch.add_column(sa.Column("exchange_rate", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    for table in ("paymentreceived", "billpayment"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("exchange_rate")
            batch.drop_column("currency")
    for table in ("invoice", "bill"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("carrying_rate")
