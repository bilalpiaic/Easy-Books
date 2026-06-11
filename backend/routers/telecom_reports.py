"""Telecom-franchise reports — mounted at /api/telecom/reports/*.

Each endpoint returns a small JSON payload suitable for direct rendering on
the telecom dashboard. Aggregations are kept simple (no Pandas) to stay in
the SQLite/Postgres common subset; production should add indices on
(tenant_id, date) for the high-traffic queries below.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import func
from sqlmodel import select

from models import Account, JournalEntry
from models_telecom import (
    CommissionLine, CommissionStatement, FcaEvent, KpiTarget, LoadTransfer,
    MobileMoneyAccount, PostpaidBillCycle, RsoAgent, RsoDailyCollection,
    RsoStockIssue, SimActivation, SimBatch, TrackerAccount, TrackerTransaction,
)
from services.money import D, ZERO

from .common import CurrentUserDep, SessionDep

router = APIRouter(tags=["telecom-reports"], prefix="/api/telecom/reports")


def _balance(session, tenant_id: int, code: str) -> Decimal:
    """Sum (debit - credit) for the given account code, tenant-scoped."""
    acc = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
    ).first()
    if acc is None:
        return ZERO
    tot = session.exec(
        select(
            func.coalesce(func.sum(JournalEntry.debit), 0),
            func.coalesce(func.sum(JournalEntry.credit), 0),
        ).where(JournalEntry.account_id == acc.id)
    ).one()
    return D(tot[0]) - D(tot[1])


@router.get("/dashboard")
def dashboard(session: SessionDep, user: CurrentUserDep):
    """Headline KPIs for the telecom-franchise dashboard."""
    tid = user.tenant_id

    # Tracker / load positions
    tracker_balance = _balance(session, tid, "1210")
    load_float = _balance(session, tid, "1211")
    rso_load_rec = _balance(session, tid, "1212")
    retail_load_rec = _balance(session, tid, "1213")
    commission_receivable = _balance(session, tid, "1110")
    rso_stock_rec = _balance(session, tid, "1120")
    mm_float_asset = _balance(session, tid, "1214")
    mm_float_liab = _balance(session, tid, "2100")
    sim_inventory_cost = _balance(session, tid, "1200")

    # FCA — current month
    month = date.today().isoformat()[:7]   # YYYY-MM
    fca_this_month = session.exec(
        select(func.count(FcaEvent.id)).where(
            FcaEvent.tenant_id == tid,
            FcaEvent.event_date.like(f"{month}-%"),
        )
    ).one()
    fca_target_row = session.exec(
        select(KpiTarget).where(
            KpiTarget.tenant_id == tid,
            KpiTarget.metric == "fca",
            KpiTarget.target_month.like(f"{month}-%"),
        ).order_by(KpiTarget.id.desc())
    ).first()

    # SIM batch utilisation
    batches = session.exec(select(SimBatch).where(SimBatch.tenant_id == tid)).all()
    total_received = sum((b.qty_received for b in batches), 0)
    total_activated = sum((b.qty_activated for b in batches), 0)

    # RSO count
    rso_count = session.exec(
        select(func.count(RsoAgent.id)).where(RsoAgent.tenant_id == tid)
    ).one()

    return {
        "as_of": date.today().isoformat(),
        "tracker": {
            "deposit_balance": str(tracker_balance),
            "load_float": str(load_float),
            "rso_load_receivable": str(rso_load_rec),
            "retail_load_receivable": str(retail_load_rec),
        },
        "commissions": {
            "receivable": str(commission_receivable),
        },
        "rso": {
            "agent_count": rso_count,
            "stock_receivable": str(rso_stock_rec),
        },
        "mobile_money": {
            "float_asset": str(mm_float_asset),
            "float_liability": str(mm_float_liab),
        },
        "sim": {
            "inventory_cost": str(sim_inventory_cost),
            "total_received": total_received,
            "total_activated": total_activated,
            "available": total_received - total_activated,
        },
        "fca": {
            "month": month,
            "actual": fca_this_month,
            "target": (str(fca_target_row.target_value) if fca_target_row else None),
            "achievement_pct": (
                str(round(D(fca_this_month) / D(fca_target_row.target_value) * 100, 2))
                if fca_target_row and D(fca_target_row.target_value) > 0 else None
            ),
        },
    }


@router.get("/commission-aging")
def commission_aging(session: SessionDep, user: CurrentUserDep):
    """Commission receivable by age bucket — current, 1-30, 31-60, 61-90, 90+."""
    today = date.today()
    buckets = {"current": ZERO, "1_30": ZERO, "31_60": ZERO, "61_90": ZERO, "90_plus": ZERO}
    activations = session.exec(
        select(SimActivation).where(
            SimActivation.tenant_id == user.tenant_id,
            SimActivation.commission_status == "accrued",
        )
    ).all()
    for act in activations:
        try:
            d = date.fromisoformat(act.activation_date)
            age = (today - d).days
        except ValueError:
            age = 0
        amt = D(act.commission_rate)
        if age <= 0:
            buckets["current"] += amt
        elif age <= 30:
            buckets["1_30"] += amt
        elif age <= 60:
            buckets["31_60"] += amt
        elif age <= 90:
            buckets["61_90"] += amt
        else:
            buckets["90_plus"] += amt
    return {k: str(v) for k, v in buckets.items()}


@router.get("/rso-ledger")
def rso_ledger(session: SessionDep, user: CurrentUserDep, rso_id: Optional[int] = None):
    """Per-RSO ledger: load issued, load settled, stock issued, cash collected."""
    tid = user.tenant_id
    rsos = session.exec(
        select(RsoAgent).where(
            RsoAgent.tenant_id == tid,
            *(RsoAgent.id == rso_id,) if rso_id else (),
        )
    ).all()

    rows = []
    for r in rsos:
        load_in = session.exec(
            select(func.coalesce(func.sum(LoadTransfer.amount), 0)).where(
                LoadTransfer.tenant_id == tid,
                LoadTransfer.to_type == "rso", LoadTransfer.to_ref_id == r.id,
            )
        ).one()
        load_out = session.exec(
            select(func.coalesce(func.sum(LoadTransfer.amount), 0)).where(
                LoadTransfer.tenant_id == tid,
                LoadTransfer.from_type == "rso", LoadTransfer.from_ref_id == r.id,
            )
        ).one()
        collected = session.exec(
            select(
                func.coalesce(func.sum(RsoDailyCollection.load_portion), 0),
                func.coalesce(func.sum(RsoDailyCollection.stock_portion), 0),
                func.coalesce(func.sum(RsoDailyCollection.total_deposited), 0),
            ).where(
                RsoDailyCollection.tenant_id == tid,
                RsoDailyCollection.rso_id == r.id,
            )
        ).one()
        rows.append({
            "rso_id": r.id, "name": r.name, "territory": r.territory,
            "load_in_msr": str(D(load_in)),
            "load_out_retail": str(D(load_out)),
            "cash_collected_load": str(D(collected[0])),
            "cash_collected_stock": str(D(collected[1])),
            "cash_collected_total": str(D(collected[2])),
            "open_load_balance": str(D(load_in) - D(load_out) - D(collected[0])),
        })
    return {"items": rows, "total": len(rows)}


@router.get("/stock-issuance")
def stock_issuance(
    session: SessionDep, user: CurrentUserDep,
    start: Optional[str] = None, end: Optional[str] = None,
):
    """Per-RSO stock & issuance report (#42). One row per RSO agent; FCA is
    franchise-level (tc_fca_event has no rso_id) so it appears only in totals.
    Covers the MSR->channel->bank segment of the franchise load/stock chain."""
    tid = user.tenant_id

    def _between(col):
        conds = []
        if start:
            conds.append(col >= start)
        if end:
            conds.append(col <= end)
        return conds

    def _sum(model, value_col, *extra):
        return session.exec(
            select(func.coalesce(func.sum(value_col), 0)).where(
                model.tenant_id == tid, *extra,
            )
        ).one()

    rsos = session.exec(select(RsoAgent).where(RsoAgent.tenant_id == tid)).all()

    items = []
    tot_stock = tot_load = tot_hlr = tot_other = tot_dep = ZERO
    tot_sim = 0
    for r in rsos:
        sim_types = RsoStockIssue.stock_type.in_(("sim_batch", "imsi"))
        stock = _sum(RsoStockIssue, RsoStockIssue.face_value,
                     RsoStockIssue.rso_id == r.id,
                     RsoStockIssue.stock_type == "scratch_card",
                     *_between(RsoStockIssue.issue_date))
        load = _sum(LoadTransfer, LoadTransfer.amount,
                    LoadTransfer.to_type == "rso", LoadTransfer.to_ref_id == r.id,
                    *_between(LoadTransfer.transfer_date))
        hlr = _sum(RsoStockIssue, RsoStockIssue.face_value,
                   RsoStockIssue.rso_id == r.id, sim_types,
                   *_between(RsoStockIssue.issue_date))
        sim_qty = _sum(RsoStockIssue, RsoStockIssue.qty_issued,
                       RsoStockIssue.rso_id == r.id, sim_types,
                       *_between(RsoStockIssue.issue_date))
        other = _sum(RsoStockIssue, RsoStockIssue.face_value,
                     RsoStockIssue.rso_id == r.id,
                     RsoStockIssue.stock_type == "bundle",
                     *_between(RsoStockIssue.issue_date))
        dep = _sum(RsoDailyCollection, RsoDailyCollection.total_deposited,
                   RsoDailyCollection.rso_id == r.id,
                   *_between(RsoDailyCollection.collection_date))

        stock_d, load_d, hlr_d, other_d, dep_d = D(stock), D(load), D(hlr), D(other), D(dep)
        sim_i = int(sim_qty)
        items.append({
            "rso_id": r.id, "name": r.name, "territory": r.territory,
            "stock_issuance": str(stock_d), "load_issued": str(load_d),
            "hlr_issued": str(hlr_d), "sim_issued_qty": sim_i,
            "other_stock": str(other_d), "bank_deposits": str(dep_d),
            "closing_hlr_load_dep": str(hlr_d + load_d - dep_d),
            "fca_hits": None, "closing_sim_fca": None,
        })
        tot_stock += stock_d; tot_load += load_d; tot_hlr += hlr_d
        tot_other += other_d; tot_dep += dep_d; tot_sim += sim_i

    fca_count = session.exec(
        select(func.coalesce(func.count(FcaEvent.id), 0)).where(
            FcaEvent.tenant_id == tid, *_between(FcaEvent.event_date),
        )
    ).one()
    fca = int(fca_count)

    totals = {
        "stock_issuance": str(tot_stock), "load_issued": str(tot_load),
        "hlr_issued": str(tot_hlr), "sim_issued_qty": tot_sim,
        "other_stock": str(tot_other), "bank_deposits": str(tot_dep),
        "closing_hlr_load_dep": str(tot_hlr + tot_load - tot_dep),
        "fca_hits": fca, "closing_sim_fca": tot_sim - fca,
    }
    return {"items": items, "totals": totals, "period": {"start": start, "end": end}}


@router.get("/float-statement")
def float_statement(session: SessionDep, user: CurrentUserDep):
    """MM accounts with system balance + GL balance for reconciliation."""
    tid = user.tenant_id
    accounts = session.exec(
        select(MobileMoneyAccount).where(MobileMoneyAccount.tenant_id == tid)
    ).all()
    gl_float = _balance(session, tid, "1214")
    rows = [
        {
            "id": a.id, "account_number": a.account_number,
            "account_type": a.account_type,
            "system_balance": str(D(a.current_float_balance)),
        }
        for a in accounts
    ]
    return {
        "gl_balance_1214": str(gl_float),
        "system_balance_total": str(sum((D(a["system_balance"]) for a in rows), ZERO)),
        "items": rows,
    }


@router.get("/sim-utilisation")
def sim_utilisation(session: SessionDep, user: CurrentUserDep):
    """Per-batch SIM utilisation."""
    batches = session.exec(
        select(SimBatch).where(SimBatch.tenant_id == user.tenant_id)
        .order_by(SimBatch.received_date.desc())
    ).all()
    rows = [
        {
            "id": b.id, "batch_number": b.batch_number,
            "qty_received": b.qty_received, "qty_activated": b.qty_activated,
            "qty_available": b.qty_received - b.qty_activated,
            "unit_cost": str(D(b.unit_cost)),
            "received_date": b.received_date,
        }
        for b in batches
    ]
    return {"items": rows, "total": len(rows)}


@router.get("/postpaid-book")
def postpaid_book(session: SessionDep, user: CurrentUserDep):
    """All postpaid cycles with collection + remittance status."""
    items = session.exec(
        select(PostpaidBillCycle).where(PostpaidBillCycle.tenant_id == user.tenant_id)
        .order_by(PostpaidBillCycle.billing_month.desc())
    ).all()
    return {"items": items, "total": len(items)}


@router.get("/revenue-by-stream")
def revenue_by_stream(session: SessionDep, user: CurrentUserDep):
    """Aggregate revenue per franchise stream (CoA 4xxx)."""
    streams = [
        ("4000", "Airtime / Recharge"),
        ("4010", "SIM Activation"),
        ("4020", "Load Uplift Commission"),
        ("4021", "Recharge Commission"),
        ("4022", "Mobile Money Commission"),
        ("4023", "Bundle Commission"),
        ("4030", "SIM Sale"),
        ("4031", "Device Sales"),
        ("4040", "Postpaid Billing"),
        ("4050", "RSO Channel"),
        ("4060", "FCA Target Commission"),
        ("4061", "Franchise Incentive"),
    ]
    rows = []
    total = ZERO
    for code, name in streams:
        b = _balance(session, user.tenant_id, code)
        # Revenue accounts have credit balance — flip sign for reader-friendly +.
        amt = -b
        rows.append({"code": code, "name": name, "amount": str(amt)})
        total += amt
    return {"items": rows, "total_revenue": str(total)}


@router.get("/fca-target")
def fca_target_progress(
    session: SessionDep, user: CurrentUserDep, month: Optional[str] = None,
):
    """Current-month FCA actual vs target progress."""
    m = month or date.today().isoformat()[:7]
    target_row = session.exec(
        select(KpiTarget).where(
            KpiTarget.tenant_id == user.tenant_id,
            KpiTarget.metric == "fca",
            KpiTarget.target_month.like(f"{m}-%"),
        ).order_by(KpiTarget.id.desc())
    ).first()
    actual = session.exec(
        select(func.count(FcaEvent.id)).where(
            FcaEvent.tenant_id == user.tenant_id,
            FcaEvent.event_date.like(f"{m}-%"),
        )
    ).one()
    target = D(target_row.target_value) if target_row else ZERO
    return {
        "month": m,
        "target": str(target),
        "actual": actual,
        "achievement_pct": (str(round(D(actual) / target * 100, 2)) if target > 0 else None),
        "delta": str(D(actual) - target),
    }


@router.get("/tracker-statement")
def tracker_statement(
    session: SessionDep, user: CurrentUserDep,
    tracker_account_id: Optional[int] = None,
):
    """Tracker txn ledger with running balance reconciliation."""
    q = select(TrackerTransaction).where(TrackerTransaction.tenant_id == user.tenant_id)
    if tracker_account_id:
        q = q.where(TrackerTransaction.tracker_account_id == tracker_account_id)
    items = session.exec(q.order_by(TrackerTransaction.txn_date, TrackerTransaction.id)).all()
    accounts = session.exec(
        select(TrackerAccount).where(
            TrackerAccount.tenant_id == user.tenant_id,
            *((TrackerAccount.id == tracker_account_id,) if tracker_account_id else ()),
        )
    ).all()
    return {
        "tracker_accounts": [
            {"id": a.id, "account_number": a.account_number,
             "deposit_balance": str(D(a.deposit_balance)),
             "load_balance": str(D(a.load_balance))}
            for a in accounts
        ],
        "transactions": items,
        "gl_deposit_balance": str(_balance(session, user.tenant_id, "1210")),
        "gl_load_balance": str(_balance(session, user.tenant_id, "1211")),
    }
