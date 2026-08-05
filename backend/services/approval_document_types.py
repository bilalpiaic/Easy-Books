"""Approval-workflow document-type catalog (#123 LOV).

Single source of truth for the Document Type list-of-values on
Approval Workflows. Types are seeded from every module available across
all tenant business models (MODULE_REGISTRY / MODULES_BY_MODEL), then
unioned with any ``document_type`` values already stored on
``ApprovalWorkflow`` rows in any tenant so historically configured keys
never disappear from the LOV.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from sqlmodel import Session, col, select


@dataclass(frozen=True)
class DocTypeDef:
    key: str
    label: str
    module: str  # MODULE_REGISTRY id; "base" = always available


# Full product catalog — one entry per approvable document entity.
# Keys stay stable (snake_case) and match submit_document() callers where
# those already exist (invoice / bill / purchase_order / journal).
_CATALOG: tuple[DocTypeDef, ...] = (
    # base
    DocTypeDef("invoice", "Sales Invoice", "base"),
    DocTypeDef("bill", "Purchase Bill", "base"),
    DocTypeDef("journal", "Journal Entry", "base"),
    DocTypeDef("credit_note", "Credit Note", "base"),
    DocTypeDef("debit_note", "Debit Note", "base"),
    DocTypeDef("payment_received", "Payment Received", "base"),
    DocTypeDef("bill_payment", "Bill Payment", "base"),
    DocTypeDef("customer_advance", "Customer Advance", "base"),
    DocTypeDef("vendor_advance", "Vendor Advance", "base"),
    DocTypeDef("commission", "Sales Commission", "base"),
    DocTypeDef("lease", "Lease Contract", "base"),
    DocTypeDef("fixed_asset", "Fixed Asset", "base"),
    DocTypeDef("budget", "Budget", "base"),
    # inventory / production
    DocTypeDef("purchase_order", "Purchase Order", "production"),
    DocTypeDef("grn", "Goods Receipt Note", "production"),
    DocTypeDef("production_order", "Production Order", "production"),
    # purchase_store
    DocTypeDef("purchase_demand", "Purchase Demand", "purchase_store"),
    DocTypeDef("comparative", "Comparative Statement", "purchase_store"),
    DocTypeDef("gate_inward", "Gate Inward", "purchase_store"),
    DocTypeDef("gate_outward", "Gate Outward", "purchase_store"),
    DocTypeDef("store_issue", "Store Issue", "purchase_store"),
    # hrm
    DocTypeDef("payroll_run", "Payroll Run", "hrm"),
    # telecom
    DocTypeDef("load_transfer", "Load Transfer", "telecom"),
    DocTypeDef("sim_activation", "SIM Activation", "telecom"),
    # healthcare
    DocTypeDef("healthcare_admission", "IPD Admission", "healthcare"),
    DocTypeDef("healthcare_opd_visit", "OPD Visit", "healthcare"),
    DocTypeDef("healthcare_lab_order", "Lab Order", "healthcare"),
    # weaving
    DocTypeDef("weaving_contract", "Weaving Contract", "weaving"),
    DocTypeDef("weaving_dispatch", "Weaving Dispatch", "weaving"),
    # spinning
    DocTypeDef("spinning_plan", "Spinning Production Plan", "spinning"),
    DocTypeDef("spinning_bale_receipt", "Bale Receipt", "spinning"),
    DocTypeDef("spinning_cone_output", "Cone Output", "spinning"),
    DocTypeDef("spinning_dispatch", "Yarn Dispatch", "spinning"),
    # textile_processing
    DocTypeDef("textile_sales_order", "Processing Sales Order", "textile_processing"),
    DocTypeDef("textile_production", "Processing Production Order", "textile_processing"),
    DocTypeDef("textile_dispatch", "Fresh Dispatch", "textile_processing"),
    DocTypeDef("textile_settlement", "Grey Settlement", "textile_processing"),
)

# purchase_order is also used when purchase_store is installed (dual-homed).
# Treat it as available under either module.
_MODULE_ALIASES: dict[str, tuple[str, ...]] = {
    "purchase_order": ("production", "purchase_store"),
}

DOCUMENT_TYPE_KEYS: frozenset[str] = frozenset(d.key for d in _CATALOG)
DOCUMENT_TYPES_BY_KEY: dict[str, DocTypeDef] = {d.key: d for d in _CATALOG}


def _modules_for(doc: DocTypeDef) -> set[str]:
    aliases = _MODULE_ALIASES.get(doc.key)
    if aliases:
        return set(aliases)
    return {doc.module}


def catalog_for_modules(modules: Iterable[str]) -> list[dict]:
    """Return LOV rows for the given installed-module set (base always in)."""
    enabled = set(modules) | {"base"}
    out: list[dict] = []
    for doc in _CATALOG:
        if _modules_for(doc) & enabled:
            out.append({"key": doc.key, "label": doc.label, "module": doc.module})
    return out


def all_catalog_types() -> list[dict]:
    """Full product catalog (every module / every tenant business model)."""
    return [{"key": d.key, "label": d.label, "module": d.module} for d in _CATALOG]


def _tenant_modules(session: Session) -> set[str]:
    """Union of enabled_modules across ALL tenants + every MODULES_BY_MODEL default."""
    from db import MODULES_BY_MODEL, MODULE_REGISTRY
    from models import Tenant

    modules: set[str] = set(MODULE_REGISTRY.keys())
    for defaults in MODULES_BY_MODEL.values():
        modules.update(defaults)
    rows = session.exec(select(Tenant.enabled_modules)).all()
    for raw in rows:
        try:
            modules.update(json.loads(raw or "[]"))
        except (TypeError, json.JSONDecodeError):
            continue
    return modules


def _workflow_types_all_tenants(session: Session) -> set[str]:
    from models import ApprovalWorkflow

    rows = session.exec(
        select(col(ApprovalWorkflow.document_type)).distinct()
    ).all()
    return {str(r) for r in rows if r}


def list_document_types(session: Session) -> list[dict]:
    """LOV payload: catalog seeded from all tenant modules + any DB keys.

    Always returns the full product set (types available to any tenant /
    business model), then appends unknown keys already present on workflows
    in any tenant so the LOV never hides a configured type.
    """
    modules = _tenant_modules(session)
    # Prefer full catalog; modules union is used as a soft filter only when
    # MODULE_REGISTRY is somehow empty (shouldn't happen). Otherwise show all.
    by_key: dict[str, dict] = {
        row["key"]: row for row in (catalog_for_modules(modules) or all_catalog_types())
    }
    # Ensure every canonical entry is present even if a module id is unknown
    for row in all_catalog_types():
        by_key.setdefault(row["key"], row)

    for key in sorted(_workflow_types_all_tenants(session)):
        if key not in by_key:
            label = key.replace("_", " ").title()
            by_key[key] = {"key": key, "label": label, "module": "custom"}

    return sorted(by_key.values(), key=lambda r: r["label"].lower())


def is_valid_document_type(session: Session, key: str) -> bool:
    if key in DOCUMENT_TYPE_KEYS:
        return True
    # Allow types already present on any tenant's workflow (legacy / custom)
    return key in _workflow_types_all_tenants(session)
