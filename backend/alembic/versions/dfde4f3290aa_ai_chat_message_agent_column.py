"""ai chat message agent column

Revision ID: dfde4f3290aa
Revises: 0033_ai_chat_sessions
Create Date: 2026-07-17 20:50:42.543330

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'dfde4f3290aa'
down_revision: Union[str, Sequence[str], None] = '0033_ai_chat_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("aichatmessage")}
    if "agent" not in cols:
        op.add_column('aichatmessage', sa.Column('agent', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    op.drop_column('aichatmessage', 'agent')
