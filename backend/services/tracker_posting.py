"""
GL-posting helpers for the telecom-franchise Tracker model.

Every helper here builds a balanced JV via services.posting.post_transaction
and returns the created Transaction (plus the domain-event row when one is
created). Callers are responsible for the outer session.commit().

Account-code lookups are centralised in `_acc()` so we never hardcode IDs;
the code passed in (e.g. "1210") is looked up per-tenant.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlmodel import Session, select

from models import Account, Transaction, User
from models_telecom import (
    LoadTransfer, Operator, RsoAgent, RsoDailyCollection, RsoStockIssue,
    SimBatch, TrackerAccount, TrackerTransaction,
)
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction


# ── account lookup ────────────────────────────────────────────────────────


def _acc(session: Session, tenant_id: int, code: str) -> Account:
    a = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()
    if a is None:
        raise HTTPException(
            status_code=400,
            detail=f"Chart-of-Accounts is missing account {code!r}. "
                   f"Re-seed the CoA or create the account manually.",
        )
    return a


# ── 5.1 — Franchise deposits funds into Tracker ───────────────────────────


def post_tracker_deposit(
    session: Session, user: User, *,
    tracker_account: TrackerAccount,
    amount: Decimal,
    date: str,
    bank_account_code: str = "1010",
    reference: Optional[str] = None,
) -> Tuple[TrackerTransaction, Transaction]:
    """Bank → Tracker deposit.  Dr 1210 / Cr 1010."""
    amount = money(D(amount))
    if amount <= ZERO:
        raise HTTPException(status_code=400, detail="Deposit amount must be > 0")

    deposit = _acc(session, user.tenant_id, "1210")
    bank = _acc(session, user.tenant_id, bank_account_code)

    txn = post_transaction(
        session, user, date=date,
        description=f"Tracker deposit — {reference or tracker_account.account_number}",
        entries=[
            EntryInput(account_id=deposit.id, debit=amount),
            EntryInput(account_id=bank.id, credit=amount),
        ],
        reference=reference,
        audit_entity_type="tracker_deposit",
        audit_detail={"tracker_account_id": tracker_account.id, "amount": str(amount)},
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_account.id,
        txn_date=date,
        txn_type="deposit",
        amount=amount,
        tracker_reference=reference,
        transaction_id=txn.id,
    )
    session.add(tt); session.flush()

    tracker_account.deposit_balance = money(D(tracker_account.deposit_balance) + amount)
    session.add(tracker_account)
    return tt, txn


# ── 5.2 — Load order (the core 3-line JV) ─────────────────────────────────


def post_load_order(
    session: Session, user: User, *,
    tracker_account: TrackerAccount,
    cash_debit: Decimal,             # PKR debited from Tracker deposit balance
    uplift_pct: Decimal = D("3.00"),  # default 3% upfront commission
    date: str,
    reference: Optional[str] = None,
) -> Tuple[TrackerTransaction, Transaction]:
    """Dr 1211 Load Float (103 %) / Cr 1210 Tracker Deposit (100 %) /
    Cr 4020 Load Uplift Commission (3 %)."""
    cash = money(D(cash_debit))
    if cash <= ZERO:
        raise HTTPException(status_code=400, detail="Load order amount must be > 0")

    pct = D(uplift_pct)
    commission = money(cash * pct / D("100"))
    load_face = money(cash + commission)

    if D(tracker_account.deposit_balance) < cash:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient Tracker deposit balance "
                   f"({tracker_account.deposit_balance} < {cash})",
        )

    load = _acc(session, user.tenant_id, "1211")
    deposit = _acc(session, user.tenant_id, "1210")
    commission_acc = _acc(session, user.tenant_id, "4020")

    txn = post_transaction(
        session, user, date=date,
        description=f"Load order — {reference or tracker_account.account_number} "
                    f"({cash} cash → {load_face} load)",
        entries=[
            EntryInput(account_id=load.id, debit=load_face),
            EntryInput(account_id=deposit.id, credit=cash),
            EntryInput(account_id=commission_acc.id, credit=commission),
        ],
        reference=reference,
        audit_entity_type="load_order",
        audit_detail={
            "tracker_account_id": tracker_account.id,
            "cash_debit": str(cash),
            "uplift_pct": str(pct),
            "load_disbursed": str(load_face),
        },
    )

    tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_account.id,
        txn_date=date,
        txn_type="load_order",
        amount=cash,
        load_disbursed=load_face,
        commission_earned=commission,
        tracker_reference=reference,
        transaction_id=txn.id,
    )
    session.add(tt); session.flush()

    tracker_account.deposit_balance = money(D(tracker_account.deposit_balance) - cash)
    tracker_account.load_balance = money(D(tracker_account.load_balance) + load_face)
    session.add(tracker_account)
    return tt, txn


# ── 5.3 — SIM / IMSI stock auto-debit ─────────────────────────────────────


def post_stock_debit(
    session: Session, user: User, *,
    tracker_account: TrackerAccount,
    inventory_account_code: str,   # "1200" SIMs or "1204" IMSI
    qty: int,
    unit_cost: Decimal,
    date: str,
    batch_number: Optional[str] = None,
) -> Tuple[Optional[SimBatch], Transaction]:
    """Dr Inventory / Cr 1210 Tracker Deposit. Creates a SimBatch when the
    inventory account is 1200."""
    total = money(D(qty) * D(unit_cost))
    if total <= ZERO:
        raise HTTPException(status_code=400, detail="Stock debit total must be > 0")
    if D(tracker_account.deposit_balance) < total:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient Tracker deposit balance for stock debit ({total})",
        )

    inv = _acc(session, user.tenant_id, inventory_account_code)
    deposit = _acc(session, user.tenant_id, "1210")

    txn = post_transaction(
        session, user, date=date,
        description=f"Tracker stock debit — {qty} × {inventory_account_code} "
                    f"@ {unit_cost} = {total}",
        entries=[
            EntryInput(account_id=inv.id, debit=total),
            EntryInput(account_id=deposit.id, credit=total),
        ],
        audit_entity_type="tracker_stock_debit",
        audit_detail={
            "tracker_account_id": tracker_account.id,
            "qty": qty, "unit_cost": str(unit_cost), "total": str(total),
        },
    )

    tracker_tt = TrackerTransaction(
        tenant_id=user.tenant_id,
        tracker_account_id=tracker_account.id,
        txn_date=date,
        txn_type="stock_debit",
        amount=total,
        transaction_id=txn.id,
    )
    session.add(tracker_tt)

    batch = None
    if inventory_account_code == "1200":
        batch = SimBatch(
            tenant_id=user.tenant_id,
            operator_id=tracker_account.operator_id,
            batch_number=batch_number or f"BATCH-{txn.id}",
            qty_received=qty,
            unit_cost=money(D(unit_cost)),
            received_date=date,
            transaction_id=txn.id,
        )
        session.add(batch); session.flush()

    tracker_account.deposit_balance = money(D(tracker_account.deposit_balance) - total)
    session.add(tracker_account)
    return batch, txn


# ── 5.4 — Load distributed MSR → RSO ──────────────────────────────────────


def post_msr_to_rso_transfer(
    session: Session, user: User, *,
    tracker_account: TrackerAccount,
    rso: RsoAgent,
    amount: Decimal,
    date: str,
) -> Tuple[LoadTransfer, Transaction]:
    """Dr 1212 RSO Load Receivable / Cr 1211 Load Float Asset."""
    amt = money(D(amount))
    if amt <= ZERO:
        raise HTTPException(status_code=400, detail="Transfer amount must be > 0")
    if D(tracker_account.load_balance) < amt:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient MSR load balance ({tracker_account.load_balance} < {amt})",
        )

    rso_rec = _acc(session, user.tenant_id, "1212")
    load = _acc(session, user.tenant_id, "1211")

    txn = post_transaction(
        session, user, date=date,
        description=f"Load transfer — MSR → RSO {rso.name} ({amt})",
        entries=[
            EntryInput(account_id=rso_rec.id, debit=amt),
            EntryInput(account_id=load.id, credit=amt),
        ],
        audit_entity_type="load_transfer",
        audit_detail={"rso_id": rso.id, "amount": str(amt)},
    )

    lt = LoadTransfer(
        tenant_id=user.tenant_id,
        transfer_date=date,
        from_type="msr",
        from_ref_id=tracker_account.id,
        to_type="rso",
        to_ref_id=rso.id,
        amount=amt,
        transaction_id=txn.id,
    )
    session.add(lt); session.flush()

    tracker_account.load_balance = money(D(tracker_account.load_balance) - amt)
    session.add(tracker_account)
    return lt, txn


# ── 5.5 — Load distributed RSO → Retail outlet ────────────────────────────


def post_rso_to_retail_transfer(
    session: Session, user: User, *,
    rso: RsoAgent,
    retail_outlet_id: int,
    amount: Decimal,
    date: str,
) -> Tuple[LoadTransfer, Transaction]:
    """Dr 1213 Retail Load Receivable / Cr 1212 RSO Load Receivable."""
    amt = money(D(amount))
    if amt <= ZERO:
        raise HTTPException(status_code=400, detail="Transfer amount must be > 0")

    retail_rec = _acc(session, user.tenant_id, "1213")
    rso_rec = _acc(session, user.tenant_id, "1212")

    txn = post_transaction(
        session, user, date=date,
        description=f"Load transfer — RSO {rso.name} → Retail #{retail_outlet_id} ({amt})",
        entries=[
            EntryInput(account_id=retail_rec.id, debit=amt),
            EntryInput(account_id=rso_rec.id, credit=amt),
        ],
        audit_entity_type="load_transfer",
        audit_detail={"rso_id": rso.id, "retail_outlet_id": retail_outlet_id, "amount": str(amt)},
    )

    lt = LoadTransfer(
        tenant_id=user.tenant_id,
        transfer_date=date,
        from_type="rso",
        from_ref_id=rso.id,
        to_type="retail",
        to_ref_id=retail_outlet_id,
        amount=amt,
        transaction_id=txn.id,
    )
    session.add(lt); session.flush()
    return lt, txn


# ── 5.6 — RSO daily cash collection (settlement) ──────────────────────────


def post_rso_daily_collection(
    session: Session, user: User, *,
    rso: RsoAgent,
    load_portion: Decimal,
    stock_portion: Decimal,
    total_deposited: Decimal,
    date: str,
    bank_account_code: str = "1010",
) -> Tuple[RsoDailyCollection, Transaction]:
    """Dr 1010 Bank / Cr 1212 RSO Load Rec (load_portion) /
    Cr 1120 RSO Receivables (stock_portion). Any difference between
    total_deposited and (load_portion + stock_portion) posts to 5070 as
    variance (gain → 4900 Other Income; loss → 5070 expense)."""
    lp = money(D(load_portion))
    sp = money(D(stock_portion))
    td = money(D(total_deposited))
    if td <= ZERO:
        raise HTTPException(status_code=400, detail="Total deposited must be > 0")
    if lp < ZERO or sp < ZERO:
        raise HTTPException(status_code=400, detail="Portions cannot be negative")

    bank = _acc(session, user.tenant_id, bank_account_code)
    rso_load = _acc(session, user.tenant_id, "1212")
    rso_stock = _acc(session, user.tenant_id, "1120")

    entries = [EntryInput(account_id=bank.id, debit=td)]
    if lp > ZERO:
        entries.append(EntryInput(account_id=rso_load.id, credit=lp))
    if sp > ZERO:
        entries.append(EntryInput(account_id=rso_stock.id, credit=sp))

    variance = money(td - lp - sp)
    if variance != ZERO:
        variance_acc_code = "5070" if variance > ZERO else "4900"
        # variance > 0 means cash deposited exceeds documented portions —
        # treat as 'other income' (4900 credit) so debits/credits balance.
        # variance < 0 means short deposit — treat as variance expense (5070 debit).
        variance_acc = _acc(session, user.tenant_id, "4900" if variance > ZERO else "5070")
        if variance > ZERO:
            entries.append(EntryInput(account_id=variance_acc.id, credit=variance))
        else:
            entries.append(EntryInput(account_id=variance_acc.id, debit=-variance))

    txn = post_transaction(
        session, user, date=date,
        description=f"RSO daily collection — {rso.name} "
                    f"(load {lp} + stock {sp} = {lp + sp}; deposited {td})",
        entries=entries,
        audit_entity_type="rso_collection",
        audit_detail={
            "rso_id": rso.id,
            "load_portion": str(lp), "stock_portion": str(sp),
            "total_deposited": str(td), "variance": str(variance),
        },
    )

    collection = RsoDailyCollection(
        tenant_id=user.tenant_id,
        rso_id=rso.id,
        collection_date=date,
        load_portion=lp,
        stock_portion=sp,
        total_deposited=td,
        variance=variance,
        transaction_id=txn.id,
    )
    session.add(collection); session.flush()
    return collection, txn


# ── 5.7 — SIM sold at service counter ─────────────────────────────────────


def post_counter_sim_sale(
    session: Session, user: User, *,
    qty: int, sale_price: Decimal, unit_cost: Decimal,
    date: str, cash_account_code: str = "1000",
) -> Tuple[Transaction, Transaction]:
    """Two JVs: (sale) Dr Cash / Cr 4030 SIM Sale Revenue
              (COGS)  Dr 5011 COGS-SIMs / Cr 1200 SIM Inventory"""
    qty_d = D(qty)
    revenue = money(qty_d * D(sale_price))
    cogs = money(qty_d * D(unit_cost))
    cash = _acc(session, user.tenant_id, cash_account_code)
    revenue_acc = _acc(session, user.tenant_id, "4030")
    cogs_acc = _acc(session, user.tenant_id, "5011")
    inv = _acc(session, user.tenant_id, "1200")

    sale_txn = post_transaction(
        session, user, date=date,
        description=f"Counter SIM sale — qty {qty} @ {sale_price}",
        entries=[
            EntryInput(account_id=cash.id, debit=revenue),
            EntryInput(account_id=revenue_acc.id, credit=revenue),
        ],
        audit_entity_type="counter_sale",
        audit_detail={"qty": qty, "sale_price": str(sale_price)},
    )
    cogs_txn = post_transaction(
        session, user, date=date,
        description=f"Counter SIM COGS — qty {qty} @ cost {unit_cost}",
        entries=[
            EntryInput(account_id=cogs_acc.id, debit=cogs),
            EntryInput(account_id=inv.id, credit=cogs),
        ],
        audit_entity_type="counter_sale_cogs",
        audit_detail={"qty": qty, "unit_cost": str(unit_cost)},
    )
    return sale_txn, cogs_txn


# ── 5.8 — SIM issued to RSO for retail feeding ────────────────────────────


def post_rso_sim_issue(
    session: Session, user: User, *,
    rso: RsoAgent, batch: SimBatch,
    qty: int, retail_price: Decimal,
    date: str,
) -> Tuple[RsoStockIssue, Transaction]:
    """Dr 1120 RSO Receivables (face) / Cr 1200 SIM Inventory (cost) /
    Cr 4050 RSO Channel Revenue (margin at point of issue)."""
    qty_d = D(qty)
    face = money(qty_d * D(retail_price))
    cost = money(qty_d * D(batch.unit_cost))
    margin = money(face - cost)
    if face <= ZERO:
        raise HTTPException(status_code=400, detail="Face value must be > 0")

    rso_rec = _acc(session, user.tenant_id, "1120")
    inv = _acc(session, user.tenant_id, "1200")
    channel_rev = _acc(session, user.tenant_id, "4050")

    entries = [EntryInput(account_id=rso_rec.id, debit=face),
               EntryInput(account_id=inv.id, credit=cost)]
    if margin > ZERO:
        entries.append(EntryInput(account_id=channel_rev.id, credit=margin))

    txn = post_transaction(
        session, user, date=date,
        description=f"RSO SIM issue — {qty} SIMs to {rso.name} (face {face})",
        entries=entries,
        audit_entity_type="rso_stock_issue",
        audit_detail={"rso_id": rso.id, "batch_id": batch.id, "qty": qty},
    )

    issue = RsoStockIssue(
        tenant_id=user.tenant_id,
        rso_id=rso.id,
        issue_date=date,
        stock_type="sim_batch",
        stock_ref_id=batch.id,
        qty_issued=qty,
        face_value=face,
        cost_value=cost,
        transaction_id=txn.id,
    )
    session.add(issue); session.flush()
    return issue, txn


# ── 5.9 — FCA target commission (month-end) ───────────────────────────────


def post_fca_target_commission(
    session: Session, user: User, *,
    tracker_account: Optional[TrackerAccount],
    amount: Decimal, date: str,
    credit_to: str = "tracker",   # "tracker" | "bank"
    bank_account_code: str = "1010",
) -> Transaction:
    """Dr 1210 Tracker Deposit (or Bank) / Cr 4060 FCA Target Commission."""
    amt = money(D(amount))
    if amt <= ZERO:
        raise HTTPException(status_code=400, detail="Commission amount must be > 0")
    target = (
        _acc(session, user.tenant_id, "1210") if credit_to == "tracker"
        else _acc(session, user.tenant_id, bank_account_code)
    )
    commission = _acc(session, user.tenant_id, "4060")

    txn = post_transaction(
        session, user, date=date,
        description=f"FCA target commission ({amt}) credited to {credit_to}",
        entries=[
            EntryInput(account_id=target.id, debit=amt),
            EntryInput(account_id=commission.id, credit=amt),
        ],
        audit_entity_type="fca_commission",
        audit_detail={"amount": str(amt), "credit_to": credit_to},
    )

    if credit_to == "tracker" and tracker_account is not None:
        tracker_account.deposit_balance = money(D(tracker_account.deposit_balance) + amt)
        session.add(tracker_account)
    return txn


# ── 5.10 — FCA target missed (penalty) ────────────────────────────────────


def post_fca_target_penalty(
    session: Session, user: User, *,
    tracker_account: TrackerAccount,
    amount: Decimal, date: str,
) -> Transaction:
    """Dr 5090 Target Shortfall / Cr 1210 Tracker Deposit."""
    amt = money(D(amount))
    if amt <= ZERO:
        raise HTTPException(status_code=400, detail="Penalty amount must be > 0")
    if D(tracker_account.deposit_balance) < amt:
        raise HTTPException(
            status_code=400,
            detail=f"Tracker deposit ({tracker_account.deposit_balance}) cannot cover penalty {amt}",
        )

    penalty = _acc(session, user.tenant_id, "5090")
    deposit = _acc(session, user.tenant_id, "1210")
    txn = post_transaction(
        session, user, date=date,
        description=f"FCA target shortfall penalty ({amt})",
        entries=[
            EntryInput(account_id=penalty.id, debit=amt),
            EntryInput(account_id=deposit.id, credit=amt),
        ],
        audit_entity_type="fca_penalty",
        audit_detail={"amount": str(amt)},
    )
    tracker_account.deposit_balance = money(D(tracker_account.deposit_balance) - amt)
    session.add(tracker_account)
    return txn
