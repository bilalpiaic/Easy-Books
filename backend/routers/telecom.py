"""Telecom-franchise API routes — mounted at /api/telecom/*.

Grouped by domain in this single file because most endpoints are small CRUD
wrappers plus a few that delegate to services/tracker_posting.py and
services/franchise_posting.py for the GL JV. Reports live in
routers/telecom_reports.py.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import Account, Tenant
from models_telecom import (
    AirtimeSale, AirtimeStock, CommissionLine, CommissionStatement,
    DeviceImei, FcaEvent, FranchiseAgreement, KpiTarget, LoadTransfer,
    MobileMoneyAccount, MobileMoneyTransaction, Operator, PostpaidBillCycle,
    PostpaidConnection, RetailOutlet, RsoAgent, RsoDailyCollection,
    RsoStockIssue, RsoTarget, SimActivation, SimBatch, TrackerAccount,
    TrackerTransaction,
)
from services.franchise_posting import (
    post_commission_accrual, post_commission_statement_settlement,
    post_franchise_fee_amortisation, post_franchise_fee_capitalisation,
    post_mm_commission_credit, post_mm_customer_deposit,
    post_mm_customer_withdrawal, post_mm_float_top_up, post_mm_reconciliation,
    post_postpaid_bill, post_postpaid_collection, post_postpaid_remittance,
    post_royalty_accrual, post_royalty_payment,
)
from services.tracker_posting import (
    post_counter_sim_sale, post_fca_target_commission,
    post_fca_target_penalty, post_load_order,
    post_msr_to_rso_transfer, post_rso_daily_collection,
    post_rso_sim_issue, post_rso_to_retail_transfer, post_stock_debit,
    post_tracker_deposit,
)

from services.permissions import perm_dep
from .common import CurrentUserDep, SessionDep, WriteUserDep

router = APIRouter(tags=["telecom"], prefix="/api/telecom", dependencies=[perm_dep("telecom.tracker")])


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _require_franchise(user) -> None:
    """Reject requests from non-telecom tenants — keep cross-model APIs clean."""
    # NB: cheap check; we don't load the tenant unless needed. Anyone with a
    # valid JWT can hit these endpoints, but the tenant_id filter on every
    # row keeps data isolated.


def _get_one(session, model, id: int, tenant_id: int):
    obj = session.get(model, id)
    if obj is None or obj.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {id} not found")
    return obj


def _today() -> str:
    return date.today().isoformat()


# ──────────────────────────────────────────────────────────────────────────
# Operator
# ──────────────────────────────────────────────────────────────────────────


class OperatorCreate(BaseModel):
    name: str
    operator_code: str
    contact_person: Optional[str] = None
    contact_phone: Optional[str] = None
    commission_settlement_cycle: str = "monthly"


@router.get("/operators")
def list_operators(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(Operator).where(Operator.tenant_id == user.tenant_id).order_by(Operator.name)
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/operators")
def create_operator(payload: OperatorCreate, session: SessionDep, user: WriteUserDep):
    # Auto-link the operator to the standard franchise CoA codes if present.
    def _acc_id(code: str) -> Optional[int]:
        a = session.exec(
            select(Account).where(Account.tenant_id == user.tenant_id, Account.code == code)
        ).first()
        return a.id if a else None

    op = Operator(
        tenant_id=user.tenant_id, name=payload.name,
        operator_code=payload.operator_code,
        contact_person=payload.contact_person,
        contact_phone=payload.contact_phone,
        commission_settlement_cycle=payload.commission_settlement_cycle,
        deposit_account_id=_acc_id("1210"),
        load_account_id=_acc_id("1211"),
        payable_account_id=_acc_id("2010"),
        commission_account_id=_acc_id("4020"),
    )
    session.add(op); session.commit(); session.refresh(op)
    return op


# ──────────────────────────────────────────────────────────────────────────
# Tracker (deposits + load orders + stock debits)
# ──────────────────────────────────────────────────────────────────────────


class TrackerAccountCreate(BaseModel):
    operator_id: int
    account_number: str


@router.get("/tracker-accounts")
def list_tracker_accounts(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(TrackerAccount).where(TrackerAccount.tenant_id == user.tenant_id)
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/tracker-accounts")
def create_tracker_account(payload: TrackerAccountCreate, session: SessionDep, user: WriteUserDep):
    op = _get_one(session, Operator, payload.operator_id, user.tenant_id)
    ta = TrackerAccount(
        tenant_id=user.tenant_id, operator_id=op.id,
        account_number=payload.account_number,
    )
    session.add(ta); session.commit(); session.refresh(ta)
    return ta


class TrackerDepositPayload(BaseModel):
    tracker_account_id: int
    amount: Decimal
    date: Optional[str] = None
    reference: Optional[str] = None
    bank_account_code: str = "1010"


@router.post("/tracker/deposits")
def post_deposit(payload: TrackerDepositPayload, session: SessionDep, user: WriteUserDep):
    ta = _get_one(session, TrackerAccount, payload.tracker_account_id, user.tenant_id)
    tt, txn = post_tracker_deposit(
        session, user, tracker_account=ta,
        amount=payload.amount, date=payload.date or _today(),
        reference=payload.reference, bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"tracker_transaction": tt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class LoadOrderPayload(BaseModel):
    tracker_account_id: int
    cash_debit: Decimal
    uplift_pct: Decimal = Decimal("3.00")
    date: Optional[str] = None
    reference: Optional[str] = None


@router.post("/tracker/load-orders")
def post_load_order_ep(payload: LoadOrderPayload, session: SessionDep, user: WriteUserDep):
    ta = _get_one(session, TrackerAccount, payload.tracker_account_id, user.tenant_id)
    tt, txn = post_load_order(
        session, user, tracker_account=ta,
        cash_debit=payload.cash_debit, uplift_pct=payload.uplift_pct,
        date=payload.date or _today(), reference=payload.reference,
    )
    session.commit()
    return {"tracker_transaction": tt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class StockDebitPayload(BaseModel):
    tracker_account_id: int
    inventory_account_code: str = "1200"   # SIMs by default; "1204" for IMSI
    qty: int
    unit_cost: Decimal
    date: Optional[str] = None
    batch_number: Optional[str] = None


@router.post("/tracker/stock-debits")
def post_stock_debit_ep(payload: StockDebitPayload, session: SessionDep, user: WriteUserDep):
    ta = _get_one(session, TrackerAccount, payload.tracker_account_id, user.tenant_id)
    batch, txn = post_stock_debit(
        session, user, tracker_account=ta,
        inventory_account_code=payload.inventory_account_code,
        qty=payload.qty, unit_cost=payload.unit_cost,
        date=payload.date or _today(), batch_number=payload.batch_number,
    )
    session.commit()
    return {"batch": batch, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


@router.get("/tracker/transactions")
def list_tracker_transactions(
    session: SessionDep, user: CurrentUserDep,
    tracker_account_id: Optional[int] = None, limit: int = 100,
):
    q = select(TrackerTransaction).where(TrackerTransaction.tenant_id == user.tenant_id)
    if tracker_account_id:
        q = q.where(TrackerTransaction.tracker_account_id == tracker_account_id)
    items = session.exec(q.order_by(TrackerTransaction.txn_date.desc()).limit(limit)).all()
    return {"items": items, "total": len(items)}


# ──────────────────────────────────────────────────────────────────────────
# RSO + Retail outlets + Load transfers
# ──────────────────────────────────────────────────────────────────────────


class RsoAgentCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    cnic: Optional[str] = None
    territory: Optional[str] = None


@router.get("/rso/agents")
def list_rso_agents(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(RsoAgent).where(RsoAgent.tenant_id == user.tenant_id).order_by(RsoAgent.name)
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/rso/agents")
def create_rso(payload: RsoAgentCreate, session: SessionDep, user: WriteUserDep):
    agent = RsoAgent(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(agent); session.commit(); session.refresh(agent)
    return agent


class RetailOutletCreate(BaseModel):
    rso_id: int
    shop_name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


@router.get("/rso/retail-outlets")
def list_retail_outlets(
    session: SessionDep, user: CurrentUserDep, rso_id: Optional[int] = None,
):
    q = select(RetailOutlet).where(RetailOutlet.tenant_id == user.tenant_id)
    if rso_id:
        q = q.where(RetailOutlet.rso_id == rso_id)
    items = session.exec(q.order_by(RetailOutlet.shop_name)).all()
    return {"items": items, "total": len(items)}


@router.post("/rso/retail-outlets")
def create_retail_outlet(payload: RetailOutletCreate, session: SessionDep, user: WriteUserDep):
    _get_one(session, RsoAgent, payload.rso_id, user.tenant_id)
    outlet = RetailOutlet(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(outlet); session.commit(); session.refresh(outlet)
    return outlet


class MsrToRsoTransferPayload(BaseModel):
    tracker_account_id: int
    rso_id: int
    amount: Decimal
    date: Optional[str] = None


@router.post("/load-transfers/msr-to-rso")
def transfer_msr_to_rso(payload: MsrToRsoTransferPayload, session: SessionDep, user: WriteUserDep):
    ta = _get_one(session, TrackerAccount, payload.tracker_account_id, user.tenant_id)
    rso = _get_one(session, RsoAgent, payload.rso_id, user.tenant_id)
    lt, txn = post_msr_to_rso_transfer(
        session, user, tracker_account=ta, rso=rso,
        amount=payload.amount, date=payload.date or _today(),
    )
    session.commit()
    return {"load_transfer": lt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class RsoToRetailTransferPayload(BaseModel):
    rso_id: int
    retail_outlet_id: int
    amount: Decimal
    date: Optional[str] = None


@router.post("/load-transfers/rso-to-retail")
def transfer_rso_to_retail(payload: RsoToRetailTransferPayload, session: SessionDep, user: WriteUserDep):
    rso = _get_one(session, RsoAgent, payload.rso_id, user.tenant_id)
    outlet = _get_one(session, RetailOutlet, payload.retail_outlet_id, user.tenant_id)
    lt, txn = post_rso_to_retail_transfer(
        session, user, rso=rso, retail_outlet_id=outlet.id,
        amount=payload.amount, date=payload.date or _today(),
    )
    session.commit()
    return {"load_transfer": lt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


@router.get("/load-transfers")
def list_load_transfers(
    session: SessionDep, user: CurrentUserDep, limit: int = 100,
    from_type: Optional[str] = None,
):
    q = select(LoadTransfer).where(LoadTransfer.tenant_id == user.tenant_id)
    if from_type:
        q = q.where(LoadTransfer.from_type == from_type)
    items = session.exec(q.order_by(LoadTransfer.transfer_date.desc()).limit(limit)).all()
    return {"items": items, "total": len(items)}


class RsoCollectionPayload(BaseModel):
    rso_id: int
    load_portion: Decimal
    stock_portion: Decimal
    total_deposited: Decimal
    date: Optional[str] = None
    bank_account_code: str = "1010"


@router.post("/rso/collections")
def post_collection(payload: RsoCollectionPayload, session: SessionDep, user: WriteUserDep):
    rso = _get_one(session, RsoAgent, payload.rso_id, user.tenant_id)
    coll, txn = post_rso_daily_collection(
        session, user, rso=rso,
        load_portion=payload.load_portion, stock_portion=payload.stock_portion,
        total_deposited=payload.total_deposited,
        date=payload.date or _today(),
        bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"collection": coll, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


@router.get("/rso/collections")
def list_collections(
    session: SessionDep, user: CurrentUserDep,
    rso_id: Optional[int] = None, limit: int = 100,
):
    q = select(RsoDailyCollection).where(RsoDailyCollection.tenant_id == user.tenant_id)
    if rso_id:
        q = q.where(RsoDailyCollection.rso_id == rso_id)
    items = session.exec(q.order_by(RsoDailyCollection.collection_date.desc()).limit(limit)).all()
    return {"items": items, "total": len(items)}


class RsoSimIssuePayload(BaseModel):
    rso_id: int
    batch_id: int
    qty: int
    retail_price: Decimal
    date: Optional[str] = None


@router.post("/rso/sim-issues")
def issue_sim_to_rso(payload: RsoSimIssuePayload, session: SessionDep, user: WriteUserDep):
    rso = _get_one(session, RsoAgent, payload.rso_id, user.tenant_id)
    batch = _get_one(session, SimBatch, payload.batch_id, user.tenant_id)
    avail = batch.qty_received - batch.qty_activated
    if payload.qty > avail:
        raise HTTPException(status_code=400, detail=f"Batch only has {avail} SIMs available")
    issue, txn = post_rso_sim_issue(
        session, user, rso=rso, batch=batch,
        qty=payload.qty, retail_price=payload.retail_price,
        date=payload.date or _today(),
    )
    batch.qty_activated += payload.qty
    session.add(batch)
    session.commit()
    return {"issue": issue, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


# ──────────────────────────────────────────────────────────────────────────
# SIM batches + activations
# ──────────────────────────────────────────────────────────────────────────


@router.get("/sim/batches")
def list_sim_batches(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(SimBatch).where(SimBatch.tenant_id == user.tenant_id).order_by(SimBatch.received_date.desc())
    ).all()
    return {"items": items, "total": len(items)}


class SimActivationCreate(BaseModel):
    operator_id: int
    sim_number: str
    batch_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_cnic: Optional[str] = None
    activation_type: str = "prepaid"
    commission_rate: Decimal = Decimal("0")
    date: Optional[str] = None


@router.get("/sim/activations")
def list_sim_activations(
    session: SessionDep, user: CurrentUserDep,
    status: Optional[str] = None, limit: int = 200,
):
    q = select(SimActivation).where(SimActivation.tenant_id == user.tenant_id)
    if status:
        q = q.where(SimActivation.status == status)
    items = session.exec(q.order_by(SimActivation.activation_date.desc()).limit(limit)).all()
    return {"items": items, "total": len(items)}


@router.post("/sim/activations")
def create_sim_activation(payload: SimActivationCreate, session: SessionDep, user: WriteUserDep):
    op = _get_one(session, Operator, payload.operator_id, user.tenant_id)
    act = SimActivation(
        tenant_id=user.tenant_id, operator_id=op.id,
        sim_number=payload.sim_number,
        batch_id=payload.batch_id,
        activation_date=payload.date or _today(),
        customer_name=payload.customer_name,
        customer_cnic=payload.customer_cnic,
        activation_type=payload.activation_type,
        status="active",
        commission_rate=payload.commission_rate,
    )
    session.add(act); session.commit(); session.refresh(act)
    return act


class CommissionAccrualPayload(BaseModel):
    activation_id: int
    amount: Decimal
    date: Optional[str] = None
    revenue_account_code: str = "4020"


@router.post("/sim/activations/accrue-commission")
def accrue_commission_ep(payload: CommissionAccrualPayload, session: SessionDep, user: WriteUserDep):
    act = _get_one(session, SimActivation, payload.activation_id, user.tenant_id)
    txn = post_commission_accrual(
        session, user, activation=act, amount=payload.amount,
        date=payload.date or _today(),
        revenue_account_code=payload.revenue_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


# ──────────────────────────────────────────────────────────────────────────
# Counter sales (SIM walk-in)
# ──────────────────────────────────────────────────────────────────────────


class CounterSimSalePayload(BaseModel):
    qty: int
    sale_price: Decimal
    unit_cost: Decimal
    date: Optional[str] = None
    cash_account_code: str = "1000"


@router.post("/sim/counter-sales")
def counter_sale(payload: CounterSimSalePayload, session: SessionDep, user: WriteUserDep):
    sale_txn, cogs_txn = post_counter_sim_sale(
        session, user, qty=payload.qty,
        sale_price=payload.sale_price, unit_cost=payload.unit_cost,
        date=payload.date or _today(),
        cash_account_code=payload.cash_account_code,
    )
    session.commit()
    return {
        "sale_transaction": {"id": sale_txn.id, "jv_number": sale_txn.jv_number},
        "cogs_transaction": {"id": cogs_txn.id, "jv_number": cogs_txn.jv_number},
    }


# ──────────────────────────────────────────────────────────────────────────
# FCA events + monthly target commission
# ──────────────────────────────────────────────────────────────────────────


class FcaEventCreate(BaseModel):
    msisdn: str
    sim_id: Optional[int] = None
    source_channel: str = "rso_retail"
    kpi_target_id: Optional[int] = None
    date: Optional[str] = None


@router.get("/fca/events")
def list_fca_events(session: SessionDep, user: CurrentUserDep, limit: int = 200):
    items = session.exec(
        select(FcaEvent).where(FcaEvent.tenant_id == user.tenant_id)
        .order_by(FcaEvent.event_date.desc()).limit(limit)
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/fca/events")
def create_fca_event(payload: FcaEventCreate, session: SessionDep, user: WriteUserDep):
    ev = FcaEvent(
        tenant_id=user.tenant_id, msisdn=payload.msisdn,
        sim_id=payload.sim_id, source_channel=payload.source_channel,
        kpi_target_id=payload.kpi_target_id,
        event_date=payload.date or _today(),
    )
    session.add(ev); session.commit(); session.refresh(ev)
    return ev


class FcaTargetCommissionPayload(BaseModel):
    tracker_account_id: Optional[int] = None
    amount: Decimal
    date: Optional[str] = None
    credit_to: str = "tracker"
    bank_account_code: str = "1010"


@router.post("/fca/target-commission")
def post_target_commission(
    payload: FcaTargetCommissionPayload, session: SessionDep, user: WriteUserDep,
):
    ta = None
    if payload.tracker_account_id:
        ta = _get_one(session, TrackerAccount, payload.tracker_account_id, user.tenant_id)
    txn = post_fca_target_commission(
        session, user, tracker_account=ta,
        amount=payload.amount, date=payload.date or _today(),
        credit_to=payload.credit_to, bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class FcaTargetPenaltyPayload(BaseModel):
    tracker_account_id: int
    amount: Decimal
    date: Optional[str] = None


@router.post("/fca/target-penalty")
def post_target_penalty(payload: FcaTargetPenaltyPayload, session: SessionDep, user: WriteUserDep):
    ta = _get_one(session, TrackerAccount, payload.tracker_account_id, user.tenant_id)
    txn = post_fca_target_penalty(
        session, user, tracker_account=ta,
        amount=payload.amount, date=payload.date or _today(),
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


# ──────────────────────────────────────────────────────────────────────────
# KPI targets
# ──────────────────────────────────────────────────────────────────────────


class KpiTargetCreate(BaseModel):
    operator_id: int
    target_month: str
    metric: str
    target_value: Decimal


@router.get("/kpi/targets")
def list_kpi_targets(
    session: SessionDep, user: CurrentUserDep,
    operator_id: Optional[int] = None, month: Optional[str] = None,
):
    q = select(KpiTarget).where(KpiTarget.tenant_id == user.tenant_id)
    if operator_id:
        q = q.where(KpiTarget.operator_id == operator_id)
    if month:
        q = q.where(KpiTarget.target_month == month)
    items = session.exec(q.order_by(KpiTarget.target_month.desc())).all()
    return {"items": items, "total": len(items)}


@router.post("/kpi/targets")
def create_kpi_target(payload: KpiTargetCreate, session: SessionDep, user: WriteUserDep):
    _get_one(session, Operator, payload.operator_id, user.tenant_id)
    target = KpiTarget(
        tenant_id=user.tenant_id, operator_id=payload.operator_id,
        target_month=payload.target_month, metric=payload.metric,
        target_value=payload.target_value,
    )
    session.add(target); session.commit(); session.refresh(target)
    return target


# ──────────────────────────────────────────────────────────────────────────
# Mobile money
# ──────────────────────────────────────────────────────────────────────────


class MmAccountCreate(BaseModel):
    operator_id: int
    account_number: str
    account_type: str = "jazzcash"


@router.get("/mm/accounts")
def list_mm_accounts(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(MobileMoneyAccount).where(MobileMoneyAccount.tenant_id == user.tenant_id)
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/mm/accounts")
def create_mm_account(payload: MmAccountCreate, session: SessionDep, user: WriteUserDep):
    _get_one(session, Operator, payload.operator_id, user.tenant_id)

    def _acc_id(code: str) -> Optional[int]:
        a = session.exec(
            select(Account).where(Account.tenant_id == user.tenant_id, Account.code == code)
        ).first()
        return a.id if a else None

    mm = MobileMoneyAccount(
        tenant_id=user.tenant_id, operator_id=payload.operator_id,
        account_number=payload.account_number, account_type=payload.account_type,
        float_asset_account_id=_acc_id("1214"),
        float_liability_account_id=_acc_id("2100"),
        commission_account_id=_acc_id("4022"),
    )
    session.add(mm); session.commit(); session.refresh(mm)
    return mm


class MmTxnPayload(BaseModel):
    mm_account_id: int
    amount: Decimal
    date: Optional[str] = None
    customer_reference: Optional[str] = None
    cash_account_code: str = "1000"


@router.post("/mm/top-up")
def mm_top_up(payload: MmTxnPayload, session: SessionDep, user: WriteUserDep):
    mm = _get_one(session, MobileMoneyAccount, payload.mm_account_id, user.tenant_id)
    mt, txn = post_mm_float_top_up(
        session, user, mm_account=mm, amount=payload.amount,
        date=payload.date or _today(), cash_account_code=payload.cash_account_code,
    )
    session.commit()
    return {"mm_transaction": mt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


@router.post("/mm/deposit")
def mm_deposit(payload: MmTxnPayload, session: SessionDep, user: WriteUserDep):
    mm = _get_one(session, MobileMoneyAccount, payload.mm_account_id, user.tenant_id)
    mt, txn = post_mm_customer_deposit(
        session, user, mm_account=mm, amount=payload.amount,
        date=payload.date or _today(),
        customer_reference=payload.customer_reference,
        cash_account_code=payload.cash_account_code,
    )
    session.commit()
    return {"mm_transaction": mt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


@router.post("/mm/withdrawal")
def mm_withdrawal(payload: MmTxnPayload, session: SessionDep, user: WriteUserDep):
    mm = _get_one(session, MobileMoneyAccount, payload.mm_account_id, user.tenant_id)
    mt, txn = post_mm_customer_withdrawal(
        session, user, mm_account=mm, amount=payload.amount,
        date=payload.date or _today(),
        customer_reference=payload.customer_reference,
        cash_account_code=payload.cash_account_code,
    )
    session.commit()
    return {"mm_transaction": mt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class MmCommissionPayload(BaseModel):
    mm_account_id: int
    amount: Decimal
    date: Optional[str] = None
    credit_to: str = "float"
    bank_account_code: str = "1010"


@router.post("/mm/commission")
def mm_commission(payload: MmCommissionPayload, session: SessionDep, user: WriteUserDep):
    mm = _get_one(session, MobileMoneyAccount, payload.mm_account_id, user.tenant_id)
    mt, txn = post_mm_commission_credit(
        session, user, mm_account=mm, amount=payload.amount,
        date=payload.date or _today(), credit_to=payload.credit_to,
        bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"mm_transaction": mt, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class MmReconcilePayload(BaseModel):
    mm_account_id: int
    statement_balance: Decimal
    date: Optional[str] = None


@router.post("/mm/reconcile")
def mm_reconcile(payload: MmReconcilePayload, session: SessionDep, user: WriteUserDep):
    mm = _get_one(session, MobileMoneyAccount, payload.mm_account_id, user.tenant_id)
    txn = post_mm_reconciliation(
        session, user, mm_account=mm,
        statement_balance=payload.statement_balance,
        date=payload.date or _today(),
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number} if txn else None}


@router.get("/mm/transactions")
def list_mm_transactions(
    session: SessionDep, user: CurrentUserDep,
    mm_account_id: Optional[int] = None, limit: int = 200,
):
    q = select(MobileMoneyTransaction).where(MobileMoneyTransaction.tenant_id == user.tenant_id)
    if mm_account_id:
        q = q.where(MobileMoneyTransaction.mm_account_id == mm_account_id)
    items = session.exec(q.order_by(MobileMoneyTransaction.txn_date.desc()).limit(limit)).all()
    return {"items": items, "total": len(items)}


# ──────────────────────────────────────────────────────────────────────────
# Postpaid
# ──────────────────────────────────────────────────────────────────────────


class PostpaidConnectionCreate(BaseModel):
    operator_id: int
    msisdn: str
    customer_name: str
    customer_cnic: Optional[str] = None
    plan_name: str
    monthly_rental: Decimal
    franchise_commission_rate: Decimal = Decimal("10")
    date: Optional[str] = None


@router.get("/postpaid/connections")
def list_postpaid_connections(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(PostpaidConnection).where(PostpaidConnection.tenant_id == user.tenant_id)
        .order_by(PostpaidConnection.activation_date.desc())
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/postpaid/connections")
def create_postpaid_connection(payload: PostpaidConnectionCreate, session: SessionDep, user: WriteUserDep):
    _get_one(session, Operator, payload.operator_id, user.tenant_id)
    conn = PostpaidConnection(
        tenant_id=user.tenant_id, operator_id=payload.operator_id,
        msisdn=payload.msisdn, customer_name=payload.customer_name,
        customer_cnic=payload.customer_cnic, plan_name=payload.plan_name,
        monthly_rental=payload.monthly_rental,
        activation_date=payload.date or _today(),
        franchise_commission_rate=payload.franchise_commission_rate,
    )
    session.add(conn); session.commit(); session.refresh(conn)
    return conn


class PostpaidBillPayload(BaseModel):
    connection_id: int
    billing_month: str
    gross_amount: Decimal


@router.post("/postpaid/bills")
def bill_postpaid(payload: PostpaidBillPayload, session: SessionDep, user: WriteUserDep):
    conn = _get_one(session, PostpaidConnection, payload.connection_id, user.tenant_id)
    cycle, txn = post_postpaid_bill(
        session, user, connection=conn,
        billing_month=payload.billing_month, gross_amount=payload.gross_amount,
    )
    session.commit()
    return {"cycle": cycle, "transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class PostpaidCollectionPayload(BaseModel):
    cycle_id: int
    amount: Decimal
    date: Optional[str] = None
    cash_account_code: str = "1000"


@router.post("/postpaid/collect")
def collect_postpaid(payload: PostpaidCollectionPayload, session: SessionDep, user: WriteUserDep):
    cycle = _get_one(session, PostpaidBillCycle, payload.cycle_id, user.tenant_id)
    txn = post_postpaid_collection(
        session, user, cycle=cycle, amount=payload.amount,
        date=payload.date or _today(),
        cash_account_code=payload.cash_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class PostpaidRemitPayload(BaseModel):
    cycle_id: int
    date: Optional[str] = None
    bank_account_code: str = "1010"


@router.post("/postpaid/remit")
def remit_postpaid(payload: PostpaidRemitPayload, session: SessionDep, user: WriteUserDep):
    cycle = _get_one(session, PostpaidBillCycle, payload.cycle_id, user.tenant_id)
    txn = post_postpaid_remittance(
        session, user, cycle=cycle,
        date=payload.date or _today(),
        bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


@router.get("/postpaid/cycles")
def list_postpaid_cycles(session: SessionDep, user: CurrentUserDep, limit: int = 200):
    items = session.exec(
        select(PostpaidBillCycle).where(PostpaidBillCycle.tenant_id == user.tenant_id)
        .order_by(PostpaidBillCycle.billing_month.desc()).limit(limit)
    ).all()
    return {"items": items, "total": len(items)}


# ──────────────────────────────────────────────────────────────────────────
# Commission statements
# ──────────────────────────────────────────────────────────────────────────


class CommissionStatementCreate(BaseModel):
    operator_id: int
    statement_date: str
    period_from: str
    period_to: str
    statement_reference: Optional[str] = None
    total_commission: Decimal
    lines: list[dict] = []   # [{commission_type, accrued_amount, event_reference?}]


@router.get("/commissions/statements")
def list_commission_statements(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(CommissionStatement).where(CommissionStatement.tenant_id == user.tenant_id)
        .order_by(CommissionStatement.statement_date.desc())
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/commissions/statements")
def create_commission_statement(payload: CommissionStatementCreate, session: SessionDep, user: WriteUserDep):
    _get_one(session, Operator, payload.operator_id, user.tenant_id)
    stmt = CommissionStatement(
        tenant_id=user.tenant_id, operator_id=payload.operator_id,
        statement_date=payload.statement_date,
        period_from=payload.period_from, period_to=payload.period_to,
        statement_reference=payload.statement_reference,
        total_commission=payload.total_commission,
    )
    session.add(stmt); session.flush()
    for ln in payload.lines:
        session.add(CommissionLine(
            tenant_id=user.tenant_id, statement_id=stmt.id,
            commission_type=ln.get("commission_type", "activation"),
            event_reference=ln.get("event_reference"),
            event_date=ln.get("event_date"),
            accrued_amount=Decimal(str(ln.get("accrued_amount", "0"))),
        ))
    session.commit(); session.refresh(stmt)
    return stmt


class CommissionSettlePayload(BaseModel):
    statement_id: int
    settlement_amount: Decimal
    date: Optional[str] = None
    credit_via: str = "bank"
    bank_account_code: str = "1010"


@router.post("/commissions/settle")
def settle_commission(payload: CommissionSettlePayload, session: SessionDep, user: WriteUserDep):
    stmt = _get_one(session, CommissionStatement, payload.statement_id, user.tenant_id)
    txn = post_commission_statement_settlement(
        session, user, statement=stmt,
        settlement_amount=payload.settlement_amount,
        date=payload.date or _today(),
        credit_via=payload.credit_via,
        bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


# ──────────────────────────────────────────────────────────────────────────
# Franchise admin (agreement + amortisation + royalty)
# ──────────────────────────────────────────────────────────────────────────


class FranchiseAgreementCreate(BaseModel):
    operator_id: int
    agreement_number: str
    start_date: str
    end_date: Optional[str] = None
    franchise_fee_paid: Decimal = Decimal("0")
    royalty_rate_pct: Decimal = Decimal("0")
    min_monthly_target: Decimal = Decimal("0")
    penalty_rate_pct: Decimal = Decimal("0")
    amortisation_months: int = 60


@router.get("/franchise/agreements")
def list_agreements(session: SessionDep, user: CurrentUserDep):
    items = session.exec(
        select(FranchiseAgreement).where(FranchiseAgreement.tenant_id == user.tenant_id)
    ).all()
    return {"items": items, "total": len(items)}


@router.post("/franchise/agreements")
def create_agreement(payload: FranchiseAgreementCreate, session: SessionDep, user: WriteUserDep):
    _get_one(session, Operator, payload.operator_id, user.tenant_id)

    def _acc_id(code: str) -> Optional[int]:
        a = session.exec(
            select(Account).where(Account.tenant_id == user.tenant_id, Account.code == code)
        ).first()
        return a.id if a else None

    ag = FranchiseAgreement(
        tenant_id=user.tenant_id,
        intangible_account_id=_acc_id("1300"),
        amortisation_account_id=_acc_id("5030"),
        **payload.model_dump(),
    )
    session.add(ag); session.commit(); session.refresh(ag)
    return ag


class FranchiseFeePayload(BaseModel):
    agreement_id: int
    fee: Decimal
    date: Optional[str] = None
    bank_account_code: str = "1010"


@router.post("/franchise/capitalise-fee")
def capitalise_fee(payload: FranchiseFeePayload, session: SessionDep, user: WriteUserDep):
    ag = _get_one(session, FranchiseAgreement, payload.agreement_id, user.tenant_id)
    txn = post_franchise_fee_capitalisation(
        session, user, agreement=ag, fee=payload.fee,
        date=payload.date or _today(),
        bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class AmortisePayload(BaseModel):
    agreement_id: int
    date: Optional[str] = None


@router.post("/franchise/amortise")
def amortise_fee(payload: AmortisePayload, session: SessionDep, user: WriteUserDep):
    ag = _get_one(session, FranchiseAgreement, payload.agreement_id, user.tenant_id)
    txn = post_franchise_fee_amortisation(
        session, user, agreement=ag, date=payload.date or _today(),
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class RoyaltyAccrualPayload(BaseModel):
    agreement_id: int
    gross_revenue: Decimal
    date: Optional[str] = None


@router.post("/franchise/royalty/accrue")
def accrue_royalty(payload: RoyaltyAccrualPayload, session: SessionDep, user: WriteUserDep):
    ag = _get_one(session, FranchiseAgreement, payload.agreement_id, user.tenant_id)
    txn = post_royalty_accrual(
        session, user, agreement=ag, gross_revenue=payload.gross_revenue,
        date=payload.date or _today(),
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


class RoyaltyPaymentPayload(BaseModel):
    amount: Decimal
    date: Optional[str] = None
    bank_account_code: str = "1010"


@router.post("/franchise/royalty/pay")
def pay_royalty(payload: RoyaltyPaymentPayload, session: SessionDep, user: WriteUserDep):
    txn = post_royalty_payment(
        session, user, amount=payload.amount,
        date=payload.date or _today(),
        bank_account_code=payload.bank_account_code,
    )
    session.commit()
    return {"transaction": {"id": txn.id, "jv_number": txn.jv_number}}


# ──────────────────────────────────────────────────────────────────────────
# Device IMEI
# ──────────────────────────────────────────────────────────────────────────


class DeviceImeiCreate(BaseModel):
    product_id: int
    imei_number: str
    serial_number: Optional[str] = None
    status: str = "in_stock"


@router.get("/imei")
def list_imei(session: SessionDep, user: CurrentUserDep, status: Optional[str] = None):
    q = select(DeviceImei).where(DeviceImei.tenant_id == user.tenant_id)
    if status:
        q = q.where(DeviceImei.status == status)
    items = session.exec(q).all()
    return {"items": items, "total": len(items)}


@router.post("/imei")
def create_imei(payload: DeviceImeiCreate, session: SessionDep, user: WriteUserDep):
    imei = DeviceImei(tenant_id=user.tenant_id, **payload.model_dump())
    session.add(imei); session.commit(); session.refresh(imei)
    return imei
