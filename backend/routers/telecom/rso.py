"""RSO Channel — Retail Sales Officers, load transfers, retail outlets,
and daily cash collections.

GL flows:
  Load MSR→RSO:      Dr 1212 RSO Load Receivable / Cr 1211 Load Float Asset
  Load RSO→Retail:   Dr 1213 Retail Load Receivable / Cr 1212 RSO Load Receivable
  Daily collection:  Dr 1010 Bank / Cr 1212 (load_portion) / Cr 1120 (stock_portion)
                     ± Dr/Cr 5070 Tracker Variance for any non-zero variance
"""
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlmodel import select

from models import (
    Account, JournalEntry, LoadTransfer, RetailOutlet,
    RSOAgent, RSODailyCollection, TrackerAccount,
)
from services.money import D, ZERO
from services.posting import EntryInput, post_transaction

from ..common import (
    CurrentUserDep, SessionDep, WriteUserDep,
    get_or_create_account, log_audit, next_number,
)

router = APIRouter(prefix="/api/telecom", tags=["telecom"])


def _get_rso(session, tenant_id: int, rso_id: int) -> RSOAgent:
    rso = session.get(RSOAgent, rso_id)
    if not rso or rso.tenant_id != tenant_id:
        raise HTTPException(404, "RSO agent not found")
    return rso


def _rso_load_outstanding(session, tenant_id: int, rso_id: int) -> Decimal:
    """Net load transferred to this RSO minus load portion of collections."""
    acc = session.exec(
        select(Account).where(Account.tenant_id == tenant_id, Account.code == "1212")
    ).first()
    if not acc:
        return ZERO
    entries = session.exec(
        select(JournalEntry).where(
            JournalEntry.account_id == acc.id,
            JournalEntry.tenant_id == tenant_id,
        )
    ).all()
    return sum((D(e.debit) - D(e.credit) for e in entries), ZERO)


# ── RSO Agent CRUD ────────────────────────────────────────────────────────────

class RSOAgentCreate(BaseModel):
    name: str
    phone: str
    cnic: Optional[str] = None
    territory: Optional[str] = None


class RSOAgentUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    territory: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/rso-agents")
def list_rso_agents(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(RSOAgent).where(RSOAgent.tenant_id == user.tenant_id)
    ).all()
    return {"items": [
        {**r.model_dump(),
         "load_outstanding": _rso_load_outstanding(session, user.tenant_id, r.id)}
        for r in rows
    ]}


@router.post("/rso-agents", status_code=201)
def create_rso_agent(body: RSOAgentCreate, session: SessionDep, user: WriteUserDep):
    rso_recv = get_or_create_account(session, user.tenant_id, "1120",
                                     "RSO Receivables", "Asset")
    rso = RSOAgent(
        tenant_id=user.tenant_id,
        name=body.name,
        phone=body.phone,
        cnic=body.cnic,
        territory=body.territory,
        receivable_account_id=rso_recv.id,
    )
    session.add(rso)
    session.flush()
    log_audit(session, user, "CREATE", "rso_agent", rso.id, {"name": body.name})
    session.commit()
    session.refresh(rso)
    return rso


@router.get("/rso-agents/{rso_id}")
def get_rso_agent(rso_id: int, session: SessionDep, user: CurrentUserDep):
    rso = _get_rso(session, user.tenant_id, rso_id)
    transfers = session.exec(
        select(LoadTransfer).where(
            LoadTransfer.tenant_id == user.tenant_id,
            LoadTransfer.to_ref_id == rso_id,
            LoadTransfer.to_type == "rso",
        ).order_by(LoadTransfer.transfer_date.desc())
    ).all()
    collections = session.exec(
        select(RSODailyCollection).where(
            RSODailyCollection.tenant_id == user.tenant_id,
            RSODailyCollection.rso_id == rso_id,
        ).order_by(RSODailyCollection.collection_date.desc())
    ).all()
    return {
        **rso.model_dump(),
        "load_outstanding": _rso_load_outstanding(session, user.tenant_id, rso_id),
        "recent_transfers":   [t.model_dump() for t in transfers[:10]],
        "recent_collections": [c.model_dump() for c in collections[:10]],
    }


@router.patch("/rso-agents/{rso_id}")
def update_rso_agent(
    rso_id: int, body: RSOAgentUpdate, session: SessionDep, user: WriteUserDep
):
    rso = _get_rso(session, user.tenant_id, rso_id)
    for field, val in body.model_dump(exclude_unset=True).items():
        setattr(rso, field, val)
    session.add(rso)
    log_audit(session, user, "UPDATE", "rso_agent", rso_id)
    session.commit()
    session.refresh(rso)
    return rso


# ── Retail Outlets ────────────────────────────────────────────────────────────

class RetailOutletCreate(BaseModel):
    rso_id: int
    shop_name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None


@router.get("/retail-outlets")
def list_retail_outlets(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(RetailOutlet).where(RetailOutlet.tenant_id == user.tenant_id)
    ).all()
    return {"items": [r.model_dump() for r in rows]}


@router.post("/retail-outlets", status_code=201)
def create_retail_outlet(body: RetailOutletCreate, session: SessionDep, user: WriteUserDep):
    _get_rso(session, user.tenant_id, body.rso_id)  # ownership check
    outlet = RetailOutlet(tenant_id=user.tenant_id, **body.model_dump())
    session.add(outlet)
    session.flush()
    log_audit(session, user, "CREATE", "retail_outlet", outlet.id,
              {"shop_name": body.shop_name})
    session.commit()
    session.refresh(outlet)
    return outlet


# ── Load Transfers ────────────────────────────────────────────────────────────

class LoadTransferCreate(BaseModel):
    transfer_date: str
    from_type: str        # msr | rso
    from_ref_id: Optional[int] = None   # rso_agent.id when from_type=rso
    to_type: str          # rso | retail
    to_ref_id: int        # rso_agent.id or retail_outlet.id
    amount: Decimal


@router.get("/load-transfers")
def list_load_transfers(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(LoadTransfer).where(
            LoadTransfer.tenant_id == user.tenant_id
        ).order_by(LoadTransfer.transfer_date.desc())
    ).all()
    return {"items": [r.model_dump() for r in rows]}


@router.post("/load-transfers", status_code=201)
def create_load_transfer(body: LoadTransferCreate, session: SessionDep, user: WriteUserDep):
    if body.from_type not in ("msr", "rso"):
        raise HTTPException(400, "from_type must be 'msr' or 'rso'")
    if body.to_type not in ("rso", "retail"):
        raise HTTPException(400, "to_type must be 'rso' or 'retail'")
    amt = D(body.amount)

    # Determine debit and credit accounts based on hop
    if body.from_type == "msr" and body.to_type == "rso":
        # MSR SIM → RSO SIM:  Dr 1212 RSO Load Receivable / Cr 1211 Load Float
        debit_acc  = get_or_create_account(session, user.tenant_id, "1212",
                                           "RSO Load Receivable", "Asset")
        credit_acc = get_or_create_account(session, user.tenant_id, "1211",
                                           "Load Float Asset (MSR SIM)", "Asset")
        description = "Load transfer MSR → RSO"
    elif body.from_type == "rso" and body.to_type == "retail":
        # RSO SIM → Retail:   Dr 1213 Retail Load Receivable / Cr 1212 RSO Load Receivable
        debit_acc  = get_or_create_account(session, user.tenant_id, "1213",
                                           "Retail Load Receivable", "Asset")
        credit_acc = get_or_create_account(session, user.tenant_id, "1212",
                                           "RSO Load Receivable", "Asset")
        description = "Load transfer RSO → Retail"
    else:
        raise HTTPException(400, "Invalid from_type / to_type combination")

    ref = next_number(session, user.tenant_id, "load_transfer", "LT")
    txn = post_transaction(
        session, user,
        date=body.transfer_date,
        description=description,
        reference=ref,
        entries=[
            EntryInput(account_id=debit_acc.id,  debit=amt),
            EntryInput(account_id=credit_acc.id, credit=amt),
        ],
        audit_entity_type="load_transfer",
    )

    lt = LoadTransfer(
        tenant_id=user.tenant_id,
        transfer_date=body.transfer_date,
        from_type=body.from_type,
        from_ref_id=body.from_ref_id,
        to_type=body.to_type,
        to_ref_id=body.to_ref_id,
        amount=amt,
        transaction_id=txn.id,
    )
    session.add(lt)
    session.commit()
    session.refresh(lt)
    return {"load_transfer": lt.model_dump(), "jv_number": txn.jv_number}


# ── RSO Daily Collection ──────────────────────────────────────────────────────

class RSOCollectionCreate(BaseModel):
    rso_id: int
    collection_date: str
    load_portion: Decimal
    stock_portion: Decimal
    total_deposited: Decimal
    bank_account_code: str = "1010"
    notes: Optional[str] = None


@router.get("/rso-collections")
def list_rso_collections(session: SessionDep, user: CurrentUserDep):
    rows = session.exec(
        select(RSODailyCollection).where(
            RSODailyCollection.tenant_id == user.tenant_id
        ).order_by(RSODailyCollection.collection_date.desc())
    ).all()
    return {"items": [r.model_dump() for r in rows]}


@router.post("/rso-collections", status_code=201)
def create_rso_collection(body: RSOCollectionCreate, session: SessionDep, user: WriteUserDep):
    """Record RSO daily bank deposit settling both load and stock.

    GL:
      Dr 1010 Bank            total_deposited
      Cr 1212 RSO Load Rec    load_portion
      Cr 1120 RSO Receivables stock_portion
      Dr/Cr 5070 Variance     variance (if non-zero)
    """
    _get_rso(session, user.tenant_id, body.rso_id)

    load_p   = D(body.load_portion)
    stock_p  = D(body.stock_portion)
    total    = D(body.total_deposited)
    variance = total - load_p - stock_p

    bank_acc  = get_or_create_account(session, user.tenant_id, body.bank_account_code,
                                      "Bank", "Asset")
    load_rec  = get_or_create_account(session, user.tenant_id, "1212",
                                      "RSO Load Receivable", "Asset")
    stock_rec = get_or_create_account(session, user.tenant_id, "1120",
                                      "RSO Receivables", "Asset")
    var_acc   = get_or_create_account(session, user.tenant_id, "5070",
                                      "Tracker Variance", "Expense")

    entries = [EntryInput(account_id=bank_acc.id, debit=total)]
    if load_p > ZERO:
        entries.append(EntryInput(account_id=load_rec.id,  credit=load_p))
    if stock_p > ZERO:
        entries.append(EntryInput(account_id=stock_rec.id, credit=stock_p))
    if variance > ZERO:
        # surplus — franchisee over-deposited; credit variance account
        entries.append(EntryInput(account_id=var_acc.id, credit=variance))
    elif variance < ZERO:
        # shortfall — franchisee under-deposited; debit variance account
        entries.append(EntryInput(account_id=var_acc.id, debit=abs(variance)))

    ref = next_number(session, user.tenant_id, "rso_collection", "RC")
    txn = post_transaction(
        session, user,
        date=body.collection_date,
        description=f"RSO daily collection – RSO #{body.rso_id}",
        reference=ref,
        entries=entries,
        audit_entity_type="rso_daily_collection",
    )

    coll = RSODailyCollection(
        tenant_id=user.tenant_id,
        rso_id=body.rso_id,
        collection_date=body.collection_date,
        load_portion=load_p,
        stock_portion=stock_p,
        total_deposited=total,
        variance=variance,
        transaction_id=txn.id,
        notes=body.notes,
    )
    session.add(coll)
    session.commit()
    session.refresh(coll)
    return {"collection": coll.model_dump(), "jv_number": txn.jv_number}
