"""Uniform CoA / stock-location / cross-module integration for installable packs.

Industry modules historically seeded CoA only at tenant *creation* via
``business_model``. Installing a pack later left required accounts/locations
missing. This module is the single ensure-path used by ``POST /api/modules/*/install``
and by an integration health check.
"""
from __future__ import annotations

from typing import Any

from sqlmodel import Session, select

from models import Account, StockLocation
from routers.common import get_or_create_account

# (code, name, type, is_memo, parent_code)
# Collision-safe textile expense codes: 5220 / 5215 avoid manufacturing 5200/5210.
_MODULE_COA: dict[str, list[tuple[str, str, str, bool, str]]] = {
    "inventory": [
        ("1200", "Inventory Asset", "Asset", False, "11"),
        ("1250", "GST Receivable (Input)", "Asset", False, "11"),
        ("5010", "Cost of Goods Sold", "Expense", False, "51"),
        ("5020", "Freight In", "Expense", False, "51"),
        ("5040", "Inventory Adjustments", "Expense", False, "51"),
    ],
    "production": [
        ("1200", "Raw Material Inventory", "Asset", False, "11"),
        ("1201", "Work-in-Progress", "Asset", False, "11"),
        ("1202", "Finished Goods Inventory", "Asset", False, "11"),
        ("1210", "Customer Goods on Hand", "Asset", True, "11"),
        ("1250", "GST Receivable (Input)", "Asset", False, "11"),
        ("2150", "Customer Goods Liability", "Liability", True, "21"),
        ("4010", "Service Revenue (Value-Add)", "Revenue", False, "41"),
        ("5010", "Cost of Goods Sold", "Expense", False, "51"),
        ("5100", "Direct Labour", "Expense", False, "51"),
        ("5110", "Subcontractor Costs", "Expense", False, "51"),
        ("5200", "Manufacturing Overhead", "Expense", False, "51"),
        ("5210", "Indirect Materials", "Expense", False, "51"),
    ],
    "textile_processing": [
        ("1210", "Customer Goods on Hand", "Asset", True, "11"),
        ("2150", "Customer Goods Liability", "Liability", True, "21"),
        ("4150", "Processing Revenue", "Revenue", False, "41"),
        ("4160", "Wastage Sales Revenue", "Revenue", False, "41"),
        # Distinct from manufacturing 5200/5210
        ("5220", "Contractor Labor Expense", "Expense", False, "52"),
        ("5215", "Process Shrinkage Expense", "Expense", False, "52"),
    ],
    "spinning": [
        ("1200", "Raw Cotton / Fiber Inventory", "Asset", False, "11"),
        ("1201", "WIP — Opening & Carding", "Asset", False, "11"),
        ("1202", "WIP — Drawing & Roving", "Asset", False, "11"),
        ("1203", "WIP — Ring Spinning", "Asset", False, "11"),
        ("1204", "Finished Yarn Inventory", "Asset", False, "11"),
        ("1250", "GST Receivable (Input)", "Asset", False, "11"),
        ("4170", "Yarn Sales Revenue", "Revenue", False, "41"),
        ("5010", "Cost of Goods Sold", "Expense", False, "51"),
        ("5100", "Direct Labour", "Expense", False, "51"),
        ("5200", "Manufacturing Overhead", "Expense", False, "51"),
        ("5901", "Hard Waste / Flat Strips", "Expense", False, "59"),
        ("5902", "Soft Waste / Noil", "Expense", False, "59"),
        ("5903", "Pneumafil / Dust Waste", "Expense", False, "59"),
        ("5904", "Moisture / Conditioning Loss", "Expense", False, "59"),
    ],
    "weaving": [
        # Memo ops in v1 — seed revenue stub + custodial pair for future GL
        ("1210", "Customer Goods on Hand", "Asset", True, "11"),
        ("2150", "Customer Goods Liability", "Liability", True, "21"),
        ("4180", "Weaving Revenue", "Revenue", False, "41"),
    ],
    "healthcare": [
        ("1102", "Lab Receivable", "Asset", False, "11"),
        ("1200", "Medical Supplies Inventory", "Asset", False, "11"),
        ("1250", "GST Receivable (Input)", "Asset", False, "11"),
        ("2310", "Patient Advance / Deposit", "Liability", False, "21"),
        ("4100", "OPD Consultation Revenue", "Revenue", False, "41"),
        ("4101", "OPD Follow-up Revenue", "Revenue", False, "41"),
        ("4110", "Laboratory Revenue", "Revenue", False, "41"),
        ("4111", "Sample Collection Revenue", "Revenue", False, "41"),
        ("4120", "Surgical / Procedure Revenue", "Revenue", False, "41"),
        ("4121", "Ward / Bed Charges Revenue", "Revenue", False, "41"),
        ("4122", "Nursing & Allied Services", "Revenue", False, "41"),
        ("4130", "Pharmacy Revenue", "Revenue", False, "41"),
        ("5010", "Cost of Medicines Sold", "Expense", False, "51"),
        ("5120", "Medical Supplies & Consumables", "Expense", False, "52"),
        ("5130", "Lab Reagents & Chemicals", "Expense", False, "52"),
    ],
    "telecom": [
        ("1110", "Commission Receivable", "Asset", False, "11"),
        ("1120", "RSO Receivables", "Asset", False, "11"),
        ("1200", "SIM Card Inventory", "Asset", False, "11"),
        ("1201", "Scratch Card / PIN Inventory", "Asset", False, "11"),
        ("1202", "Device Inventory", "Asset", False, "11"),
        ("1210", "Tracker Deposit Balance", "Asset", False, "11"),
        ("1211", "Load Float Asset (MSR SIM)", "Asset", False, "11"),
        ("1250", "GST Receivable (Input)", "Asset", False, "11"),
        ("2010", "Operator Payable", "Liability", False, "21"),
        ("4000", "Airtime / Recharge Revenue", "Revenue", False, "41"),
        ("4010", "SIM Activation Revenue", "Revenue", False, "41"),
        ("4020", "Load Uplift Commission (3%)", "Revenue", False, "41"),
        ("4030", "SIM Sale Revenue", "Revenue", False, "41"),
        ("4060", "FCA Target Commission", "Revenue", False, "41"),
        ("5010", "COGS — Devices", "Expense", False, "51"),
        ("5011", "COGS — SIMs", "Expense", False, "51"),
    ],
    "purchase_store": [
        # Uses inventory CoA; ensure common purchase expense leaves exist
        ("5020", "Freight In", "Expense", False, "51"),
        ("5030", "Storage & Handling", "Expense", False, "51"),
    ],
}

_MODULE_LOCATIONS: dict[str, list[tuple[str, str, str]]] = {
    "inventory": [
        ("MAIN", "Main Store", "own"),
    ],
    "production": [
        ("MAIN", "Main Store", "own"),
        ("GODOWN", "Customer Goods Godown", "customer_custodial"),
        ("WIP", "Work-in-Progress Floor", "wip"),
    ],
    "purchase_store": [
        ("MAIN", "Main Store", "own"),
        ("GODOWN", "Receiving Godown", "own"),
    ],
    "spinning": [
        ("RAW", "Raw Cotton Store", "own"),
        ("WIP-CARD", "WIP Carding", "wip"),
        ("WIP-DRAW", "WIP Drawing", "wip"),
        ("WIP-SPIN", "WIP Spinning", "wip"),
        ("FG-YARN", "Finished Yarn", "own"),
    ],
    "textile_processing": [
        ("GODOWN", "Customer Grey Godown", "customer_custodial"),
        ("REJ", "Rejection Bay", "customer_custodial"),
        ("WIP", "Processing Floor", "wip"),
        ("FG-PACK", "Fresh Packing Store", "own"),
    ],
    "weaving": [
        ("MAIN", "Main Store", "own"),
        ("GODOWN", "Yarn / Grey Godown", "customer_custodial"),
    ],
    "healthcare": [
        ("MAIN", "Main Store", "own"),
        ("PHARM", "Pharmacy Store", "own"),
        ("LAB", "Lab Consumables", "own"),
    ],
    "telecom": [
        ("MAIN", "Main Store", "own"),
        ("SIM_STOCK", "SIM Card Store", "own"),
    ],
}

# Module → core systems it must integrate with (for health report)
_MODULE_LINKS: dict[str, list[str]] = {
    "inventory": ["coa", "stock_locations", "stock_movements"],
    "production": ["coa", "stock_locations", "inventory", "invoices"],
    "purchase_store": ["coa", "stock_locations", "purchase_orders", "gate_inward", "bills"],
    "spinning": ["coa", "stock_locations", "inventory", "invoices", "bills"],
    "textile_processing": ["coa", "stock_locations", "invoices", "bills", "gate_inward"],
    "weaving": ["coa", "stock_locations"],
    "healthcare": ["coa", "stock_locations", "inventory", "invoices"],
    "telecom": ["coa", "stock_locations"],
    "hrm": ["coa"],
}


def _parent_id(session: Session, tenant_id: int, parent_code: str | None) -> int | None:
    if not parent_code:
        return None
    p = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == parent_code)
    ).first()
    return p.id if p else None


def ensure_module_coa(session: Session, tenant_id: int, module_id: str) -> list[str]:
    """Create missing leaf accounts for a module. Never renames existing codes."""
    created: list[str] = []
    for code, name, atype, is_memo, parent_code in _MODULE_COA.get(module_id, []):
        existing = session.exec(
            select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
        ).first()
        if existing:
            continue
        acc = Account(
            tenant_id=tenant_id, code=code, name=name, type=atype,
            is_memo=is_memo, is_group=False,
            parent_id=_parent_id(session, tenant_id, parent_code),
        )
        if code == "1100":
            acc.party_type = "customer"
        elif code == "2000":
            acc.party_type = "vendor"
        session.add(acc)
        created.append(code)
    if created:
        session.flush()
    return created


def ensure_module_locations(session: Session, tenant_id: int, module_id: str) -> list[str]:
    created: list[str] = []
    for code, name, ltype in _MODULE_LOCATIONS.get(module_id, []):
        existing = session.exec(
            select(StockLocation).where(
                StockLocation.tenant_id == tenant_id,
                StockLocation.code == code,
            )
        ).first()
        if existing:
            continue
        session.add(StockLocation(
            tenant_id=tenant_id, code=code, name=name, type=ltype, is_active=True,
        ))
        created.append(code)
    if created:
        session.flush()
    return created


def ensure_module_integration(session: Session, tenant_id: int, module_id: str) -> dict[str, Any]:
    """Idempotent CoA + location seed for one module (and inventory if it depends)."""
    accounts = ensure_module_coa(session, tenant_id, module_id)
    locations = ensure_module_locations(session, tenant_id, module_id)
    # Always ensure MAIN when inventory-bearing modules install
    if module_id in ("production", "spinning", "healthcare", "telecom", "purchase_store", "weaving"):
        extra = ensure_module_locations(session, tenant_id, "inventory")
        locations = sorted(set(locations + extra))
    return {
        "module_id": module_id,
        "accounts_created": accounts,
        "locations_created": locations,
    }


def integration_status(session: Session, tenant_id: int, enabled_modules: list[str]) -> dict[str, Any]:
    """Report missing CoA codes / locations for installed industry packs."""
    modules_out = []
    for mid in sorted(enabled_modules):
        if mid not in _MODULE_COA and mid not in _MODULE_LOCATIONS:
            continue
        missing_acc = []
        for code, *_rest in _MODULE_COA.get(mid, []):
            exists = session.exec(
                select(Account.id).where(Account.tenant_id == tenant_id, Account.code == code)
            ).first()
            if not exists:
                missing_acc.append(code)
        missing_loc = []
        for code, *_rest in _MODULE_LOCATIONS.get(mid, []):
            exists = session.exec(
                select(StockLocation.id).where(
                    StockLocation.tenant_id == tenant_id, StockLocation.code == code,
                )
            ).first()
            if not exists:
                missing_loc.append(code)
        modules_out.append({
            "module_id": mid,
            "links": _MODULE_LINKS.get(mid, []),
            "missing_accounts": missing_acc,
            "missing_locations": missing_loc,
            "ok": not missing_acc and not missing_loc,
        })
    return {
        "tenant_id": tenant_id,
        "modules": modules_out,
        "all_ok": all(m["ok"] for m in modules_out) if modules_out else True,
    }


def resolve_tp_expense_account(session: Session, tenant_id: int, kind: str) -> Account:
    """Textile contractor labor / shrinkage — prefer collision-safe codes."""
    if kind == "contractor":
        # Prefer 5220; fall back to legacy 5200 if it was seeded as contractor labor
        for code, name in (
            ("5220", "Contractor Labor Expense"),
            ("5200", "Contractor Labor Expense"),
        ):
            acc = session.exec(
                select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
            ).first()
            if acc:
                return acc
        return get_or_create_account(session, tenant_id, "5220", "Contractor Labor Expense", "Expense")
    # shrinkage
    for code, name in (
        ("5215", "Process Shrinkage Expense"),
        ("5210", "Process Shrinkage Expense"),
    ):
        acc = session.exec(
            select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
        ).first()
        if acc:
            return acc
    return get_or_create_account(session, tenant_id, "5215", "Process Shrinkage Expense", "Expense")
