"""Month-end close checklist defaults + auditor ZIP pack (#262)."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime

from sqlmodel import Session, select

from models import (
    Account, AccountingPeriod, CloseChecklistItem, FixedAsset, InventoryLayer,
    JournalEntry, Product, Settings, Transaction, User,
)
from services.export_utils import safe_cell
from services.money import D


DEFAULT_CLOSE_TASKS: list[tuple[str, str, bool, int]] = [
    ("bank_recon", "Bank reconciliations complete", True, 10),
    ("fx_reval", "FX revaluation run (if multi-currency)", False, 20),
    ("deferred_recognition", "Deferred revenue recognition posted", False, 30),
    ("payroll_posted", "Payroll run posted (if HRM)", False, 40),
    ("approvals_cleared", "Pending approvals cleared / none open", True, 50),
    ("inventory_count", "Inventory count / valuation reviewed", False, 60),
    ("nrv_review", "NRV write-downs considered", False, 70),
    ("tb_reviewed", "Trial balance reviewed", True, 80),
]


def require_checklist_setting(session: Session, tenant_id: int) -> bool:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == tenant_id,
            Settings.key == "period_close_require_checklist",
        )
    ).first()
    val = (row.value if row else "true") or "true"
    return val.lower() not in ("0", "false", "no", "off")


def ensure_checklist(session: Session, period: AccountingPeriod) -> list[CloseChecklistItem]:
    existing = session.exec(
        select(CloseChecklistItem).where(
            CloseChecklistItem.tenant_id == period.tenant_id,
            CloseChecklistItem.period_id == period.id,
        ).order_by(CloseChecklistItem.sort_order, CloseChecklistItem.id)  # type: ignore
    ).all()
    if existing:
        return list(existing)
    rows: list[CloseChecklistItem] = []
    for key, label, required, order in DEFAULT_CLOSE_TASKS:
        item = CloseChecklistItem(
            tenant_id=period.tenant_id,
            period_id=period.id,  # type: ignore
            task_key=key,
            label=label,
            required=required,
            sort_order=order,
        )
        session.add(item)
        rows.append(item)
    session.flush()
    return rows


def open_required_tasks(session: Session, period: AccountingPeriod) -> list[CloseChecklistItem]:
    items = ensure_checklist(session, period)
    return [i for i in items if i.required and not i.is_done]


def assert_can_lock(session: Session, period: AccountingPeriod) -> None:
    if not require_checklist_setting(session, period.tenant_id):
        return
    open_tasks = open_required_tasks(session, period)
    if open_tasks:
        labels = ", ".join(t.label for t in open_tasks[:5])
        more = f" (+{len(open_tasks) - 5} more)" if len(open_tasks) > 5 else ""
        raise ValueError(
            f"Required close checklist incomplete: {labels}{more}. "
            "Complete required tasks or disable period_close_require_checklist in Settings."
        )


def serialize_item(i: CloseChecklistItem) -> dict:
    return {
        "id": i.id,
        "period_id": i.period_id,
        "task_key": i.task_key,
        "label": i.label,
        "required": i.required,
        "sort_order": i.sort_order,
        "is_done": i.is_done,
        "completed_at": i.completed_at,
        "completed_by_id": i.completed_by_id,
        "notes": i.notes,
    }


def _csv_bytes(headers: list[str], rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for row in rows:
        w.writerow([safe_cell(row.get(h, "")) for h in headers])
    return buf.getvalue().encode("utf-8")


def _flatten_tb_tree(nodes: list, acc: list[dict] | None = None) -> list[dict]:
    acc = acc if acc is not None else []
    for n in nodes:
        acc.append({
            "code": n.get("code", ""),
            "name": n.get("name", ""),
            "type": n.get("type", ""),
            "debit": n.get("debit", 0),
            "credit": n.get("credit", 0),
        })
        children = n.get("children") or []
        if children:
            _flatten_tb_tree(children, acc)
    return acc


def build_audit_pack_zip(
    session: Session,
    user: User,
    period: AccountingPeriod,
) -> bytes:
    """Build a formula-injection-safe ZIP of close reports for the period."""
    from routers.aging import bill_aging, invoice_aging
    from routers.reports import cash_flow_statement, get_trial_balance

    start, end = period.period_start, period.period_end

    tb = get_trial_balance(session, user, start=start, end=end)
    tb_rows = _flatten_tb_tree(tb.get("tree") or [])
    tb_csv = _csv_bytes(
        ["code", "name", "type", "debit", "credit"],
        [{**r, "debit": str(r["debit"]), "credit": str(r["credit"])} for r in tb_rows],
    )

    # GL detail — direct JE join (stable shape)
    gl_q = session.exec(
        select(
            Account.code, Account.name, Transaction.date, Transaction.jv_number,
            Transaction.description, JournalEntry.debit, JournalEntry.credit,
        )
        .join(JournalEntry, JournalEntry.transaction_id == Transaction.id)
        .join(Account, Account.id == JournalEntry.account_id)
        .where(
            Transaction.tenant_id == user.tenant_id,
            Transaction.date >= start,
            Transaction.date <= end,
        )
        .order_by(Transaction.date, Transaction.id)  # type: ignore
    ).all()
    gl_rows = [
        {
            "account_code": r[0], "account_name": r[1], "date": r[2],
            "jv_number": r[3], "description": r[4] or "",
            "debit": str(r[5]), "credit": str(r[6]),
        }
        for r in gl_q
    ]
    gl_csv = _csv_bytes(
        ["account_code", "account_name", "date", "jv_number", "description", "debit", "credit"],
        gl_rows,
    )

    ar = invoice_aging(session, user)
    ar_csv = _csv_bytes(
        ["number", "name", "due_date", "amount", "bucket", "days_past"],
        [
            {
                "number": it["number"], "name": it["name"], "due_date": it["due_date"],
                "amount": str(it["amount"]), "bucket": it["bucket"], "days_past": it["days_past"],
            }
            for it in ar.get("items", [])
        ],
    )

    ap = bill_aging(session, user)
    ap_csv = _csv_bytes(
        ["number", "name", "due_date", "amount", "bucket", "days_past"],
        [
            {
                "number": it["number"], "name": it["name"], "due_date": it["due_date"],
                "amount": str(it["amount"]), "bucket": it["bucket"], "days_past": it["days_past"],
            }
            for it in ap.get("items", [])
        ],
    )

    layers = session.exec(
        select(InventoryLayer, Product)
        .join(Product, Product.id == InventoryLayer.product_id)
        .where(
            InventoryLayer.tenant_id == user.tenant_id,
            InventoryLayer.qty_remaining > 0,
        )
    ).all()
    inv_csv = _csv_bytes(
        ["product_code", "product_name", "lot_no", "qty", "unit_cost", "value", "source_doc"],
        [
            {
                "product_code": p.code or "",
                "product_name": p.name,
                "lot_no": ly.lot_no or "",
                "qty": str(ly.qty_remaining),
                "unit_cost": str(ly.unit_cost),
                "value": str(D(ly.qty_remaining) * D(ly.unit_cost)),
                "source_doc": ly.source_doc or "",
            }
            for ly, p in layers
        ],
    )

    assets = session.exec(
        select(FixedAsset).where(FixedAsset.tenant_id == user.tenant_id)
    ).all()
    fa_csv = _csv_bytes(
        ["name", "code", "acquisition_date", "cost", "accum_depr", "book_value", "disposed"],
        [
            {
                "name": a.name,
                "code": a.code or "",
                "acquisition_date": a.acquisition_date,
                "cost": str(a.acquisition_cost),
                "accum_depr": str(a.accumulated_depreciation),
                "book_value": str(a.book_value),
                "disposed": "yes" if a.is_disposed else "no",
            }
            for a in assets
        ],
    )

    try:
        cf = cash_flow_statement(session, user, start=start, end=end)
    except Exception:
        cf = {}
    cf_rows: list[dict] = []
    if isinstance(cf, dict):
        for key in ("operating", "investing", "financing", "summary"):
            block = cf.get(key)
            if isinstance(block, dict):
                for k, v in block.items():
                    if isinstance(v, (list, dict)):
                        continue
                    cf_rows.append({"section": key, "label": k, "amount": str(v)})
            elif block is not None and not isinstance(block, (list, dict)):
                cf_rows.append({"section": "summary", "label": key, "amount": str(block)})
        for k in ("net_income", "net_change", "ending_cash", "beginning_cash"):
            if k in cf and not isinstance(cf[k], (list, dict)):
                cf_rows.append({"section": "summary", "label": k, "amount": str(cf[k])})
    cf_csv = _csv_bytes(["section", "label", "amount"], cf_rows)

    manifest = _csv_bytes(
        ["key", "value"],
        [
            {"key": "tenant_id", "value": user.tenant_id},
            {"key": "period_id", "value": period.id},
            {"key": "period_name", "value": period.name or ""},
            {"key": "period_start", "value": start},
            {"key": "period_end", "value": end},
            {"key": "exported_at", "value": datetime.utcnow().isoformat() + "Z"},
            {"key": "exported_by", "value": user.email},
        ],
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.csv", manifest)
        zf.writestr("trial_balance.csv", tb_csv)
        zf.writestr("general_ledger.csv", gl_csv)
        zf.writestr("ar_aging.csv", ar_csv)
        zf.writestr("ap_aging.csv", ap_csv)
        zf.writestr("inventory_valuation.csv", inv_csv)
        zf.writestr("fixed_assets.csv", fa_csv)
        zf.writestr("cash_flow.csv", cf_csv)
    return buf.getvalue()
