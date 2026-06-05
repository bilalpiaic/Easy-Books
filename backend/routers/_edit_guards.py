"""Shared eligibility checks for editing posted invoices/bills."""
from fastapi import HTTPException
from sqlmodel import Session, select

from models import PaymentAllocation, Transaction
from services.posting import PostingError, _check_period_locked


def assert_doc_editable(session: Session, *, tenant_id: int, doc, kind: str) -> None:
    """Raise HTTPException if a posted invoice/bill may not be edited.

    kind: 'invoice' or 'bill'. Drafts are always editable (caller short-circuits).
    Rules: block if any payment allocated; block if date in a locked period;
    block if the GL txn is already reversed.
    """
    if doc.status == "draft":
        return

    alloc_filter = (
        PaymentAllocation.invoice_id == doc.id if kind == "invoice"
        else PaymentAllocation.bill_id == doc.id
    )
    allocated = session.exec(
        select(PaymentAllocation).where(
            PaymentAllocation.tenant_id == tenant_id, alloc_filter
        )
    ).first()
    if allocated:
        raise HTTPException(400, "Unallocate payments before editing this document.")

    # Locked period — PostingError IS an HTTPException (status 400), so it bubbles up.
    doc_date = getattr(doc, "issue_date", None) or getattr(doc, "bill_date", None)
    if doc_date:
        try:
            _check_period_locked(session, tenant_id, doc_date)
        except PostingError:
            raise

    if doc.transaction_id:
        txn = session.get(Transaction, doc.transaction_id)
        if txn and txn.is_reversed:
            raise HTTPException(400, "This document was already reversed and cannot be edited.")
