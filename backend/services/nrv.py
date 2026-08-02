"""NRV write-down runs (#257 / IAS 2.9).

Compares on-hand cost to net realisable value; posts write-downs as
Dr Inventory Write-down Expense / Cr Inventory Allowance (or Inventory).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import NrVLine, NrVRun, Product, User
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction
from routers.common import get_or_create_account, next_number


class NrVError(Exception):
    pass


def preview_lines(
    session: Session,
    tenant_id: int,
    overrides: Optional[dict[int, Decimal]] = None,
) -> list[dict]:
    """Compute write-downs for all stock products with qty > 0 and NRV set."""
    overrides = overrides or {}
    products = session.exec(
        select(Product).where(
            Product.tenant_id == tenant_id,
            Product.product_type == "stock",
            Product.is_active == True,  # noqa: E712
            Product.stock_qty > 0,
        )
    ).all()
    rows: list[dict] = []
    for p in products:
        qty = D(p.stock_qty)
        cost = D(p.avg_cost)
        nrv = overrides.get(p.id)  # type: ignore
        if nrv is None:
            if p.nrv_unit is None:
                continue
            nrv = D(p.nrv_unit)
        else:
            nrv = D(nrv)
        write_down = money(max(ZERO, (cost - nrv) * qty))
        if write_down <= ZERO:
            continue
        rows.append({
            "product_id": p.id,
            "product_name": p.name,
            "qty": qty,
            "unit_cost": cost,
            "nrv_unit": nrv,
            "write_down": write_down,
        })
    return rows


def create_and_post(
    session: Session,
    actor: User,
    *,
    run_date: str,
    use_allowance: bool = True,
    notes: Optional[str] = None,
    overrides: Optional[dict[int, Decimal]] = None,
) -> NrVRun:
    preview = preview_lines(session, actor.tenant_id, overrides)
    if not preview:
        raise NrVError("No products require an NRV write-down")

    number = next_number(session, actor.tenant_id, "nrv_run", "NRV")
    run = NrVRun(
        tenant_id=actor.tenant_id,
        number=number,
        run_date=run_date,
        status="draft",
        use_allowance=use_allowance,
        notes=notes,
        created_by_id=actor.id,
    )
    session.add(run)
    session.flush()

    total = ZERO
    for row in preview:
        session.add(NrVLine(
            tenant_id=actor.tenant_id,
            run_id=run.id,  # type: ignore
            product_id=row["product_id"],
            qty=row["qty"],
            unit_cost=row["unit_cost"],
            nrv_unit=row["nrv_unit"],
            write_down=row["write_down"],
        ))
        total += row["write_down"]

    exp = get_or_create_account(
        session, actor.tenant_id, "5041", "Inventory Write-down", "Expense",
    )
    if use_allowance:
        credit_acc = get_or_create_account(
            session, actor.tenant_id, "1295", "Inventory Valuation Allowance", "Asset",
        )
    else:
        credit_acc = get_or_create_account(
            session, actor.tenant_id, "1200", "Inventory (Raw Material)", "Asset",
        )

    txn = post_transaction(
        session, actor,
        date=run_date,
        description=f"NRV write-down {number}",
        entries=[
            EntryInput(account_id=exp.id, debit=money(total)),
            EntryInput(account_id=credit_acc.id, credit=money(total)),
        ],
        reference=number,
        audit_entity_type="nrv_run",
        audit_detail={"total": str(total), "use_allowance": use_allowance},
        voucher_type="JV",
    )
    run.status = "posted"
    run.transaction_id = txn.id
    session.add(run)
    session.flush()
    return run


def reverse_run(session: Session, actor: User, run: NrVRun) -> NrVRun:
    if run.status != "posted" or not run.transaction_id:
        raise NrVError("Only posted NRV runs can be reversed")
    from models import JournalEntry, Transaction
    from datetime import date as DateType

    orig = session.get(Transaction, run.transaction_id)
    if not orig:
        raise NrVError("Original transaction missing")
    lines = session.exec(
        select(JournalEntry).where(JournalEntry.transaction_id == orig.id)
    ).all()
    entries = []
    for ln in lines:
        # Flip Dr/Cr
        if D(ln.debit) > ZERO:
            entries.append(EntryInput(account_id=ln.account_id, credit=D(ln.debit)))
        elif D(ln.credit) > ZERO:
            entries.append(EntryInput(account_id=ln.account_id, debit=D(ln.credit)))
    txn = post_transaction(
        session, actor,
        date=DateType.today().isoformat(),
        description=f"Reverse NRV {run.number}",
        entries=entries,
        reference=f"REV-{run.number}",
        audit_entity_type="nrv_run",
        audit_detail={"reversed_run_id": run.id},
        voucher_type="JV",
    )
    run.status = "reversed"
    run.reverse_transaction_id = txn.id
    session.add(run)
    session.flush()
    return run
