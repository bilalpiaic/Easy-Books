"""add hs_code to product and explode_on_invoice to bomheader

Revision ID: 1af1ee747edb
Revises: dashlayout01
Create Date: 2026-06-14 13:47:21.991499

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '1af1ee747edb'
down_revision: Union[str, Sequence[str], None] = 'dashlayout01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    cols = {c['name'] for c in insp.get_columns('product')}
    if 'hs_code' not in cols:
        op.add_column('product', sa.Column('hs_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True))

    cols = {c['name'] for c in insp.get_columns('bomheader')}
    if 'explode_on_invoice' not in cols:
        op.add_column('bomheader', sa.Column('explode_on_invoice', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    pass  # SQLite cannot drop columns; no-op
