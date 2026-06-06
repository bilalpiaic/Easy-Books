"""voucher_backfill

One-time backfill that infers each existing transaction's voucher type from
its source document (Invoice, Bill, PaymentReceived, BillPayment, CreditNote,
DebitNote) and renumbers per type in chronological (date, id) order, preserving
the original number in ``legacy_jv_number``.

Idempotency is guaranteed by the ``legacy_jv_number IS NULL`` guard inside
``backfill_vouchers`` — rows already processed are skipped on re-run.

Revision ID: a1b2c3d4e5f6
Revises: 9ea44fbcd894
Create Date: 2026-06-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9ea44fbcd894"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Iterate all tenants and backfill their voucher types / numbers."""
    import sys
    import os

    # Make sure the backend package is importable from within the Alembic context.
    _here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _here not in sys.path:
        sys.path.insert(0, _here)

    from sqlmodel import Session, select
    from models import Tenant
    from services.voucher_backfill import backfill_vouchers

    bind = op.get_bind()

    # Alembic passes a Connection; wrap it in a Session for the service layer.
    with Session(bind=bind) as session:
        tenants = session.exec(select(Tenant)).all()
        for tenant in tenants:
            backfill_vouchers(session, tenant.id)
            session.flush()
        session.commit()


def downgrade() -> None:
    """Downgrade is intentionally a no-op.

    The legacy_jv_number column (added in the previous migration) still holds
    the original numbers; restoring them would require reversing the renumber.
    Since this is a data migration on historical data that callers should not
    rely on, we do not attempt a rollback.  To fully undo: restore from backup.
    """
    pass
