"""FBR Digital Invoicing (PRAL DI API v1.12) fields.

Revision ID: 0089_pra_di_v112
Revises: 0088_device_tokens
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0089_pra_di_v112"
down_revision: Union[str, Sequence[str], None] = "0088_device_tokens"
branch_labels = None
depends_on = None


def _add(table: str, name: str, col: sa.Column) -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    _add("customer", "registration_type", sa.Column("registration_type", sa.String(), nullable=True))
    _add("customer", "province", sa.Column("province", sa.String(), nullable=True))

    _add("invoice", "buyer_registration_type", sa.Column("buyer_registration_type", sa.String(), nullable=True))
    _add("invoice", "buyer_province", sa.Column("buyer_province", sa.String(), nullable=True))
    _add("invoice", "di_invoice_type", sa.Column("di_invoice_type", sa.String(), nullable=True))
    _add("invoice", "di_invoice_ref_no", sa.Column("di_invoice_ref_no", sa.String(), nullable=True))
    _add("invoice", "di_scenario_id", sa.Column("di_scenario_id", sa.String(), nullable=True))

    _add("product", "sale_type", sa.Column("sale_type", sa.String(), nullable=True))
    _add("product", "di_uom", sa.Column("di_uom", sa.String(), nullable=True))
    _add("product", "sro_schedule_no", sa.Column("sro_schedule_no", sa.String(), nullable=True))
    _add("product", "sro_item_serial", sa.Column("sro_item_serial", sa.String(), nullable=True))
    _add("product", "fixed_notified_value", sa.Column("fixed_notified_value", sa.Numeric(18, 4), nullable=True))

    _add("invoiceline", "sale_type", sa.Column("sale_type", sa.String(), nullable=True))
    _add("invoiceline", "hs_code", sa.Column("hs_code", sa.String(), nullable=True))
    _add("invoiceline", "di_uom", sa.Column("di_uom", sa.String(), nullable=True))
    _add("invoiceline", "di_rate", sa.Column("di_rate", sa.String(), nullable=True))
    _add("invoiceline", "further_tax", sa.Column("further_tax", sa.Numeric(18, 4), nullable=True, server_default="0"))
    _add("invoiceline", "extra_tax", sa.Column("extra_tax", sa.Numeric(18, 4), nullable=True, server_default="0"))
    _add("invoiceline", "fed_payable", sa.Column("fed_payable", sa.Numeric(18, 4), nullable=True, server_default="0"))
    _add("invoiceline", "st_withheld", sa.Column("st_withheld", sa.Numeric(18, 4), nullable=True, server_default="0"))
    _add("invoiceline", "fixed_notified_value", sa.Column("fixed_notified_value", sa.Numeric(18, 4), nullable=True, server_default="0"))
    _add("invoiceline", "sro_schedule_no", sa.Column("sro_schedule_no", sa.String(), nullable=True))
    _add("invoiceline", "sro_item_serial", sa.Column("sro_item_serial", sa.String(), nullable=True))


def downgrade() -> None:
    for col in (
        "sro_item_serial", "sro_schedule_no", "fixed_notified_value", "st_withheld",
        "fed_payable", "extra_tax", "further_tax", "di_rate", "di_uom", "hs_code", "sale_type",
    ):
        op.drop_column("invoiceline", col)
    for col in ("fixed_notified_value", "sro_item_serial", "sro_schedule_no", "di_uom", "sale_type"):
        op.drop_column("product", col)
    for col in ("di_scenario_id", "di_invoice_ref_no", "di_invoice_type", "buyer_province", "buyer_registration_type"):
        op.drop_column("invoice", col)
    op.drop_column("customer", "province")
    op.drop_column("customer", "registration_type")
