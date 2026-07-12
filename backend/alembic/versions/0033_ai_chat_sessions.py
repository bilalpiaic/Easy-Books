"""ai chat sessions (#117 completion)

Revision ID: 0033_ai_chat_sessions
Revises: 0032_store_issue
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0033_ai_chat_sessions'
down_revision: Union[str, Sequence[str], None] = '0032_store_issue'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'aichatsession'):
        op.create_table('aichatsession',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_aichatsession_tenant_id'), 'aichatsession', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_aichatsession_user_id'), 'aichatsession', ['user_id'], unique=False)

    if not bind.dialect.has_table(bind, 'aichatmessage'):
        op.create_table('aichatmessage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('user','assistant')", name='ck_ai_msg_role'),
        sa.ForeignKeyConstraint(['session_id'], ['aichatsession.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_aichatmessage_session_id'), 'aichatmessage', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_table('aichatmessage')
    op.drop_table('aichatsession')
