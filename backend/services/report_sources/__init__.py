"""Declarative report data-source registry — the security boundary.

User report configs reference only the string `key`s defined here; the engine
resolves them to real SQLModel columns. An unknown key is a 400, never a query.
`tenant_id` is intentionally NOT a field on any source — the engine injects it.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from sqlalchemy.orm.attributes import InstrumentedAttribute

from models import (Account, Bill, BillPayment, Customer, Invoice, JournalEntry,
                    PaymentReceived, Product, StockMovement, Transaction, Vendor)


class FieldType(str, Enum):
    TEXT = "text"
    NUMBER = "number"
    MONEY = "money"
    DATE = "date"
    ENUM = "enum"
    BOOL = "bool"


# Operators allowed per field type (also enforced server-side in the engine).
OPS_BY_TYPE: dict[FieldType, list[str]] = {
    FieldType.TEXT:   ["equals", "contains", "starts_with", "in"],
    FieldType.NUMBER: ["equals", "gt", "gte", "lt", "lte", "between"],
    FieldType.MONEY:  ["equals", "gt", "gte", "lt", "lte", "between"],
    FieldType.DATE:   ["equals", "before", "after", "between"],
    FieldType.ENUM:   ["equals", "in"],
    FieldType.BOOL:   ["equals"],
}


@dataclass(frozen=True)
class JoinPath:
    local: InstrumentedAttribute   # e.g. Invoice.customer_id
    target: type                   # e.g. Customer (SQLModel table)
    target_key: InstrumentedAttribute  # e.g. Customer.id


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str
    type: FieldType
    column: InstrumentedAttribute
    join: Optional[JoinPath] = None
    enum_values: Optional[list[str]] = None
    aggregatable: bool = False
    groupable: bool = True


@dataclass(frozen=True)
class ReportSource:
    key: str
    label: str
    model: type
    fields: dict[str, FieldDef]
    default_columns: list[str]
    date_field: Optional[str] = None

    def field(self, key: str) -> FieldDef:
        return self.fields[key]  # KeyError on miss; router converts to HTTP 400


def _f(key, label, type_, column, **kw) -> FieldDef:
    return FieldDef(key=key, label=label, type=type_, column=column, **kw)


# NOTE: Customer.region does not exist in the current model, so customer_region
# is intentionally omitted. INVOICES therefore has 9 fields.
INVOICES = ReportSource(
    key="invoices", label="Invoices", model=Invoice, date_field="issue_date",
    default_columns=["number", "customer_name", "issue_date", "status", "total"],
    fields={
        "number":        _f("number", "Invoice #", FieldType.TEXT, Invoice.number),
        "customer_name": _f("customer_name", "Customer", FieldType.TEXT, Invoice.customer_name),
        "issue_date":    _f("issue_date", "Issue Date", FieldType.DATE, Invoice.issue_date),
        "due_date":      _f("due_date", "Due Date", FieldType.DATE, Invoice.due_date),
        "status":        _f("status", "Status", FieldType.ENUM, Invoice.status,
                            enum_values=["draft", "sent", "posted", "partial", "paid", "overdue", "void"]),
        "currency":      _f("currency", "Currency", FieldType.TEXT, Invoice.currency),
        "subtotal":      _f("subtotal", "Subtotal", FieldType.MONEY, Invoice.subtotal, aggregatable=True),
        "gst_amount":    _f("gst_amount", "Tax", FieldType.MONEY, Invoice.gst_amount, aggregatable=True),
        "total":         _f("total", "Total", FieldType.MONEY, Invoice.total, aggregatable=True),
    },
)

BILLS = ReportSource(
    key="bills", label="Bills", model=Bill, date_field="bill_date",
    default_columns=["number", "vendor_name", "bill_date", "status", "total"],
    fields={
        "number":      _f("number", "Bill #", FieldType.TEXT, Bill.number),
        "vendor_name": _f("vendor_name", "Vendor", FieldType.TEXT, Bill.vendor_name),
        "bill_date":   _f("bill_date", "Bill Date", FieldType.DATE, Bill.bill_date),
        "due_date":    _f("due_date", "Due Date", FieldType.DATE, Bill.due_date),
        "status":      _f("status", "Status", FieldType.ENUM, Bill.status,
                          enum_values=["draft", "posted", "partial", "paid", "overdue", "void"]),
        "currency":    _f("currency", "Currency", FieldType.TEXT, Bill.currency),
        "subtotal":    _f("subtotal", "Subtotal", FieldType.MONEY, Bill.subtotal, aggregatable=True),
        "gst_amount":  _f("gst_amount", "Tax", FieldType.MONEY, Bill.gst_amount, aggregatable=True),
        "total":       _f("total", "Total", FieldType.MONEY, Bill.total, aggregatable=True),
    },
)

JOURNAL_LINES = ReportSource(
    key="journal_lines", label="Journal Entry Lines", model=JournalEntry, date_field="date",
    default_columns=["date", "account_code", "account_name", "debit", "credit"],
    fields={
        "date":         _f("date", "Date", FieldType.DATE, Transaction.date,
                           join=JoinPath(JournalEntry.transaction_id, Transaction, Transaction.id)),
        "jv_number":    _f("jv_number", "JV #", FieldType.TEXT, Transaction.jv_number,
                           join=JoinPath(JournalEntry.transaction_id, Transaction, Transaction.id)),
        "account_code": _f("account_code", "Account Code", FieldType.TEXT, Account.code,
                           join=JoinPath(JournalEntry.account_id, Account, Account.id)),
        "account_name": _f("account_name", "Account", FieldType.TEXT, Account.name,
                           join=JoinPath(JournalEntry.account_id, Account, Account.id)),
        "account_type": _f("account_type", "Type", FieldType.ENUM, Account.type,
                           enum_values=["Asset", "Liability", "Equity", "Revenue", "Expense"],
                           join=JoinPath(JournalEntry.account_id, Account, Account.id)),
        "debit":        _f("debit", "Debit", FieldType.MONEY, JournalEntry.debit, aggregatable=True),
        "credit":       _f("credit", "Credit", FieldType.MONEY, JournalEntry.credit, aggregatable=True),
    },
)

PAYMENTS_RECEIVED = ReportSource(
    key="payments_received", label="Payments Received", model=PaymentReceived, date_field="payment_date",
    default_columns=["payment_date", "customer_name", "method", "amount"],
    fields={
        "payment_date":  _f("payment_date", "Date", FieldType.DATE, PaymentReceived.payment_date),
        "customer_name": _f("customer_name", "Customer", FieldType.TEXT, PaymentReceived.customer_name),
        "method":        _f("method", "Method", FieldType.ENUM, PaymentReceived.method,
                            enum_values=["cash", "bank", "card", "cheque"]),
        "reference":     _f("reference", "Reference", FieldType.TEXT, PaymentReceived.reference),
        "amount":        _f("amount", "Amount", FieldType.MONEY, PaymentReceived.amount, aggregatable=True),
    },
)

PAYMENTS_MADE = ReportSource(
    key="payments_made", label="Payments Made", model=BillPayment, date_field="payment_date",
    default_columns=["payment_date", "vendor_name", "method", "amount"],
    fields={
        "payment_date": _f("payment_date", "Date", FieldType.DATE, BillPayment.payment_date),
        "vendor_name":  _f("vendor_name", "Vendor", FieldType.TEXT, BillPayment.vendor_name),
        "method":       _f("method", "Method", FieldType.ENUM, BillPayment.method,
                           enum_values=["cash", "bank", "card", "cheque"]),
        "reference":    _f("reference", "Reference", FieldType.TEXT, BillPayment.reference),
        "amount":       _f("amount", "Amount", FieldType.MONEY, BillPayment.amount, aggregatable=True),
    },
)

# NOTE: Product has no 'sku' or 'sale_price'/'cost_price' columns.
# Real attributes: code (str), default_rate (sale price), avg_cost (cost).
# 'sku' → dropped (no equivalent); 'sale_price' → default_rate; 'cost_price' → avg_cost.
PRODUCTS = ReportSource(
    key="products", label="Products", model=Product, date_field=None,
    default_columns=["code", "name", "stock_qty", "default_rate"],
    fields={
        "code":         _f("code", "Code", FieldType.TEXT, Product.code),
        "name":         _f("name", "Name", FieldType.TEXT, Product.name),
        "stock_qty":    _f("stock_qty", "On Hand", FieldType.NUMBER, Product.stock_qty, aggregatable=True),
        "default_rate": _f("default_rate", "Sale Price", FieldType.MONEY, Product.default_rate, aggregatable=True),
        "avg_cost":     _f("avg_cost", "Avg Cost", FieldType.MONEY, Product.avg_cost, aggregatable=True),
    },
)

# NOTE: StockMovement has no 'date' or 'kind' columns.
# Real attributes: occurred_at (datetime), direction (str).
# 'date' → occurred_at; 'kind' → direction.
STOCK_MOVEMENTS = ReportSource(
    key="stock_movements", label="Stock Movements", model=StockMovement, date_field="occurred_at",
    default_columns=["occurred_at", "product_id", "direction", "qty", "unit_cost"],
    fields={
        "occurred_at": _f("occurred_at", "Date/Time", FieldType.DATE, StockMovement.occurred_at),
        "product_id":  _f("product_id", "Product ID", FieldType.NUMBER, StockMovement.product_id),
        "direction":   _f("direction", "Direction", FieldType.ENUM, StockMovement.direction,
                          enum_values=["RECEIPT", "CUSTODIAL_RECEIPT", "ISSUE", "CUSTODIAL_ISSUE",
                                       "COMPLETION", "CUSTODIAL_COMPLETION", "DELIVERY", "SHIPMENT",
                                       "ADJUSTMENT"]),
        "qty":         _f("qty", "Qty", FieldType.NUMBER, StockMovement.qty, aggregatable=True),
        "unit_cost":   _f("unit_cost", "Unit Cost", FieldType.MONEY, StockMovement.unit_cost, aggregatable=True),
    },
)

CUSTOMERS = ReportSource(
    key="customers", label="Customers", model=Customer, date_field=None,
    default_columns=["name", "email", "phone"],
    fields={
        "name":  _f("name", "Name", FieldType.TEXT, Customer.name),
        "email": _f("email", "Email", FieldType.TEXT, Customer.email),
        "phone": _f("phone", "Phone", FieldType.TEXT, Customer.phone),
    },
)

VENDORS = ReportSource(
    key="vendors", label="Vendors", model=Vendor, date_field=None,
    default_columns=["name", "email", "phone"],
    fields={
        "name":  _f("name", "Name", FieldType.TEXT, Vendor.name),
        "email": _f("email", "Email", FieldType.TEXT, Vendor.email),
        "phone": _f("phone", "Phone", FieldType.TEXT, Vendor.phone),
    },
)

REGISTRY: dict[str, ReportSource] = {s.key: s for s in (
    INVOICES, BILLS, JOURNAL_LINES, PAYMENTS_RECEIVED, PAYMENTS_MADE,
    PRODUCTS, STOCK_MOVEMENTS, CUSTOMERS, VENDORS,
)}
