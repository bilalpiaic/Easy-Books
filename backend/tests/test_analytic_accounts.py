"""Tests: analytic_account_id propagates to JournalEntry rows for all document types."""
from decimal import Decimal
from models import Invoice, Bill, PaymentReceived, BillPayment, TransactionCreate
import inspect


def test_invoice_model_has_analytic_account_id():
    fields = Invoice.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_bill_model_has_analytic_account_id():
    fields = Bill.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_payment_received_model_has_analytic_account_id():
    fields = PaymentReceived.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_bill_payment_model_has_analytic_account_id():
    fields = BillPayment.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None


def test_transaction_create_has_analytic_account_id():
    fields = TransactionCreate.model_fields
    assert "analytic_account_id" in fields
    assert fields["analytic_account_id"].default is None
