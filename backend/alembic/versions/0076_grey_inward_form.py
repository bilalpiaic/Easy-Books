"""GREY IN form fields on grey lot / than (# textile processing UX)

Revision ID: 0076_grey_inward_form
Revises: 0075_leave_module
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0076_grey_inward_form"
down_revision: Union[str, Sequence[str], None] = "0075_leave_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tp_grey_lot") as batch:
        batch.add_column(sa.Column("mending_date", sa.String(), nullable=True))
        batch.add_column(sa.Column("contractor_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("category", sa.String(), nullable=True))
        batch.add_column(sa.Column("process_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("lot_no", sa.String(), nullable=True))
        batch.add_column(sa.Column("lot_remarks", sa.String(), nullable=True))
        batch.add_column(sa.Column("l_kami_mtr", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("manual_rejection_mtr", sa.Numeric(18, 4), nullable=True))
        batch.add_column(sa.Column("rej_driver_name", sa.String(), nullable=True))
        batch.add_column(sa.Column("rej_mobile", sa.String(), nullable=True))
        batch.add_column(sa.Column("rej_vehicle", sa.String(), nullable=True))

    with op.batch_alter_table("tp_grey_than") as batch:
        batch.add_column(sa.Column("g_kami_mtr", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("cp_mtr", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("des_date", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tp_grey_than") as batch:
        batch.drop_column("des_date")
        batch.drop_column("cp_mtr")
        batch.drop_column("g_kami_mtr")
    with op.batch_alter_table("tp_grey_lot") as batch:
        for col in (
            "rej_vehicle", "rej_mobile", "rej_driver_name", "manual_rejection_mtr",
            "l_kami_mtr", "lot_remarks", "lot_no", "rate", "process_name",
            "category", "contractor_id", "mending_date",
        ):
            batch.drop_column(col)
