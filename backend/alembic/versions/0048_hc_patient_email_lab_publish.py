"""Patient email + lab publish helpers migration

Revision ID: 0048_hc_patient_email_lab_publish
Revises: 0047_po_scrap_reasons
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0048_hc_patient_email_lab_publish"
down_revision: Union[str, Sequence[str], None] = "0047_po_scrap_reasons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "hc_patient"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("hc_patient")}
        if "email" not in cols:
            op.add_column("hc_patient", sa.Column("email", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.has_table(bind, "hc_patient"):
        cols = {c["name"] for c in sa.inspect(bind).get_columns("hc_patient")}
        if "email" in cols:
            op.drop_column("hc_patient", "email")
