"""IFRS 15 remaining (#259): relative-SSP allocation + contract assets.

Allocation redistributes the transaction price across multi-element invoice
lines using standalone selling prices. Contract assets capture unbilled
revenue after a performance obligation is satisfied (Dr 1140 / Cr Revenue);
settling on invoice credits 1140 instead of Revenue so revenue is not
double-counted. Deferred-revenue schedules remain separate (is_deferred
products only) and use allocated line.amount.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from models import (
    ContractAsset,
    Customer,
    Product,
    RevenueAllocationAudit,
)
from services.money import D, ZERO, money, sum_money
from services.posting import EntryInput, post_transaction


def line_net(qty, rate, discount_pct=0) -> Decimal:
    """qty × rate × (1 − discount_pct/100), money-rounded."""
    base = D(qty) * D(rate)
    disc = D(discount_pct or 0)
    if disc:
        base = base * (D("100") - disc) / D("100")
    return money(base)


def allocate_relative_ssp(lines: list[dict]) -> tuple[list[Decimal], dict]:
    """Relative SSP allocation of transaction price across lines.

    Each line dict needs: qty, rate, discount_pct, ssp (optional), description.
    Returns (allocated_amounts, audit) where audit has method, transaction_price,
    and detail list of {line_index, description, ssp, weight, allocated}.
    """
    originals = [
        line_net(ln.get("qty", 1), ln.get("rate", 0), ln.get("discount_pct", 0))
        for ln in lines
    ]
    transaction_price = money(sum_money(originals))

    ssps: list[Decimal] = []
    for ln in lines:
        s = ln.get("ssp")
        ssps.append(money(s) if s is not None and D(s) > ZERO else ZERO)

    positive = [s for s in ssps if s > ZERO]
    if len(positive) >= 2 and sum_money(ssps) > ZERO:
        sum_ssp = money(sum_money(ssps))
        # allocated_i = TP × (ssp_i / sum_ssp); last line absorbs rounding.
        allocated: list[Decimal] = []
        running = ZERO
        n = len(lines)
        for i, ssp in enumerate(ssps):
            if i == n - 1:
                allocated.append(money(transaction_price - running))
            else:
                share = money(transaction_price * (ssp / sum_ssp))
                allocated.append(share)
                running = money(running + share)

        detail = []
        for i, ln in enumerate(lines):
            ssp = ssps[i]
            weight = float(ssp / sum_ssp) if sum_ssp > ZERO else 0.0
            detail.append({
                "line_index": i,
                "description": ln.get("description") or "",
                "ssp": float(ssp),
                "weight": weight,
                "allocated": float(allocated[i]),
            })
        return allocated, {
            "method": "relative_ssp",
            "transaction_price": float(transaction_price),
            "detail": detail,
        }

    detail = []
    for i, ln in enumerate(lines):
        detail.append({
            "line_index": i,
            "description": ln.get("description") or "",
            "ssp": float(ssps[i]),
            "weight": 0.0,
            "allocated": float(originals[i]),
        })
    return originals, {
        "method": "none",
        "transaction_price": float(transaction_price),
        "detail": detail,
    }


def resolve_line_ssps(
    session: Session,
    tenant_id: int,
    lines: list[Any],
) -> list[Optional[Decimal]]:
    """Resolve line-level SSP: explicit line.ssp, else qty × product.SSP."""
    out: list[Optional[Decimal]] = []
    for ln in lines:
        explicit = getattr(ln, "ssp", None)
        if explicit is not None and D(explicit) > ZERO:
            out.append(money(explicit))
            continue
        pid = getattr(ln, "product_id", None)
        if not pid:
            out.append(None)
            continue
        prod = session.exec(
            select(Product).where(Product.id == pid, Product.tenant_id == tenant_id)
        ).first()
        if prod and prod.standalone_selling_price is not None and D(prod.standalone_selling_price) > ZERO:
            out.append(money(D(getattr(ln, "qty", 1)) * D(prod.standalone_selling_price)))
        else:
            out.append(None)
    return out


def apply_allocation_to_invoice_lines(
    session: Session,
    tenant_id: int,
    invoice_id: int,
    lines: list[Any],
) -> tuple[list[Decimal], list[Optional[Decimal]], list[Decimal], dict]:
    """Run SSP allocation for invoice create/update.

    Returns (allocated_amounts, resolved_ssps, pre_allocation_amounts, audit).
    Persists RevenueAllocationAudit when method is relative_ssp (replacing any
    prior audit for this invoice).
    """
    # Drop prior audit rows on rebuild (invoice edit).
    old = session.exec(
        select(RevenueAllocationAudit).where(
            RevenueAllocationAudit.tenant_id == tenant_id,
            RevenueAllocationAudit.invoice_id == invoice_id,
        )
    ).all()
    for row in old:
        session.delete(row)
    session.flush()

    ssps = resolve_line_ssps(session, tenant_id, lines)
    pre = [
        line_net(
            getattr(ln, "qty", 1),
            getattr(ln, "rate", 0),
            getattr(ln, "discount_pct", 0),
        )
        for ln in lines
    ]
    payload = []
    for i, ln in enumerate(lines):
        payload.append({
            "qty": getattr(ln, "qty", 1),
            "rate": getattr(ln, "rate", 0),
            "discount_pct": getattr(ln, "discount_pct", 0),
            "ssp": ssps[i],
            "description": getattr(ln, "description", "") or "",
        })
    allocated, audit = allocate_relative_ssp(payload)

    if audit["method"] == "relative_ssp":
        session.add(RevenueAllocationAudit(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            transaction_price=money(audit["transaction_price"]),
            method="relative_ssp",
            detail_json=audit["detail"],
            created_at=datetime.utcnow(),
        ))
        session.flush()

    return allocated, ssps, pre, audit


def resolve_contract_asset_account(session: Session, tenant_id: int):
    from routers.common import get_default_account
    return get_default_account(
        session, tenant_id, "default_contract_asset_account",
        "1140", "Contract Asset (Unbilled)", "Asset",
    )


def certify_contract_asset(
    session: Session,
    user,
    customer_id: int,
    amount,
    certify_date: str,
    description: str,
    revenue_account_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> ContractAsset:
    """POB satisfied, unbilled: Dr Contract Asset / Cr Revenue."""
    amt = money(amount)
    if amt <= ZERO:
        raise HTTPException(400, "Contract asset amount must be positive")
    cust = session.exec(
        select(Customer).where(
            Customer.id == customer_id, Customer.tenant_id == user.tenant_id
        )
    ).first()
    if not cust:
        raise HTTPException(404, "Customer not found")

    asset_acc = resolve_contract_asset_account(session, user.tenant_id)
    if revenue_account_id:
        from models import Account
        rev = session.exec(
            select(Account).where(
                Account.id == revenue_account_id,
                Account.tenant_id == user.tenant_id,
            )
        ).first()
        if not rev:
            raise HTTPException(400, "Revenue account not found")
    else:
        from routers.common import get_default_account
        rev = get_default_account(
            session, user.tenant_id, "default_revenue_account",
            "4000", "Sales Revenue", "Revenue",
        )

    txn = post_transaction(
        session, user,
        date=certify_date,
        description=f"Contract asset — {description}",
        entries=[
            EntryInput(account_id=asset_acc.id, debit=amt, customer_id=customer_id),
            EntryInput(account_id=rev.id, credit=amt),
        ],
        audit_entity_type="contract_asset",
        audit_detail={"customer_id": customer_id, "amount": str(amt)},
        voucher_type="JV",
    )

    ca = ContractAsset(
        tenant_id=user.tenant_id,
        customer_id=customer_id,
        description=description,
        certify_date=certify_date,
        amount=amt,
        recognised_amount=ZERO,
        revenue_account_id=rev.id,
        asset_account_id=asset_acc.id,
        status="open",
        transaction_id=txn.id,
        created_by_id=user.id,
        notes=notes,
    )
    session.add(ca)
    session.flush()
    return ca


def unsettle_contract_assets_for_invoice(
    session: Session, tenant_id: int, invoice_id: int
) -> None:
    """Re-open CAs previously settled against this invoice (invoice edit)."""
    rows = session.exec(
        select(ContractAsset).where(
            ContractAsset.tenant_id == tenant_id,
            ContractAsset.invoice_id == invoice_id,
        )
    ).all()
    for ca in rows:
        ca.recognised_amount = ZERO
        ca.status = "open"
        ca.invoice_id = None
        session.add(ca)
    session.flush()


def settle_contract_assets_on_invoice(
    session: Session,
    user,
    *,
    invoice_id: int,
    customer_id: Optional[int],
    contract_asset_ids: list[int],
    available_revenue_base: Decimal,
) -> Decimal:
    """Settle open CAs against an invoice's immediate revenue credit.

    Returns the total base amount that should credit Contract Asset (1140)
    instead of Revenue. Marks each CA recognised_amount / closed.
    Does not post a separate JV — caller folds Cr 1140 into the invoice JV.
    """
    if not contract_asset_ids:
        return ZERO
    if not customer_id:
        raise HTTPException(400, "contract_asset_ids require a customer_id on the invoice")

    remaining_budget = money(available_revenue_base)
    settled_total = ZERO
    for ca_id in contract_asset_ids:
        if remaining_budget <= ZERO:
            break
        ca = session.exec(
            select(ContractAsset).where(
                ContractAsset.id == ca_id,
                ContractAsset.tenant_id == user.tenant_id,
            )
        ).first()
        if not ca:
            raise HTTPException(404, f"Contract asset {ca_id} not found")
        if ca.customer_id != customer_id:
            raise HTTPException(400, f"Contract asset {ca_id} belongs to another customer")
        if ca.status != "open":
            raise HTTPException(400, f"Contract asset {ca_id} is not open")
        open_amt = money(D(ca.amount) - D(ca.recognised_amount))
        if open_amt <= ZERO:
            continue
        take = money(min(open_amt, remaining_budget))
        ca.recognised_amount = money(D(ca.recognised_amount) + take)
        ca.invoice_id = invoice_id
        if D(ca.recognised_amount) >= D(ca.amount):
            ca.status = "closed"
        session.add(ca)
        settled_total = money(settled_total + take)
        remaining_budget = money(remaining_budget - take)
    session.flush()
    return settled_total


def settle_contract_asset_standalone(
    session: Session,
    user,
    ca_id: int,
    invoice_id: int,
) -> ContractAsset:
    """Reclassify: Dr Revenue / Cr Contract Asset for remaining open amount.

    Use when an invoice was posted without contract_asset_ids. Net effect
    matches settle-during-invoice (revenue reduced, CA cleared).
    """
    from models import Invoice

    ca = session.exec(
        select(ContractAsset).where(
            ContractAsset.id == ca_id,
            ContractAsset.tenant_id == user.tenant_id,
        )
    ).first()
    if not ca:
        raise HTTPException(404, "Contract asset not found")
    if ca.status != "open":
        raise HTTPException(400, "Contract asset is not open")

    inv = session.exec(
        select(Invoice).where(
            Invoice.id == invoice_id, Invoice.tenant_id == user.tenant_id
        )
    ).first()
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if inv.customer_id and inv.customer_id != ca.customer_id:
        raise HTTPException(400, "Invoice customer does not match contract asset")

    remaining = money(D(ca.amount) - D(ca.recognised_amount))
    if remaining <= ZERO:
        ca.status = "closed"
        session.add(ca)
        session.flush()
        return ca

    asset_acc_id = ca.asset_account_id or resolve_contract_asset_account(session, user.tenant_id).id
    rev_id = ca.revenue_account_id
    if not rev_id:
        from routers.common import get_default_account
        rev_id = get_default_account(
            session, user.tenant_id, "default_revenue_account",
            "4000", "Sales Revenue", "Revenue",
        ).id

    post_transaction(
        session, user,
        date=inv.issue_date,
        description=f"Settle contract asset #{ca.id} vs {inv.number}",
        entries=[
            EntryInput(account_id=rev_id, debit=remaining),
            EntryInput(account_id=asset_acc_id, credit=remaining, customer_id=ca.customer_id),
        ],
        audit_entity_type="contract_asset",
        audit_detail={"contract_asset_id": ca.id, "invoice_id": invoice_id, "amount": str(remaining)},
        voucher_type="JV",
    )
    ca.recognised_amount = money(D(ca.recognised_amount) + remaining)
    ca.invoice_id = invoice_id
    ca.status = "closed"
    session.add(ca)
    session.flush()
    return ca


def contract_balances_report(session: Session, tenant_id: int) -> dict:
    """Contract liability (unearned deferred) + contract asset (unbilled) by customer."""
    from models import DeferredRevenueSchedule, Invoice, Customer

    # Liability: remaining deferred schedules, attributed via invoice → customer
    scheds = session.exec(
        select(DeferredRevenueSchedule).where(
            DeferredRevenueSchedule.tenant_id == tenant_id,
            DeferredRevenueSchedule.status == "active",
        )
    ).all()
    liab_by_cust: dict[int, Decimal] = {}
    for sch in scheds:
        rem = money(D(sch.total_amount) - D(sch.recognised_amount))
        if rem <= ZERO:
            continue
        inv = session.get(Invoice, sch.invoice_id)
        if not inv or inv.tenant_id != tenant_id or not inv.customer_id:
            continue
        cid = inv.customer_id
        liab_by_cust[cid] = money(liab_by_cust.get(cid, ZERO) + rem)

    # Asset: open contract assets remaining
    assets = session.exec(
        select(ContractAsset).where(
            ContractAsset.tenant_id == tenant_id,
            ContractAsset.status == "open",
        )
    ).all()
    asset_by_cust: dict[int, Decimal] = {}
    for ca in assets:
        rem = money(D(ca.amount) - D(ca.recognised_amount))
        if rem <= ZERO:
            continue
        asset_by_cust[ca.customer_id] = money(
            asset_by_cust.get(ca.customer_id, ZERO) + rem
        )

    cust_ids = set(liab_by_cust) | set(asset_by_cust)
    customers = []
    total_liab = ZERO
    total_asset = ZERO
    if cust_ids:
        rows = session.exec(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.id.in_(list(cust_ids)),  # type: ignore[attr-defined]
            )
        ).all()
        name_map = {c.id: c.name for c in rows}
        for cid in sorted(cust_ids, key=lambda i: name_map.get(i, "")):
            liab = liab_by_cust.get(cid, ZERO)
            asset = asset_by_cust.get(cid, ZERO)
            total_liab = money(total_liab + liab)
            total_asset = money(total_asset + asset)
            customers.append({
                "customer_id": cid,
                "name": name_map.get(cid, f"#{cid}"),
                "contract_liability": float(liab),
                "contract_asset": float(asset),
            })

    return {
        "customers": customers,
        "totals": {
            "contract_liability": float(total_liab),
            "contract_asset": float(total_asset),
        },
    }
