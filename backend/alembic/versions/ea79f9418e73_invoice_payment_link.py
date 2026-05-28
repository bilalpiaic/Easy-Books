"""invoice_payment_link

Revision ID: ea79f9418e73
Revises: 5df34b7550dd
Create Date: 2026-05-28 22:26:01.989118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ea79f9418e73'
down_revision: Union[str, Sequence[str], None] = '5df34b7550dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c['name'] for c in sa.inspect(bind).get_columns('invoice')}
    if 'payment_link_url' not in cols:
        op.add_column('invoice', sa.Column('payment_link_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    if 'payment_link_status' not in cols:
        op.add_column('invoice', sa.Column('payment_link_status', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    # FK on journalentry omitted: SQLite does not support ADD CONSTRAINT via ALTER TABLE.


def downgrade() -> None:
    op.drop_column('invoice', 'payment_link_status')
    op.drop_column('invoice', 'payment_link_url')
