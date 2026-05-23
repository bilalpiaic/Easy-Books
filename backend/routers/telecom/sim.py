"""SIM stock management, counter sales, RSO SIM issues, FCA events,
and monthly KPI target management.

GL flows:
  Counter sale:    Dr 1000 Cash / Cr 4030 SIM Sale Revenue
                   Dr 5011 COGS—SIMs / Cr 1200 SIM Card Inventory
  RSO SIM issue:   Dr 1120 RSO Receivables (face) / Cr 1200 (cost) / Cr 4050 RSO Channel Revenue (margin)
  FCA event:       No GL — only increments KPITarget.actual_fca_count
  KPI close:       Commission → Dr 1210/Bank / Cr 4060
                   Penalty    → Dr 5090 / Cr 1210
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    Account, FCAEvent, KPITarget, RSOAgent,
    SimActivation, SimBatch, TrackerAccount, TrackerTransaction,
)
from services.money import D, ZERO
from services.posting import EntryInput, post_transaction

from ..common import (
    CurrentUserDep, SessionDep, WriteUserDep,
    get_or_create_account, log_audit, next_number,
)

router = APIRouter(prefix="/api/telecom", tags=["telecom"])


def _get_batch(session, tenant_id: int, batch_id: int) -> SimBatch:
    b = session.get(SimBatch, batch_id)
    if not b or b.tenant_id != tenant_id:
        raise HTTPException(404, "SIM batch not found")
    return b


def _get_kpi(session, tenant_id: int, kpi_id: int) -> KPITarget:
    k = session.get(KPITarget, kpi_id)
    if not k or k.tenant_id != tenant_id:
        raise HTTPException(404, "KPI target not found")
    return k


# ── SIM Batches ───────────────────────────────────────────────────────────────

class SimBatchCreate(BaseModel):
    operator_name: str
    batch_reference: str
    series_from: Optional[str] = None
    series_to: Optional[str] = None
    qty_received: int
    unit_cost: Decimal
    received_date: str
    tracker_txn_id: Optional[int] = None   # link to existing stock_debit TrackerTransaction
    notes: Optional[str] = None


@router.get("/sim-batches")
def list_sim_batches(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(SimBatch).where(SimBatch.tenant_id == user.tenant_id)
        .order_by(SimBatch.received_date.desc())
    ).all()
    return {"items": [
        {
            **r.model_dump(),
            "qty_available": r.qty_received - r.qty_activated - r.qty_issued_rso,
        }
        for r in rows
    ]}


@router.post("/sim-batches", status_code=201)
def create_sim_batch(body: SimBatchCreate, session: SessionDep, user: WriteUserDep):
    batch = SimBatch(
        tenant_id=user.tenant_id,
        operator_name=body.operator_name,
        batch_reference=body.batch_reference,
        series_from=body.series_from,
        series_to=body.series_to,
        qty_received=body.qty_received,
        unit_cost=D(body.unit_cost),
        received_date=body.received_date,
        tracker_txn_id=body.tracker_txn_id,
        notes=body.notes,
    )
    session.add(batch)
    session.flush()
    log_audit(session, user, "CREATE", "sim_batch", batch.id,
              {"batch_reference": body.batch_reference, "qty": body.qty_received})
    session.commit()
    session.refresh(batch)
    return {**batch.model_dump(),
            "qty_available": batch.qty_received - batch.qty_activated - batch.qty_issued_rso}


@router.get("/sim-batches/{batch_id}")
def get_sim_batch(batch_id: int, session: SessionDep, user: CurrentUserDep):
    batch = _get_batch(session, user.tenant_id, batch_id)
    activations = session.exec(
        select(SimActivation).where(
            SimActivation.tenant_id == user.tenant_id,
            SimActivation.sim_batch_id == batch_id,
        )
    ).all()
    return {
        **batch.model_dump(),
        "qty_available": batch.qty_received - batch.qty_activated - batch.qty_issued_rso,
        "activations": [a.model_dump() for a in activations],
    }


# ── Counter SIM Sales ─────────────────────────────────────────────────────────

class CounterSaleCreate(BaseModel):
    sim_batch_id: int
    activation_date: str
    sim_number: Optional[str] = None
    customer_name: Optional[str] = None
    customer_cnic: Optional[str] = None
    sale_price: Decimal
    cash_account_code: str = "1000"   # Cash in Hand


@router.post("/sim-sales", status_code=201)
def create_counter_sale(body: CounterSaleCreate, session: SessionDep, user: WriteUserDep):
    """Sell one SIM at the service counter.

    JV #1 — Sale:  Dr Cash / Cr 4030 SIM Sale Revenue
    JV #2 — COGS:  Dr 5011 COGS-SIMs / Cr 1200 SIM Card Inventory (at unit_cost)
    """
    batch = _get_batch(session, user.tenant_id, body.sim_batch_id)
    available = batch.qty_received - batch.qty_activated - batch.qty_issued_rso
    if available < 1:
        raise HTTPException(400, "No SIMs available in this batch")

    price     = D(body.sale_price)
    unit_cost = D(batch.unit_cost)

    cash_acc     = get_or_create_account(session, user.tenant_id, body.cash_account_code,
                                         "Cash in Hand", "Asset")
    revenue_acc  = get_or_create_account(session, user.tenant_id, "4030",
                                         "SIM Sale Revenue", "Revenue")
    cogs_acc     = get_or_create_account(session, user.tenant_id, "5011",
                                         "COGS — SIMs", "Expense")
    inventory_acc = get_or_create_account(session, user.tenant_id, "1200",
                                          "SIM Card Inventory", "Asset")

    ref = next_number(session, user.tenant_id, "sim_sale", "SIM")

    # JV #1 — revenue
    txn_sale = post_transaction(
        session, user,
        date=body.activation_date,
        description=f"Counter SIM sale {ref}",
        reference=ref,
        entries=[
            EntryInput(account_id=cash_acc.id,    debit=price),
            EntryInput(account_id=revenue_acc.id, credit=price),
        ],
        audit_entity_type="sim_activation",
    )

    # JV #2 — COGS (only if we have a cost)
    if unit_cost > ZERO:
        post_transaction(
            session, user,
            date=body.activation_date,
            description=f"COGS – SIM {ref}",
            reference=ref + "-C",
            entries=[
                EntryInput(account_id=cogs_acc.id,      debit=unit_cost),
                EntryInput(account_id=inventory_acc.id, credit=unit_cost),
            ],
            audit_entity_type="sim_activation",
        )

    activation = SimActivation(
        tenant_id=user.tenant_id,
        sim_batch_id=body.sim_batch_id,
        sim_number=body.sim_number,
        activation_date=body.activation_date,
        customer_name=body.customer_name,
        customer_cnic=body.customer_cnic,
        activation_type="counter_sale",
        sale_price=price,
        status="active",
        transaction_id=txn_sale.id,
    )
    session.add(activation)

    batch.qty_activated += 1
    session.add(batch)

    session.commit()
    session.refresh(activation)
    return {"activation": activation.model_dump(), "jv_number": txn_sale.jv_number}


# ── RSO SIM Issue ─────────────────────────────────────────────────────────────

class RSOSimIssueCreate(BaseModel):
    sim_batch_id: int
    rso_id: int
    issue_date: str
    qty: int
    face_price_per_sim: Decimal   # selling price to RSO channel


@router.post("/sim-issues", status_code=201)
def create_rso_sim_issue(body: RSOSimIssueCreate, session: SessionDep, user: WriteUserDep):
    """Issue SIMs to RSO channel.

    Dr 1120 RSO Receivables (face_value) / Cr 1200 SIM Inventory (cost) / Cr 4050 RSO Channel Revenue (margin)
    """
    batch = _get_batch(session, user.tenant_id, body.sim_batch_id)
    available = batch.qty_received - batch.qty_activated - batch.qty_issued_rso
    if available < body.qty:
        raise HTTPException(400, f"Only {available} SIMs available, requested {body.qty}")

    rso = session.get(RSOAgent, body.rso_id)
    if not rso or rso.tenant_id != user.tenant_id:
        raise HTTPException(404, "RSO agent not found")

    qty        = body.qty
    face_value = D(body.face_price_per_sim) * qty
    cost_value = D(batch.unit_cost) * qty
    margin     = face_value - cost_value

    rso_recv     = get_or_create_account(session, user.tenant_id, "1120",
                                         "RSO Receivables", "Asset")
    inventory_acc = get_or_create_account(session, user.tenant_id, "1200",
                                          "SIM Card Inventory", "Asset")
    rso_rev_acc  = get_or_create_account(session, user.tenant_id, "4050",
                                         "RSO Channel Revenue", "Revenue")

    entries = [
        EntryInput(account_id=rso_recv.id,     debit=face_value),
        EntryInput(account_id=inventory_acc.id, credit=cost_value),
    ]
    if margin > ZERO:
        entries.append(EntryInput(account_id=rso_rev_acc.id, credit=margin))
    elif margin < ZERO:
        # Negative margin shouldn't happen but keep the JV balanced
        entries.append(EntryInput(account_id=rso_rev_acc.id, debit=abs(margin)))

    ref = next_number(session, user.tenant_id, "sim_sale", "SI")
    txn = post_transaction(
        session, user,
        date=body.issue_date,
        description=f"SIM issue to RSO #{body.rso_id} – {qty} SIMs",
        reference=ref,
        entries=entries,
        audit_entity_type="sim_activation",
    )

    # Create activation records for each SIM (no customer info at issue time)
    for _ in range(qty):
        session.add(SimActivation(
            tenant_id=user.tenant_id,
            sim_batch_id=body.sim_batch_id,
            activation_date=body.issue_date,
            activation_type="rso_issue",
            rso_id=body.rso_id,
            sale_price=D(body.face_price_per_sim),
            status="pending",
            transaction_id=txn.id,
        ))

    batch.qty_issued_rso += qty
    session.add(batch)

    session.commit()
    return {
        "qty_issued": qty,
        "face_value": str(face_value),
        "cost_value": str(cost_value),
        "margin": str(margin),
        "jv_number": txn.jv_number,
    }


# ── FCA Events ────────────────────────────────────────────────────────────────

class FCAEventCreate(BaseModel):
    kpi_target_id: int
    event_date: str
    sim_number: Optional[str] = None
    source_channel: str = "rso_retail"  # counter | rso_retail | direct
    notes: Optional[str] = None


@router.get("/fca-events")
def list_fca_events(
    session: SessionDep,
    user: CurrentUserDep,
    kpi_target_id: Optional[int] = None,
):
    q = select(FCAEvent).where(FCAEvent.tenant_id == user.tenant_id)
    if kpi_target_id:
        q = q.where(FCAEvent.kpi_target_id == kpi_target_id)
    rows = session.exec(q.order_by(FCAEvent.event_date.desc())).all()
    return {"items": [r.model_dump() for r in rows]}


@router.post("/fca-events", status_code=201)
def create_fca_event(body: FCAEventCreate, session: SessionDep, user: WriteUserDep):
    """Record an FCA event. No GL posting — only increments the KPI counter."""
    kpi = _get_kpi(session, user.tenant_id, body.kpi_target_id)
    if kpi.status == "closed":
        raise HTTPException(400, "Cannot add FCA events to a closed KPI target")

    event = FCAEvent(
        tenant_id=user.tenant_id,
        kpi_target_id=body.kpi_target_id,
        event_date=body.event_date,
        sim_number=body.sim_number,
        source_channel=body.source_channel,
        notes=body.notes,
    )
    session.add(event)

    kpi.actual_fca_count += 1
    session.add(kpi)

    session.commit()
    session.refresh(event)
    return event


# ── KPI Targets ───────────────────────────────────────────────────────────────

class KPITargetCreate(BaseModel):
    tracker_account_id: int
    target_month: str        # YYYY-MM-01
    target_fca_count: int


class KPICloseIn(BaseModel):
    txn_date: str
    incentive_earned: Decimal = ZERO
    penalty_applied: Decimal = ZERO
    credit_method: str = "tracker"   # "tracker" or "bank"
    notes: Optional[str] = None


@router.get("/kpi-targets")
def list_kpi_targets(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(KPITarget).where(KPITarget.tenant_id == user.tenant_id)
        .order_by(KPITarget.target_month.desc())
    ).all()
    return {"items": [r.model_dump() for r in rows]}


@router.post("/kpi-targets", status_code=201)
def create_kpi_target(body: KPITargetCreate, session: SessionDep, user: WriteUserDep):
    ta = session.get(TrackerAccount, body.tracker_account_id)
    if not ta or ta.tenant_id != user.tenant_id:
        raise HTTPException(404, "Tracker account not found")

    kpi = KPITarget(
        tenant_id=user.tenant_id,
        tracker_account_id=body.tracker_account_id,
        target_month=body.target_month,
        target_fca_count=body.target_fca_count,
    )
    session.add(kpi)
    session.flush()
    log_audit(session, user, "CREATE", "kpi_target", kpi.id,
              {"month": body.target_month, "target": body.target_fca_count})
    session.commit()
    session.refresh(kpi)
    return kpi


@router.post("/kpi-targets/{kpi_id}/close", status_code=200)
def close_kpi_target(kpi_id: int, body: KPICloseIn, session: SessionDep, user: WriteUserDep):
    """Month-end close: post commission or penalty JV, mark KPI as closed."""
    kpi = _get_kpi(session, user.tenant_id, kpi_id)
    if kpi.status == "closed":
        raise HTTPException(400, "KPI target is already closed")

    incentive = D(body.incentive_earned)
    penalty   = D(body.penalty_applied)

    if incentive > ZERO and penalty > ZERO:
        raise HTTPException(400, "Specify either incentive_earned or penalty_applied, not both")

    txn = None

    if incentive > ZERO:
        deposit_acc = get_or_create_account(session, user.tenant_id, "1210",
                                            "Tracker Deposit Balance", "Asset")
        bank_acc    = get_or_create_account(session, user.tenant_id, "1010", "Bank", "Asset")
        comm_rev    = get_or_create_account(session, user.tenant_id, "4060",
                                            "FCA Target Commission", "Revenue")
        debit_acc = bank_acc if body.credit_method == "bank" else deposit_acc
        txn = post_transaction(
            session, user,
            date=body.txn_date,
            description=f"FCA commission – KPI #{kpi_id} ({kpi.target_month})",
            entries=[
                EntryInput(account_id=debit_acc.id, debit=incentive),
                EntryInput(account_id=comm_rev.id,  credit=incentive),
            ],
            audit_entity_type="kpi_target",
        )
        kpi.incentive_earned = incentive

    elif penalty > ZERO:
        penalty_exp = get_or_create_account(session, user.tenant_id, "5090",
                                            "Target Shortfall Penalties", "Expense")
        deposit_acc = get_or_create_account(session, user.tenant_id, "1210",
                                            "Tracker Deposit Balance", "Asset")
        txn = post_transaction(
            session, user,
            date=body.txn_date,
            description=f"FCA penalty – KPI #{kpi_id} ({kpi.target_month})",
            entries=[
                EntryInput(account_id=penalty_exp.id, debit=penalty),
                EntryInput(account_id=deposit_acc.id, credit=penalty),
            ],
            audit_entity_type="kpi_target",
        )
        kpi.penalty_applied = penalty

    kpi.status = "closed"
    kpi.notes  = body.notes
    if txn:
        kpi.commission_txn_id = txn.id
    session.add(kpi)

    log_audit(session, user, "CLOSE", "kpi_target", kpi_id,
              {"incentive": str(incentive), "penalty": str(penalty)})
    session.commit()
    session.refresh(kpi)
    return {
        "kpi_target": kpi.model_dump(),
        "jv_number": txn.jv_number if txn else None,
    }


# ── Telecom Dashboard ─────────────────────────────────────────────────────────

@router.get("/dashboard")
def telecom_dashboard(session: SessionDep, user: CurrentUserDep):
    """Aggregate KPIs for the telecom franchise dashboard."""
    from sqlmodel import func

    def _acc_balance(code: str) -> Decimal:
        acc = session.exec(
            select(Account).where(
                Account.tenant_id == user.tenant_id,
                Account.code == code,
            )
        ).first()
        if not acc:
            return ZERO
        from models import JournalEntry
        entries = session.exec(
            select(JournalEntry).where(
                JournalEntry.account_id == acc.id,
                JournalEntry.tenant_id == user.tenant_id,
            )
        ).all()
        if acc.type in ("Asset", "Expense"):
            return sum((D(e.debit) - D(e.credit) for e in entries), ZERO)
        return sum((D(e.credit) - D(e.debit) for e in entries), ZERO)

    # Latest open KPI target
    open_kpi = session.exec(
        select(KPITarget).where(
            KPITarget.tenant_id == user.tenant_id,
            KPITarget.status == "open",
        ).order_by(KPITarget.target_month.desc())
    ).first()

    return {
        "tracker_deposit_balance": str(_acc_balance("1210")),
        "load_float_balance":      str(_acc_balance("1211")),
        "rso_load_outstanding":    str(_acc_balance("1212")),
        "retail_load_outstanding": str(_acc_balance("1213")),
        "rso_stock_receivable":    str(_acc_balance("1120")),
        "commission_receivable":   str(_acc_balance("1110")),
        "current_kpi": open_kpi.model_dump() if open_kpi else None,
    }
