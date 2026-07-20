"""Declarative registry of the AI chat's read-only tools.

Mirrors services/report_sources's pattern: a frozen, key-based registry that
is the single source of truth for every tool the AI assistant can call.
`routers/ai_chat.py` derives its provider-facing tool schemas
(anthropic_tools / openai_tools), progress labels (tool_labels), and dispatch
(execute_tool) from here — adding a tool is one TOOL_REGISTRY entry, not a
4-place hand-edit across ai_chat.py.

Each executor wraps an existing report function directly (no HTTP
re-request) so business rules, tenant filters, and calculations are reused,
never re-implemented. `required_module` gates module-specific tools the same
way AgentDef.required_module gates agents (None = base, always available).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Iterable

from sqlmodel import Session, select

from models import (
    Account, AnalyticAccount, Customer, Employee, Invoice, Product, Tenant, User, Vendor,
)
from models_healthcare import HcPatient
from models_telecom import RsoAgent
from models_weaving import WvContract
from routers.aging import invoice_aging, bill_aging
from routers.assets import list_assets
from routers.attendance import get_summary as attendance_summary
from routers.bank_accounts import list_bank_accounts
from routers.commissions import list_ledger as commission_list_ledger, list_plans as commission_list_plans
from routers.deferred_revenue import list_schedules as deferred_list_schedules
from routers.healthcare_reports import (
    dashboard as hc_dashboard,
    doctor_collections,
    ipd_census,
    lab_summary,
    opd_summary,
    patient_statement,
    revenue_by_type as hc_revenue_by_type,
)
from routers.manufacturing_reports import (
    customer_custody,
    dashboard as mfg_dashboard,
    production_summary,
    wip_aging,
)
from routers.payroll import hrm_summary
from routers.pra import get_invoice_pra_status, list_pra_logs
from routers.purchase_reports import (
    gate_register,
    three_way_match,
    vendor_performance as purchase_vendor_performance,
)
from routers.reports import (
    get_dashboard_data,
    get_dashboard_charts,
    get_day_book,
    get_income_statement,
    get_journal_report,
    get_ledger,
    get_trial_balance,
    cash_flow_statement,
    customer_performance,
    get_analytic_pl,
    get_balance_sheet,
    get_budget_vs_actual,
    get_net_worth_trend,
    inventory_performance,
    ledger_subledger,
    product_coa,
    product_ledger,
    product_performance,
    tax_summary,
)
from routers.store_reports import (
    dispatch_reconciliation,
    gate_outward_register,
    issue_register,
    stock_tie_out,
)
from routers.subledger import (
    customer_ledger,
    customer_statement,
    vendor_ledger,
    vendor_statement,
)
from services.report_engine import DateRange, ReportConfig, run_report
from services.report_sources import REGISTRY as REPORT_SOURCE_REGISTRY
from routers.telecom_reports import (
    commission_aging,
    dashboard as tc_dashboard,
    fca_target_progress,
    float_statement,
    postpaid_book,
    revenue_by_stream,
    rso_ledger,
    sim_utilisation,
    stock_issuance,
    tracker_statement,
)
from routers.weaving_reports import (
    contract_control,
    customer_contract_kpi,
    daily_operations,
    weaving_dashboard,
)

# Oversized tool results are truncated before they re-enter the LLM loop —
# unpaginated reports (per-product/per-customer lists) can otherwise blow the
# reviewer/drafting stages' input budget. This constant is the tuning knob.
MAX_TOOL_RESULT_CHARS = 15_000

_DATE_RANGE_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
        "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
    },
    "required": [],
}

_EMPTY_SCHEMA = {"type": "object", "properties": {}, "required": []}

_HC_PERIOD_SCHEMA = {
    "type": "object",
    "properties": {
        "from_date": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
        "to_date":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
    },
    "required": [],
}

_REGISTER_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
        "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
        "q":     {"type": "string", "description": "Search text (optional)"},
    },
    "required": [],
}


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: dict               # JSON Schema (Anthropic tool shape)
    label: str                       # user-facing progress label ("Checking your P&L…")
    executor: Callable[[Session, User, dict], Any]
    required_module: str | None = None  # None = base, always available


def _json_safe(obj):
    """Recursively convert Decimal → float and date/datetime → ISO string for
    JSON serialization (module report functions return both)."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(i) for i in obj]
    return obj


# ── Executors ─────────────────────────────────────────────────────────────────

def _exec_dashboard_summary(session, user, tool_input):
    return get_dashboard_data(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_income_statement(session, user, tool_input):
    return get_income_statement(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_ar_aging(session, user, tool_input):
    return invoice_aging(session, user)


def _exec_ap_aging(session, user, tool_input):
    return bill_aging(session, user)


def _exec_trial_balance(session, user, tool_input):
    return get_trial_balance(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_cash_flow(session, user, tool_input):
    return cash_flow_statement(
        session, user,
        start=tool_input.get("start", ""),
        end=tool_input.get("end", ""),
    )


def _exec_top_customers(session, user, tool_input):
    return get_dashboard_charts(session, user, months=12)


def _require_id(tool_input: dict, key: str, lookup_tool: str) -> int:
    value = tool_input.get(key)
    if not value:
        raise ValueError(f"{key} is required — use {lookup_tool} first to resolve the name to an id.")
    return int(value)


def _exec_balance_sheet(session, user, tool_input):
    return get_balance_sheet(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
        date=tool_input.get("date"),
    )


def _exec_tax_summary(session, user, tool_input):
    return tax_summary(
        session, user,
        start=tool_input.get("start", ""),
        end=tool_input.get("end", ""),
    )


def _exec_budget_vs_actual(session, user, tool_input):
    year = tool_input.get("year")
    if not year:
        raise ValueError("year is required (e.g. 2026).")
    return get_budget_vs_actual(session, user, year=int(year), month=tool_input.get("month"))


def _exec_net_worth_trend(session, user, tool_input):
    months = int(tool_input.get("months") or 12)
    return get_net_worth_trend(session, user, months=max(1, min(months, 36)))


def _exec_customer_performance(session, user, tool_input):
    return customer_performance(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
        customer_id=tool_input.get("customer_id"),
    )


def _exec_customer_statement(session, user, tool_input):
    return customer_statement(
        session, user,
        customer_id=_require_id(tool_input, "customer_id", "find_customer"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
    )


def _exec_customer_ledger(session, user, tool_input):
    return customer_ledger(
        session, user,
        customer_id=_require_id(tool_input, "customer_id", "find_customer"),
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_vendor_statement(session, user, tool_input):
    return vendor_statement(
        session, user,
        vendor_id=_require_id(tool_input, "vendor_id", "find_vendor"),
        from_date=tool_input.get("from_date"),
        to_date=tool_input.get("to_date"),
    )


def _exec_vendor_ledger(session, user, tool_input):
    return vendor_ledger(
        session, user,
        vendor_id=_require_id(tool_input, "vendor_id", "find_vendor"),
        start=tool_input.get("start"),
        end=tool_input.get("end"),
    )


def _exec_find_customer(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Customer).where(
            Customer.tenant_id == user.tenant_id,
            Customer.name.ilike(f"%{q}%"),
        ).limit(10)
    ).all()
    return [{"id": c.id, "name": c.name} for c in rows]


def _exec_find_vendor(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Vendor).where(
            Vendor.tenant_id == user.tenant_id,
            Vendor.name.ilike(f"%{q}%"),
        ).limit(10)
    ).all()
    return [{"id": v.id, "name": v.name} for v in rows]


def _dates(tool_input, start_key="start", end_key="end"):
    return tool_input.get(start_key), tool_input.get(end_key)


# inventory ──────────────────────────────────────────────────────────────────

def _exec_product_ledger(session, user, tool_input):
    start, end = _dates(tool_input)
    return product_ledger(
        session, user,
        product_id=_require_id(tool_input, "product_id", "find_product"),
        start=start, end=end,
    )


def _exec_inventory_performance(session, user, tool_input):
    start, end = _dates(tool_input)
    return inventory_performance(session, user, start=start, end=end)


def _exec_product_performance(session, user, tool_input):
    start, end = _dates(tool_input)
    return product_performance(
        session, user, start=start, end=end, group_by=tool_input.get("group_by"),
    )


def _exec_product_valuation(session, user, tool_input):
    return product_coa(session, user)


def _exec_find_product(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Product).where(
            Product.tenant_id == user.tenant_id,
            (Product.name.ilike(f"%{q}%")) | (Product.code.ilike(f"%{q}%")),
        ).limit(10)
    ).all()
    return [{"id": p.id, "code": p.code, "name": p.name} for p in rows]


# hrm — note (user, session, ...) arg order on the wrapped functions ─────────

def _exec_hrm_summary(session, user, tool_input):
    return hrm_summary(user, session)


def _exec_attendance_summary(session, user, tool_input):
    year, month = tool_input.get("year"), tool_input.get("month")
    if not year or not month:
        raise ValueError("year and month are both required (e.g. year=2026, month=7).")
    return attendance_summary(user, session, year=int(year), month=int(month))


def _exec_find_employee(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Employee).where(
            Employee.tenant_id == user.tenant_id,
            (Employee.name.ilike(f"%{q}%")) | (Employee.employee_code.ilike(f"%{q}%")),
        ).limit(10)
    ).all()
    return [{"id": e.id, "code": e.employee_code, "name": e.name} for e in rows]


# healthcare — note (user, session, ...) arg order on the wrapped functions ──

def _exec_hc_dashboard(session, user, tool_input):
    return hc_dashboard(user, session, date=tool_input.get("date"))


def _hc_period(fn):
    def exec_(session, user, tool_input):
        return fn(
            user, session,
            from_date=tool_input.get("from_date", ""),
            to_date=tool_input.get("to_date", ""),
        )
    return exec_


_exec_opd_summary = _hc_period(opd_summary)
_exec_doctor_collections = _hc_period(doctor_collections)
_exec_lab_summary = _hc_period(lab_summary)
_exec_ipd_census = _hc_period(ipd_census)
_exec_hc_revenue_by_type = _hc_period(hc_revenue_by_type)


def _exec_patient_statement(session, user, tool_input):
    return patient_statement(
        user, session,
        patient_id=_require_id(tool_input, "patient_id", "find_patient"),
        from_date=tool_input.get("from_date", ""),
        to_date=tool_input.get("to_date", ""),
    )


def _exec_find_patient(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(HcPatient).where(
            HcPatient.tenant_id == user.tenant_id,
            (HcPatient.name.ilike(f"%{q}%")) | (HcPatient.mr_number.ilike(f"%{q}%")),
        ).limit(10)
    ).all()
    return [{"id": p.id, "mr_number": p.mr_number, "name": p.name} for p in rows]


# telecom ────────────────────────────────────────────────────────────────────

def _exec_tc_dashboard(session, user, tool_input):
    return tc_dashboard(session, user)


def _exec_commission_aging(session, user, tool_input):
    return commission_aging(session, user)


def _exec_float_statement(session, user, tool_input):
    return float_statement(session, user)


def _exec_sim_utilisation(session, user, tool_input):
    return sim_utilisation(session, user)


def _exec_revenue_by_stream(session, user, tool_input):
    return revenue_by_stream(session, user)


def _exec_fca_target_progress(session, user, tool_input):
    return fca_target_progress(session, user, month=tool_input.get("month"))


def _exec_stock_issuance(session, user, tool_input):
    start, end = _dates(tool_input)
    return stock_issuance(session, user, start=start, end=end)


def _exec_rso_ledger(session, user, tool_input):
    return rso_ledger(session, user, rso_id=tool_input.get("rso_id"))


def _exec_find_rso(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(RsoAgent).where(
            RsoAgent.tenant_id == user.tenant_id,
            RsoAgent.name.ilike(f"%{q}%"),
        ).limit(10)
    ).all()
    return [{"id": r.id, "name": r.name, "territory": r.territory} for r in rows]


# purchase_store — registers pin skip=0, limit=50 (one page for the model) ───

def _exec_gate_register(session, user, tool_input):
    start, end = _dates(tool_input)
    return gate_register(session, user, start=start, end=end, q=tool_input.get("q"))


def _exec_three_way_match(session, user, tool_input):
    start, end = _dates(tool_input)
    return three_way_match(session, user, start=start, end=end, q=tool_input.get("q"))


def _exec_purchase_vendor_performance(session, user, tool_input):
    start, end = _dates(tool_input)
    return purchase_vendor_performance(
        session, user, start=start, end=end, vendor_id=tool_input.get("vendor_id"),
    )


def _exec_gate_outward_register(session, user, tool_input):
    start, end = _dates(tool_input)
    return gate_outward_register(
        session, user, start=start, end=end,
        q=tool_input.get("q"), source_doc_type=tool_input.get("source_doc_type"),
    )


def _exec_dispatch_reconciliation(session, user, tool_input):
    start, end = _dates(tool_input)
    return dispatch_reconciliation(session, user, start=start, end=end, q=tool_input.get("q"))


def _exec_issue_register(session, user, tool_input):
    start, end = _dates(tool_input)
    return issue_register(
        session, user, start=start, end=end,
        analytic_account_id=tool_input.get("analytic_account_id"), q=tool_input.get("q"),
    )


def _exec_stock_tie_out(session, user, tool_input):
    start, end = _dates(tool_input)
    return stock_tie_out(session, user, start=start, end=end, product_id=tool_input.get("product_id"))


# generic report-builder engine ──────────────────────────────────────────────

# Report-builder sources gated to the module whose data they expose; None =
# base, always queryable. The report_sources registry itself is not
# module-aware, so the gate lives here in the AI tool wrapper.
_REPORT_SOURCE_MODULES: dict[str, str | None] = {
    "invoices": None, "bills": None, "invoice_lines": None, "bill_lines": None,
    "journal_lines": None, "payments_received": None, "payments_made": None,
    "customers": None, "vendors": None, "accounts": None,
    "products": "inventory", "stock_movements": "inventory",
    "employees": "hrm", "payroll_runs": "hrm", "payroll_lines": "hrm",
    "attendance": "hrm",
    "purchase_orders": "purchase_store",
}

_CUSTOM_REPORT_MAX_ROWS = 50


def _enabled_modules(session, user) -> set[str]:
    from routers.modules import _get_enabled
    tenant = session.get(Tenant, user.tenant_id)
    return _get_enabled(tenant) if tenant else {"base"}


def _allowed_source(source_key: str, enabled: set[str]) -> bool:
    mod = _REPORT_SOURCE_MODULES.get(source_key)
    return source_key in REPORT_SOURCE_REGISTRY and (mod is None or mod in enabled)


def _exec_list_report_sources(session, user, tool_input):
    enabled = _enabled_modules(session, user)
    source_key = (tool_input.get("source_key") or "").strip()
    if not source_key:
        return [
            {"key": s.key, "label": s.label}
            for s in REPORT_SOURCE_REGISTRY.values()
            if _allowed_source(s.key, enabled)
        ]
    if not _allowed_source(source_key, enabled):
        raise ValueError(
            f"unknown or unavailable source {source_key!r} — call list_report_sources "
            "with no arguments to see the valid keys."
        )
    s = REPORT_SOURCE_REGISTRY[source_key]
    return {
        "key": s.key, "label": s.label, "date_field": s.date_field,
        "default_columns": s.default_columns,
        "fields": [
            {"key": f.key, "label": f.label, "type": f.type.value,
             "enum_values": f.enum_values, "aggregatable": f.aggregatable,
             "groupable": f.groupable}
            for f in s.fields.values()
        ],
    }


def _exec_run_custom_report(session, user, tool_input):
    source_key = (tool_input.get("source_key") or "").strip()
    if not _allowed_source(source_key, _enabled_modules(session, user)):
        raise ValueError(
            f"unknown or unavailable source {source_key!r} — call list_report_sources "
            "with no arguments to see the valid keys."
        )
    date_range = None
    if tool_input.get("date_start") or tool_input.get("date_end"):
        date_range = DateRange(start=tool_input.get("date_start"), end=tool_input.get("date_end"))
    config = ReportConfig(
        columns=tool_input.get("columns") or [],
        filters=tool_input.get("filters") or [],
        sort=tool_input.get("sort") or [],
        group_by=tool_input.get("group_by") or [],
        aggregates=tool_input.get("aggregates") or [],
        date_range=date_range,
    )
    page_size = min(int(tool_input.get("page_size") or _CUSTOM_REPORT_MAX_ROWS),
                    _CUSTOM_REPORT_MAX_ROWS)
    res = run_report(
        session, tenant_id=user.tenant_id, source_key=source_key,
        config=config, page=0, page_size=page_size,
    )
    return {
        "columns": [asdict(c) for c in res.columns],
        "rows": res.rows,
        "group_by": res.group_by,
        "footers": res.footers,
        "total_count": res.total_count,
        "rows_returned": len(res.rows),
    }


# production ─────────────────────────────────────────────────────────────────

def _exec_mfg_dashboard(session, user, tool_input):
    return mfg_dashboard(session, user)


def _exec_wip_aging(session, user, tool_input):
    return wip_aging(session, user)


def _exec_production_summary(session, user, tool_input):
    start, end = _dates(tool_input)
    return production_summary(session, user, start=start, end=end)


def _exec_customer_custody(session, user, tool_input):
    return customer_custody(session, user)


# weaving — note (user, session, ...) arg order on the wrapped functions ─────

def _exec_weaving_dashboard(session, user, tool_input):
    return weaving_dashboard(user, session)


def _exec_weaving_daily(session, user, tool_input):
    start, end = _dates(tool_input)
    return daily_operations(user, session, start=start, end=end)


def _exec_contract_control(session, user, tool_input):
    return contract_control(
        user, session,
        contract_id=_require_id(tool_input, "contract_id", "find_wv_contract"),
    )


def _exec_weaving_customer_kpi(session, user, tool_input):
    return customer_contract_kpi(user, session)


def _exec_find_wv_contract(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(WvContract).where(
            WvContract.tenant_id == user.tenant_id,
            WvContract.number.ilike(f"%{q}%"),
        ).limit(10)
    ).all()
    return [
        {"id": c.id, "number": c.number, "status": c.status, "customer_id": c.customer_id}
        for c in rows
    ]


# pra ────────────────────────────────────────────────────────────────────────

def _exec_pra_logs(session, user, tool_input):
    return list_pra_logs(
        user, session,
        invoice_id=tool_input.get("invoice_id"),
        limit=min(int(tool_input.get("limit") or 50), 100),
    )


def _exec_invoice_pra_status(session, user, tool_input):
    return get_invoice_pra_status(
        _require_id(tool_input, "invoice_id", "run_custom_report (source invoices)"),
        user, session,
    )


def _exec_pra_today_summary(session, user, tool_input):
    """Group tenant invoices by pra_status for a date window (default today)."""
    start = tool_input.get("start") or date.today().isoformat()
    end = tool_input.get("end") or start
    rows = session.exec(
        select(Invoice).where(
            Invoice.tenant_id == user.tenant_id,
            Invoice.issue_date >= start,
            Invoice.issue_date <= end,
        )
    ).all()
    buckets: dict[str, int] = {}
    for inv in rows:
        status = inv.pra_status or "not_required"
        buckets[status] = buckets.get(status, 0) + 1
    return {
        "start": start,
        "end": end,
        "total_invoices": len(rows),
        "by_status": buckets,
        "submitted": buckets.get("submitted", 0),
        "pending": buckets.get("pending", 0),
        "failed": buckets.get("failed", 0),
        "not_required": buckets.get("not_required", 0),
    }


# banking / GL ───────────────────────────────────────────────────────────────

def _exec_day_book(session, user, tool_input):
    return get_day_book(session, user, date=tool_input.get("date"))


def _exec_account_ledger(session, user, tool_input):
    account_id = tool_input.get("account_id")
    account_code = tool_input.get("account_code")
    if not account_id and not account_code:
        raise ValueError(
            "account_id or account_code is required — use find_account first to resolve a name."
        )
    return get_ledger(
        session, user,
        start=tool_input.get("start"),
        end=tool_input.get("end"),
        account_id=int(account_id) if account_id else None,
        account_code=account_code,
        skip=0,
        limit=min(int(tool_input.get("limit") or 50), 100),
    )


def _exec_cash_bank_subledger(session, user, tool_input):
    start, end = _dates(tool_input)
    return ledger_subledger(session, user, control="bank", start=start, end=end)


def _exec_list_bank_accounts(session, user, tool_input):
    return list_bank_accounts(session, user)


def _exec_find_account(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(Account).where(
            Account.tenant_id == user.tenant_id,
            (Account.name.ilike(f"%{q}%")) | (Account.code.ilike(f"%{q}%")),
        ).limit(10)
    ).all()
    return [
        {"id": a.id, "code": a.code, "name": a.name, "type": a.type, "is_group": a.is_group}
        for a in rows
    ]


def _exec_analytic_pl(session, user, tool_input):
    start, end = _dates(tool_input)
    return get_analytic_pl(
        session, user,
        analytic_account_id=_require_id(tool_input, "analytic_account_id", "find_analytic_account"),
        start=start, end=end,
    )


def _exec_find_analytic_account(session, user, tool_input):
    q = (tool_input.get("query") or "").strip()
    if not q:
        raise ValueError("query is required.")
    rows = session.exec(
        select(AnalyticAccount).where(
            AnalyticAccount.tenant_id == user.tenant_id,
            (AnalyticAccount.name.ilike(f"%{q}%")) | (AnalyticAccount.code.ilike(f"%{q}%")),
        ).limit(10)
    ).all()
    return [
        {"id": a.id, "code": a.code, "name": a.name, "type": a.type}
        for a in rows
    ]


def _exec_journal_report(session, user, tool_input):
    start, end = _dates(tool_input)
    return get_journal_report(
        session, user,
        start=start, end=end,
        voucher_type=tool_input.get("voucher_type"),
        voucher_number=tool_input.get("voucher_number"),
        skip=0,
        limit=min(int(tool_input.get("limit") or 50), 100),
    )


# deferred revenue / commissions / fixed assets ──────────────────────────────

def _exec_list_deferred_schedules(session, user, tool_input):
    result = deferred_list_schedules(
        session, user,
        status=tool_input.get("status"),
        skip=0,
        limit=min(int(tool_input.get("limit") or 50), 100),
    )
    items = result.get("items") or []
    return {
        "total": result.get("total", len(items)),
        "items": [i.model_dump() if hasattr(i, "model_dump") else i for i in items],
    }


def _exec_commission_ledger(session, user, tool_input):
    return commission_list_ledger(
        user, session,
        period=tool_input.get("period"),
        user_id=tool_input.get("user_id"),
    )


def _exec_list_commission_plans(session, user, tool_input):
    return commission_list_plans(user, session)


def _exec_list_fixed_assets(session, user, tool_input):
    result = list_assets(
        session, user,
        skip=0,
        limit=min(int(tool_input.get("limit") or 50), 100),
    )
    items = result.get("items") or []
    return {
        "total": result.get("total", len(items)),
        "items": [i.model_dump() if hasattr(i, "model_dump") else i for i in items],
    }


# telecom leftovers ──────────────────────────────────────────────────────────

def _exec_postpaid_book(session, user, tool_input):
    result = postpaid_book(session, user)
    items = result.get("items") or []
    return {
        "total": result.get("total", len(items)),
        "items": [i.model_dump() if hasattr(i, "model_dump") else i for i in items],
    }


def _exec_tracker_statement(session, user, tool_input):
    result = tracker_statement(
        session, user,
        tracker_account_id=tool_input.get("tracker_account_id"),
    )
    txns = result.get("transactions") or []
    return {
        "tracker_accounts": result.get("tracker_accounts"),
        "gl_deposit_balance": result.get("gl_deposit_balance"),
        "gl_load_balance": result.get("gl_load_balance"),
        "transactions": [
            t.model_dump() if hasattr(t, "model_dump") else t for t in txns[:100]
        ],
        "transactions_returned": min(len(txns), 100),
        "transactions_total": len(txns),
    }


# ── Registry ──────────────────────────────────────────────────────────────────

_TOOLS: tuple[ToolDef, ...] = (
    ToolDef(
        name="get_dashboard_summary",
        description=(
            "Get the current financial dashboard KPIs: total revenue, total expenses, "
            "AR outstanding, AP outstanding, overdue invoices, low stock items, cash & bank balance, "
            "and AR aging buckets. Optionally filter by date range."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your dashboard…",
        executor=_exec_dashboard_summary,
    ),
    ToolDef(
        name="get_income_statement",
        description=(
            "Get the Profit & Loss / Income Statement showing revenue and expense totals "
            "and net profit for a period."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your P&L…",
        executor=_exec_income_statement,
    ),
    ToolDef(
        name="get_ar_aging",
        description=(
            "Get Accounts Receivable aging: outstanding invoice amounts grouped by age bucket "
            "(current, 1-30 days, 31-60 days, 61-90 days, 90+ days overdue), plus a list of "
            "individual outstanding invoices with customer names and amounts."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking who owes you (receivables)…",
        executor=_exec_ar_aging,
    ),
    ToolDef(
        name="get_ap_aging",
        description=(
            "Get Accounts Payable aging: outstanding bill amounts grouped by age bucket, "
            "plus individual outstanding bills with vendor names."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking what you owe (payables)…",
        executor=_exec_ap_aging,
    ),
    ToolDef(
        name="get_trial_balance",
        description=(
            "Get the Trial Balance showing debit and credit totals for all accounts. "
            "Useful for checking if books are balanced or auditing account balances."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your trial balance…",
        executor=_exec_trial_balance,
    ),
    ToolDef(
        name="get_cash_flow",
        description=(
            "Get the Cash Flow Statement showing operating, investing, and financing cash flows "
            "for a period."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your cash flow…",
        executor=_exec_cash_flow,
    ),
    ToolDef(
        name="get_top_customers",
        description=(
            "Get the top 10 customers by total invoiced amount and the monthly revenue/expense "
            "trend for the last 12 months."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking your top customers…",
        executor=_exec_top_customers,
    ),
    ToolDef(
        name="get_balance_sheet",
        description=(
            "Get the Balance Sheet: assets, liabilities, and equity account balances "
            "(with retained earnings) as of a date, or for a period."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "date":  {"type": "string", "description": "As-of date YYYY-MM-DD (optional)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": [],
        },
        label="Checking your balance sheet…",
        executor=_exec_balance_sheet,
    ),
    ToolDef(
        name="get_tax_summary",
        description=(
            "Get the tax summary: sales tax collected and purchase tax paid per tax account "
            "for a period (defaults to the current fiscal year to date)."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking your tax summary…",
        executor=_exec_tax_summary,
    ),
    ToolDef(
        name="get_budget_vs_actual",
        description=(
            "Get budget vs actual variance per account for a fiscal year, optionally "
            "narrowed to a single month."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "year":  {"type": "integer", "description": "Fiscal year, e.g. 2026"},
                "month": {"type": "integer", "description": "Month 1-12 (optional)"},
            },
            "required": ["year"],
        },
        label="Checking budget vs actual…",
        executor=_exec_budget_vs_actual,
    ),
    ToolDef(
        name="get_net_worth_trend",
        description=(
            "Get the monthly assets / liabilities / net worth trend over the last N months "
            "(default 12, max 36)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "months": {"type": "integer", "description": "How many months back (default 12, max 36)"},
            },
            "required": [],
        },
        label="Checking your net worth trend…",
        executor=_exec_net_worth_trend,
    ),
    ToolDef(
        name="get_customer_performance",
        description=(
            "Get per-customer sales performance for a period: invoiced totals, receipts, "
            "outstanding balances, and invoice counts. Optionally filter to one customer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "customer_id": {"type": "integer", "description": "Limit to one customer (optional; use find_customer to resolve a name)"},
            },
            "required": [],
        },
        label="Checking customer performance…",
        executor=_exec_customer_performance,
    ),
    ToolDef(
        name="get_customer_statement",
        description=(
            "Get a customer's account statement: opening balance, period invoices, payments "
            "received, and closing balance. Use find_customer first to resolve a customer "
            "name to its numeric id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer id (required)"},
                "from_date": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "to_date":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["customer_id"],
        },
        label="Fetching the customer statement…",
        executor=_exec_customer_statement,
    ),
    ToolDef(
        name="get_customer_ledger",
        description=(
            "Get a customer's chronological AR sub-ledger: every invoice and payment with a "
            "running balance. Use find_customer first to resolve a customer name to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer id (required)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["customer_id"],
        },
        label="Fetching the customer ledger…",
        executor=_exec_customer_ledger,
    ),
    ToolDef(
        name="get_vendor_statement",
        description=(
            "Get a vendor's account statement: opening balance, period bills, payments made, "
            "and closing balance. Use find_vendor first to resolve a vendor name to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "integer", "description": "Vendor id (required)"},
                "from_date": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "to_date":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["vendor_id"],
        },
        label="Fetching the vendor statement…",
        executor=_exec_vendor_statement,
    ),
    ToolDef(
        name="get_vendor_ledger",
        description=(
            "Get a vendor's chronological AP sub-ledger: every bill and payment with a "
            "running balance. Use find_vendor first to resolve a vendor name to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "vendor_id": {"type": "integer", "description": "Vendor id (required)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["vendor_id"],
        },
        label="Fetching the vendor ledger…",
        executor=_exec_vendor_ledger,
    ),
    ToolDef(
        name="find_customer",
        description=(
            "Search customers by (partial) name and return up to 10 matches as {id, name}. "
            "Use this first to resolve a customer name to its numeric id before calling "
            "get_customer_statement, get_customer_ledger, or get_customer_performance."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial customer name"},
            },
            "required": ["query"],
        },
        label="Looking up the customer…",
        executor=_exec_find_customer,
    ),
    ToolDef(
        name="find_vendor",
        description=(
            "Search vendors by (partial) name and return up to 10 matches as {id, name}. "
            "Use this first to resolve a vendor name to its numeric id before calling "
            "get_vendor_statement or get_vendor_ledger."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial vendor name"},
            },
            "required": ["query"],
        },
        label="Looking up the vendor…",
        executor=_exec_find_vendor,
    ),
    # ── inventory ────────────────────────────────────────────────────────────
    ToolDef(
        name="get_product_ledger",
        description=(
            "Get one product's stock movement ledger: every in/out movement with source "
            "document, location, and running quantity/value. Use find_product first to "
            "resolve a product name to its numeric id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "Product id (required)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["product_id"],
        },
        label="Fetching the product ledger…",
        executor=_exec_product_ledger,
        required_module="inventory",
    ),
    ToolDef(
        name="get_inventory_performance",
        description=(
            "Get inventory performance for a period: per-product turnover, movement totals, "
            "and on-hand value."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking inventory performance…",
        executor=_exec_inventory_performance,
        required_module="inventory",
    ),
    ToolDef(
        name="get_product_performance",
        description=(
            "Get per-product period movement: opening, purchased, sold (net), and closing "
            "quantities/values, optionally grouped by category."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "group_by": {"type": "string", "description": "Set to 'category' to group by product category (optional)"},
            },
            "required": [],
        },
        label="Checking product performance…",
        executor=_exec_product_performance,
        required_module="inventory",
    ),
    ToolDef(
        name="get_product_valuation",
        description=(
            "Get the closing-stock valuation tree: products grouped Main category → "
            "Sub-category → Item with closing quantity, average rate, and value."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking stock valuation…",
        executor=_exec_product_valuation,
        required_module="inventory",
    ),
    ToolDef(
        name="find_product",
        description=(
            "Search products by (partial) name or code and return up to 10 matches as "
            "{id, code, name}. Use this first to resolve a product to its numeric id "
            "before calling get_product_ledger."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial product name or code"},
            },
            "required": ["query"],
        },
        label="Looking up the product…",
        executor=_exec_find_product,
        required_module="inventory",
    ),
    # ── hrm ──────────────────────────────────────────────────────────────────
    ToolDef(
        name="get_hrm_summary",
        description=(
            "Get HR & payroll KPIs: active headcount, employees added this month, latest "
            "payroll run status and totals."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking HR & payroll summary…",
        executor=_exec_hrm_summary,
        required_module="hrm",
    ),
    ToolDef(
        name="get_attendance_summary",
        description=(
            "Get the monthly attendance summary: per-employee present/absent/half-day/leave "
            "counts and hours worked for a given year and month."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "year":  {"type": "integer", "description": "Year, e.g. 2026"},
                "month": {"type": "integer", "description": "Month 1-12"},
            },
            "required": ["year", "month"],
        },
        label="Checking attendance…",
        executor=_exec_attendance_summary,
        required_module="hrm",
    ),
    ToolDef(
        name="find_employee",
        description=(
            "Search employees by (partial) name or employee code and return up to 10 matches "
            "as {id, code, name}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial employee name or code"},
            },
            "required": ["query"],
        },
        label="Looking up the employee…",
        executor=_exec_find_employee,
        required_module="hrm",
    ),
    # ── healthcare ───────────────────────────────────────────────────────────
    ToolDef(
        name="get_healthcare_dashboard",
        description=(
            "Get hospital KPIs for a date (default today): OPD tokens issued, patients "
            "currently admitted, bed occupancy, and pending lab results."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD (optional, default today)"},
            },
            "required": [],
        },
        label="Checking hospital KPIs…",
        executor=_exec_hc_dashboard,
        required_module="healthcare",
    ),
    ToolDef(
        name="get_opd_summary",
        description="Get daily OPD visit counts and revenue by doctor for a period.",
        input_schema=_HC_PERIOD_SCHEMA,
        label="Checking OPD summary…",
        executor=_exec_opd_summary,
        required_module="healthcare",
    ),
    ToolDef(
        name="get_doctor_collections",
        description="Get total consultations and billed amounts per doctor for a period.",
        input_schema=_HC_PERIOD_SCHEMA,
        label="Checking doctor collections…",
        executor=_exec_doctor_collections,
        required_module="healthcare",
    ),
    ToolDef(
        name="get_lab_summary",
        description="Get lab orders grouped by status and source (OPD/IPD) for a period.",
        input_schema=_HC_PERIOD_SCHEMA,
        label="Checking lab summary…",
        executor=_exec_lab_summary,
        required_module="healthcare",
    ),
    ToolDef(
        name="get_ipd_census",
        description="Get IPD admissions and average length of stay per ward for a period.",
        input_schema=_HC_PERIOD_SCHEMA,
        label="Checking IPD census…",
        executor=_exec_ipd_census,
        required_module="healthcare",
    ),
    ToolDef(
        name="get_hc_revenue_by_type",
        description="Get hospital revenue split across OPD, Lab, Procedures, and IPD for a period.",
        input_schema=_HC_PERIOD_SCHEMA,
        label="Checking revenue by service type…",
        executor=_exec_hc_revenue_by_type,
        required_module="healthcare",
    ),
    ToolDef(
        name="get_patient_statement",
        description=(
            "Get a patient's account statement: visits, admissions, lab orders, invoices and "
            "payments. Use find_patient first to resolve a patient name or MR number to its id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "Patient id (required)"},
                "from_date": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "to_date":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["patient_id"],
        },
        label="Fetching the patient statement…",
        executor=_exec_patient_statement,
        required_module="healthcare",
    ),
    ToolDef(
        name="find_patient",
        description=(
            "Search patients by (partial) name or MR number and return up to 10 matches as "
            "{id, mr_number, name}. Use this first to resolve a patient to its numeric id "
            "before calling get_patient_statement."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial patient name or MR number"},
            },
            "required": ["query"],
        },
        label="Looking up the patient…",
        executor=_exec_find_patient,
        required_module="healthcare",
    ),
    # ── telecom ──────────────────────────────────────────────────────────────
    ToolDef(
        name="get_telecom_dashboard",
        description=(
            "Get telecom-franchise KPIs: tracker/load-float balances, SIM stock, activations, "
            "and commission position."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking franchise KPIs…",
        executor=_exec_tc_dashboard,
        required_module="telecom",
    ),
    ToolDef(
        name="get_commission_aging",
        description="Get telecom commission receivable grouped by age bucket (current → 90+ days).",
        input_schema=_EMPTY_SCHEMA,
        label="Checking commission aging…",
        executor=_exec_commission_aging,
        required_module="telecom",
    ),
    ToolDef(
        name="get_float_statement",
        description=(
            "Get the mobile-money float statement: per-account system balance vs GL balance "
            "for reconciliation."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking the float statement…",
        executor=_exec_float_statement,
        required_module="telecom",
    ),
    ToolDef(
        name="get_sim_utilisation",
        description="Get per-batch SIM utilisation: received, issued, activated, remaining.",
        input_schema=_EMPTY_SCHEMA,
        label="Checking SIM utilisation…",
        executor=_exec_sim_utilisation,
        required_module="telecom",
    ),
    ToolDef(
        name="get_revenue_by_stream",
        description=(
            "Get telecom revenue aggregated per franchise stream: airtime/recharge, SIM "
            "activation, load & recharge commissions, and other streams."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking revenue by stream…",
        executor=_exec_revenue_by_stream,
        required_module="telecom",
    ),
    ToolDef(
        name="get_fca_target_progress",
        description="Get FCA actual-vs-target progress for a month (default: current month).",
        input_schema={
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Month YYYY-MM (optional, default current)"},
            },
            "required": [],
        },
        label="Checking FCA target progress…",
        executor=_exec_fca_target_progress,
        required_module="telecom",
    ),
    ToolDef(
        name="get_stock_issuance",
        description="Get the per-RSO stock & issuance report for a period (load and SIM movement per agent).",
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking stock issuance…",
        executor=_exec_stock_issuance,
        required_module="telecom",
    ),
    ToolDef(
        name="get_rso_ledger",
        description=(
            "Get the per-RSO ledger: load issued/settled, stock issued, and cash collected. "
            "Covers all RSO agents unless rso_id narrows it to one (use find_rso to resolve "
            "an agent name)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "rso_id": {"type": "integer", "description": "Limit to one RSO agent (optional)"},
            },
            "required": [],
        },
        label="Fetching the RSO ledger…",
        executor=_exec_rso_ledger,
        required_module="telecom",
    ),
    ToolDef(
        name="find_rso",
        description=(
            "Search RSO agents by (partial) name and return up to 10 matches as "
            "{id, name, territory}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial RSO agent name"},
            },
            "required": ["query"],
        },
        label="Looking up the RSO agent…",
        executor=_exec_find_rso,
        required_module="telecom",
    ),
    # ── purchase_store ───────────────────────────────────────────────────────
    ToolDef(
        name="get_gate_register",
        description=(
            "Get the Gate Inward register: goods received at the gate against purchase "
            "orders, with vehicle/challan details (first 50 rows)."
        ),
        input_schema=_REGISTER_SCHEMA,
        label="Checking the gate register…",
        executor=_exec_gate_register,
        required_module="purchase_store",
    ),
    ToolDef(
        name="get_three_way_match",
        description=(
            "Get the 3-way match report: purchase order vs goods received (Gate Inward) vs "
            "billed quantities, with variance flags per PO line (first 50 rows)."
        ),
        input_schema=_REGISTER_SCHEMA,
        label="Running the 3-way match…",
        executor=_exec_three_way_match,
        required_module="purchase_store",
    ),
    ToolDef(
        name="get_purchase_vendor_performance",
        description=(
            "Get vendor performance for purchasing: delivery lead time, quotation rate trend, "
            "and short-receipt rate per vendor."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "vendor_id": {"type": "integer", "description": "Limit to one vendor (optional; use find_vendor)"},
            },
            "required": [],
        },
        label="Checking vendor performance…",
        executor=_exec_purchase_vendor_performance,
        required_module="purchase_store",
    ),
    ToolDef(
        name="get_gate_outward_register",
        description=(
            "Get the Gate Outward register: dispatch exits for invoices, debit notes, and "
            "scrap (first 50 rows). Optionally filter by source document type."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "q":     {"type": "string", "description": "Search text (optional)"},
                "source_doc_type": {"type": "string", "description": "invoice | debit_note | scrap (optional)"},
            },
            "required": [],
        },
        label="Checking the outward register…",
        executor=_exec_gate_outward_register,
        required_module="purchase_store",
    ),
    ToolDef(
        name="get_dispatch_reconciliation",
        description=(
            "Get the dispatch reconciliation: posted invoices and debit notes with no "
            "matching gate exit flagged (first 50 rows)."
        ),
        input_schema=_REGISTER_SCHEMA,
        label="Reconciling dispatches…",
        executor=_exec_dispatch_reconciliation,
        required_module="purchase_store",
    ),
    ToolDef(
        name="get_issue_register",
        description=(
            "Get the Store Issue register: departmental/cost-center material consumption "
            "with expense account and analytic tagging (first 50 rows)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "q":     {"type": "string", "description": "Search text (optional)"},
                "analytic_account_id": {"type": "integer", "description": "Limit to one analytic account (optional)"},
            },
            "required": [],
        },
        label="Checking the issue register…",
        executor=_exec_issue_register,
        required_module="purchase_store",
    ),
    ToolDef(
        name="get_stock_tie_out",
        description=(
            "Get the stock tie-out: per-product received vs issued vs on-hand variance "
            "reconciliation. Optionally limit to one product."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "product_id": {"type": "integer", "description": "Limit to one product (optional; use find_product)"},
            },
            "required": [],
        },
        label="Running the stock tie-out…",
        executor=_exec_stock_tie_out,
        required_module="purchase_store",
    ),
    # ── generic report builder ───────────────────────────────────────────────
    ToolDef(
        name="list_report_sources",
        description=(
            "List the raw data sources available to run_custom_report. Without arguments: "
            "all available source keys with labels. With a source_key: that source's full "
            "field list (key, type, enum values, aggregatable/groupable flags), date field, "
            "and default columns. Always call this before run_custom_report to get valid "
            "field names."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source_key": {"type": "string", "description": "Source key to describe in detail (optional)"},
            },
            "required": [],
        },
        label="Checking available data sources…",
        executor=_exec_list_report_sources,
    ),
    ToolDef(
        name="run_custom_report",
        description=(
            "Run an ad-hoc tabular query over raw records (invoices, bills, journal lines, "
            "payments, customers, vendors, accounts, and module data) when no dedicated tool "
            "fits the question. Supports column selection, filters, grouping, aggregates "
            "(sum/avg/count/min/max), sorting, and a date range. Call list_report_sources "
            "first to discover valid source keys and field names. Returns at most 50 rows."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "source_key": {"type": "string", "description": "Data source key (from list_report_sources)"},
                "columns": {"type": "array", "items": {"type": "string"},
                            "description": "Field keys to return (optional; defaults per source)"},
                "filters": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "op": {"type": "string", "description": "equals, not_equals, contains, gt, gte, lt, lte, in, between, is_null…"},
                        "value": {},
                    },
                    "required": ["field", "op"],
                }, "description": "Filter clauses (optional)"},
                "group_by": {"type": "array", "items": {"type": "string"},
                             "description": "Field keys to group by (optional)"},
                "aggregates": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "fn": {"type": "string", "enum": ["sum", "avg", "count", "min", "max"]},
                    },
                    "required": ["field", "fn"],
                }, "description": "Aggregates (required when group_by is used)"},
                "sort": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "dir": {"type": "string", "enum": ["asc", "desc"]},
                    },
                    "required": ["field"],
                }, "description": "Sort order (optional)"},
                "date_start": {"type": "string", "description": "Date range start YYYY-MM-DD (optional)"},
                "date_end":   {"type": "string", "description": "Date range end YYYY-MM-DD (optional)"},
                "page_size":  {"type": "integer", "description": "Max rows (capped at 50)"},
            },
            "required": ["source_key"],
        },
        label="Running a custom report…",
        executor=_exec_run_custom_report,
    ),
    # ── production ───────────────────────────────────────────────────────────
    ToolDef(
        name="get_manufacturing_dashboard",
        description=(
            "Get manufacturing KPIs: production orders by state, WIP value, and recent "
            "completion/billing activity."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking manufacturing KPIs…",
        executor=_exec_mfg_dashboard,
        required_module="production",
    ),
    ToolDef(
        name="get_wip_aging",
        description=(
            "Get work-in-progress aging: open production orders grouped by days since started."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking WIP aging…",
        executor=_exec_wip_aging,
        required_module="production",
    ),
    ToolDef(
        name="get_production_summary",
        description=(
            "Get the production summary for a period: orders grouped by state with value "
            "totals and billed revenue."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking production summary…",
        executor=_exec_production_summary,
        required_module="production",
    ),
    ToolDef(
        name="get_customer_custody",
        description=(
            "Get customer custody stock: goods currently held on behalf of customers, one "
            "row per customer and product."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking customer custody stock…",
        executor=_exec_customer_custody,
        required_module="production",
    ),
    # ── weaving ──────────────────────────────────────────────────────────────
    ToolDef(
        name="get_weaving_dashboard",
        description=(
            "Get weaving unit KPIs: yarn received/used/balance (Kg/Lbs/Bags), grey meters, "
            "dispatch meters, weaving revenue, average efficiency, and contract status counts."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking weaving KPIs…",
        executor=_exec_weaving_dashboard,
        required_module="weaving",
    ),
    ToolDef(
        name="get_weaving_daily",
        description=(
            "Get weaving daily operations for a period: yarn received/sized, fabric produced/"
            "delivered, efficiency by shift/operator/loom, and an activity feed."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking weaving daily ops…",
        executor=_exec_weaving_daily,
        required_module="weaving",
    ),
    ToolDef(
        name="get_contract_control",
        description=(
            "Get one weaving contract's control panel: yarn received/sized/used/balance, "
            "grey vs dispatched meters, progress %, and activity. Use find_wv_contract first."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "contract_id": {"type": "integer", "description": "Weaving contract id (required)"},
            },
            "required": ["contract_id"],
        },
        label="Checking contract control…",
        executor=_exec_contract_control,
        required_module="weaving",
    ),
    ToolDef(
        name="get_weaving_customer_kpi",
        description=(
            "Get weaving customer contract KPIs: meters, yarn, progress, and revenue rolled "
            "up per customer."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking weaving customer KPIs…",
        executor=_exec_weaving_customer_kpi,
        required_module="weaving",
    ),
    ToolDef(
        name="find_wv_contract",
        description=(
            "Search weaving contracts by (partial) contract number and return up to 10 matches "
            "as {id, number, status, customer_id}. Use this first before get_contract_control."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial contract number"},
            },
            "required": ["query"],
        },
        label="Looking up the weaving contract…",
        executor=_exec_find_wv_contract,
        required_module="weaving",
    ),
    # ── pra ──────────────────────────────────────────────────────────────────
    ToolDef(
        name="get_pra_logs",
        description=(
            "Get recent PRA e-invoice submission log entries (success/failure, response codes). "
            "Optionally filter by invoice_id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer", "description": "Filter to one invoice (optional)"},
                "limit": {"type": "integer", "description": "Max rows (default 50, max 100)"},
            },
            "required": [],
        },
        label="Checking PRA submission logs…",
        executor=_exec_pra_logs,
        required_module="pra",
    ),
    ToolDef(
        name="get_invoice_pra_status",
        description=(
            "Get one invoice's PRA status: pra_status, fiscal number, USIN, and submitted_at."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "invoice_id": {"type": "integer", "description": "Invoice id (required)"},
            },
            "required": ["invoice_id"],
        },
        label="Checking invoice PRA status…",
        executor=_exec_invoice_pra_status,
        required_module="pra",
    ),
    ToolDef(
        name="get_pra_today_summary",
        description=(
            "Summarize PRA e-invoice compliance for a date window (default today): invoice "
            "counts by pra_status (submitted/pending/failed/not_required)."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Summarising PRA status…",
        executor=_exec_pra_today_summary,
        required_module="pra",
    ),
    # ── banking / GL ─────────────────────────────────────────────────────────
    ToolDef(
        name="get_day_book",
        description=(
            "Get the Day Book for a date (default today): vouchers grouped by type with "
            "counts and debit totals, plus source-document activity."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date YYYY-MM-DD (optional, default today)"},
            },
            "required": [],
        },
        label="Checking the day book…",
        executor=_exec_day_book,
    ),
    ToolDef(
        name="get_account_ledger",
        description=(
            "Get the General Ledger for one account (opening balance, period movements, "
            "closing). Pass account_id or account_code — use find_account first to resolve a name."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "account_id": {"type": "integer", "description": "Account id (preferred)"},
                "account_code": {"type": "string", "description": "Account code (alternative)"},
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "limit": {"type": "integer", "description": "Max lines (default 50, max 100)"},
            },
            "required": [],
        },
        label="Fetching the account ledger…",
        executor=_exec_account_ledger,
    ),
    ToolDef(
        name="get_cash_bank_subledger",
        description=(
            "Get the cash/bank sub-ledger: per cash/bank GL account opening, debit, credit, "
            "and closing balances that reconcile to the bank control."
        ),
        input_schema=_DATE_RANGE_SCHEMA,
        label="Checking cash & bank sub-ledger…",
        executor=_exec_cash_bank_subledger,
    ),
    ToolDef(
        name="list_bank_accounts",
        description="List linked bank accounts with their current GL balances.",
        input_schema=_EMPTY_SCHEMA,
        label="Listing bank accounts…",
        executor=_exec_list_bank_accounts,
    ),
    ToolDef(
        name="find_account",
        description=(
            "Search Chart of Accounts by (partial) name or code and return up to 10 matches "
            "as {id, code, name, type, is_group}. Use before get_account_ledger."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial account name or code"},
            },
            "required": ["query"],
        },
        label="Looking up the account…",
        executor=_exec_find_account,
    ),
    ToolDef(
        name="get_analytic_pl",
        description=(
            "Get a P&L filtered to one analytic dimension (cost center / project / department). "
            "Use find_analytic_account first to resolve the name to an id."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "analytic_account_id": {
                    "type": "integer",
                    "description": "Analytic account id (required)",
                },
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
            },
            "required": ["analytic_account_id"],
        },
        label="Checking analytic P&L…",
        executor=_exec_analytic_pl,
    ),
    ToolDef(
        name="find_analytic_account",
        description=(
            "Search analytic accounts (cost centers / projects / departments) by name or code "
            "and return up to 10 matches as {id, code, name, type}."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Full or partial analytic name or code"},
            },
            "required": ["query"],
        },
        label="Looking up the cost center…",
        executor=_exec_find_analytic_account,
    ),
    ToolDef(
        name="get_journal_report",
        description=(
            "Get journal voucher lines for a period (optionally filtered by voucher_type or "
            "voucher_number). Returns at most 100 lines — narrow the date range for full data."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Period start YYYY-MM-DD (optional)"},
                "end":   {"type": "string", "description": "Period end YYYY-MM-DD (optional)"},
                "voucher_type": {"type": "string", "description": "e.g. JV, CP, BR (optional)"},
                "voucher_number": {"type": "string", "description": "Partial JV number (optional)"},
                "limit": {"type": "integer", "description": "Max lines (default 50, max 100)"},
            },
            "required": [],
        },
        label="Fetching journal lines…",
        executor=_exec_journal_report,
    ),
    # ── deferred revenue ─────────────────────────────────────────────────────
    ToolDef(
        name="list_deferred_schedules",
        description=(
            "List deferred-revenue recognition schedules (IFRS-15), optionally filtered by "
            "status (active/completed/cancelled)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "active | completed | cancelled"},
                "limit": {"type": "integer", "description": "Max rows (default 50, max 100)"},
            },
            "required": [],
        },
        label="Listing deferred-revenue schedules…",
        executor=_exec_list_deferred_schedules,
    ),
    # ── staff commissions ────────────────────────────────────────────────────
    ToolDef(
        name="get_commission_ledger",
        description=(
            "Get staff sales-commission ledger entries (draft/approved/posted) with invoiced, "
            "recovered, and payable amounts. Optional period (YYYY-MM) or user_id filter. "
            "Not telecom franchise commissions — those use get_commission_aging."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "period": {"type": "string", "description": "Period YYYY-MM (optional)"},
                "user_id": {"type": "integer", "description": "Staff user id (optional)"},
            },
            "required": [],
        },
        label="Checking staff commissions…",
        executor=_exec_commission_ledger,
    ),
    ToolDef(
        name="list_commission_plans",
        description="List staff commission plans: rate, sales/recovery targets, and bonus.",
        input_schema=_EMPTY_SCHEMA,
        label="Listing commission plans…",
        executor=_exec_list_commission_plans,
    ),
    # ── fixed assets ─────────────────────────────────────────────────────────
    ToolDef(
        name="list_fixed_assets",
        description=(
            "List active fixed assets (not disposed): acquisition date, cost, accumulated "
            "depreciation, and net book value."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max rows (default 50, max 100)"},
            },
            "required": [],
        },
        label="Listing fixed assets…",
        executor=_exec_list_fixed_assets,
    ),
    # ── telecom leftovers ────────────────────────────────────────────────────
    ToolDef(
        name="get_postpaid_book",
        description=(
            "Get telecom postpaid billing cycles with collection and remittance status."
        ),
        input_schema=_EMPTY_SCHEMA,
        label="Checking postpaid book…",
        executor=_exec_postpaid_book,
        required_module="telecom",
    ),
    ToolDef(
        name="get_tracker_statement",
        description=(
            "Get the telecom tracker (wallet) statement: account balances and recent "
            "transactions reconciled to GL deposit/load accounts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "tracker_account_id": {
                    "type": "integer",
                    "description": "Filter to one tracker account (optional)",
                },
            },
            "required": [],
        },
        label="Checking tracker statement…",
        executor=_exec_tracker_statement,
        required_module="telecom",
    ),
)

TOOL_REGISTRY: dict[str, ToolDef] = {t.name: t for t in _TOOLS}


# ── Derivations + dispatch ────────────────────────────────────────────────────

def anthropic_tools(names: Iterable[str]) -> list[dict]:
    """Anthropic-shaped tool defs for the named registry entries."""
    return [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in (TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY)
    ]


def openai_tools(names: Iterable[str]) -> list[dict]:
    """OpenAI function-calling-shaped tool defs (what litellm is passed)."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in (TOOL_REGISTRY[n] for n in names if n in TOOL_REGISTRY)
    ]


def tool_labels() -> dict[str, str]:
    return {t.name: t.label for t in TOOL_REGISTRY.values()}


def filter_by_modules(names: Iterable[str], enabled_modules: set[str]) -> list[str]:
    """Drop tool names whose required_module isn't installed for the tenant.
    Agent-level gating (AgentDef.required_module) already implies this for
    well-formed agents — this is defense in depth against a registry entry
    granted to an agent outside its module."""
    return [
        n for n in names
        if n in TOOL_REGISTRY
        and (
            TOOL_REGISTRY[n].required_module is None
            or TOOL_REGISTRY[n].required_module in enabled_modules
        )
    ]


def execute_tool(name: str, tool_input: dict, session: Session, user: User) -> tuple[str, bool]:
    """Run one tool call; returns (json_text, is_error). Unknown names and
    executor exceptions become error payloads the model can recover from,
    never HTTP failures mid-stream."""
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return json.dumps({"error": f"Unknown tool: {name}"}), True
    try:
        result = tool.executor(session, user, tool_input)
    except Exception as exc:
        return json.dumps({"error": str(exc)}), True
    text = json.dumps(_json_safe(result))
    if len(text) > MAX_TOOL_RESULT_CHARS:
        text = json.dumps({
            "truncated": True,
            "note": (
                "Result was too large and has been truncated; totals may be "
                "incomplete. Narrow the query (date range or filters) for full data."
            ),
            "data": text[:MAX_TOOL_RESULT_CHARS],
        })
    return text, False
