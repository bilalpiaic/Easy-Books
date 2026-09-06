"""Declared hot-path indexes for journal / invoice list queries."""
from models import (
    BillLine,
    Invoice,
    InvoiceLine,
    JournalEntry,
    PaymentAllocation,
    Transaction,
)


def _index_map(model) -> dict[str, list[str]]:
    return {ix.name: [c.name for c in ix.columns] for ix in model.__table__.indexes}


def test_transaction_tenant_date_index():
    cols = _index_map(Transaction)["ix_transaction_tenant_date"]
    assert cols == ["tenant_id", "date"]


def test_journal_entry_fk_indexes():
    names = _index_map(JournalEntry)
    assert "transaction_id" in names["ix_journalentry_transaction_id"]
    assert "account_id" in names["ix_journalentry_account_id"]


def test_invoice_tenant_issue_date_index():
    cols = _index_map(Invoice)["ix_invoice_tenant_issue_date"]
    assert cols == ["tenant_id", "issue_date"]


def test_line_and_allocation_fk_indexes():
    assert "invoice_id" in _index_map(InvoiceLine)["ix_invoiceline_invoice_id"]
    assert "bill_id" in _index_map(BillLine)["ix_billline_bill_id"]
    alloc = _index_map(PaymentAllocation)
    assert "invoice_id" in alloc["ix_paymentallocation_invoice_id"]
    assert "bill_id" in alloc["ix_paymentallocation_bill_id"]
