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


def _add_missing(table: str, columns: list[tuple[str, sa.Column]]) -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, table):
        return
    existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    missing = [col for name, col in columns if name not in existing]
    if not missing:
        return
    with op.batch_alter_table(table) as batch:
        for col in missing:
            batch.add_column(col)


def upgrade() -> None:
    _add_missing("tp_grey_lot", [
        ("mending_date", sa.Column("mending_date", sa.String(), nullable=True)),
        ("contractor_id", sa.Column("contractor_id", sa.Integer(), nullable=True)),
        ("category", sa.Column("category", sa.String(), nullable=True)),
        ("process_name", sa.Column("process_name", sa.String(), nullable=True)),
        ("rate", sa.Column("rate", sa.Numeric(18, 4), nullable=False, server_default="0")),
        ("lot_no", sa.Column("lot_no", sa.String(), nullable=True)),
        ("lot_remarks", sa.Column("lot_remarks", sa.String(), nullable=True)),
        ("l_kami_mtr", sa.Column("l_kami_mtr", sa.Numeric(18, 4), nullable=False, server_default="0")),
        ("manual_rejection_mtr", sa.Column("manual_rejection_mtr", sa.Numeric(18, 4), nullable=True)),
        ("rej_driver_name", sa.Column("rej_driver_name", sa.String(), nullable=True)),
        ("rej_mobile", sa.Column("rej_mobile", sa.String(), nullable=True)),
        ("rej_vehicle", sa.Column("rej_vehicle", sa.String(), nullable=True)),
    ])
    _add_missing("tp_grey_than", [
        ("g_kami_mtr", sa.Column("g_kami_mtr", sa.Numeric(18, 4), nullable=False, server_default="0")),
        ("cp_mtr", sa.Column("cp_mtr", sa.Numeric(18, 4), nullable=False, server_default="0")),
        ("des_date", sa.Column("des_date", sa.String(), nullable=True)),
    ])


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
