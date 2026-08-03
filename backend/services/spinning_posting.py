"""Central GL posting for the Yarn Spinning module."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlmodel import Session, func, select

from models import Product, StockLocation, User
from models_spinning import (
    STAGE_WIP_ACCOUNTS,
    SpBaleReceipt,
    SpConeOutput,
    SpSpinLot,
    SpStageEntry,
    SpWasteLog,
    SpWasteType,
    SpYarnDispatch,
    SpYarnSpec,
)
from services.inventory import InventoryError, consume_stock, record_purchase
from services.money import D, ZERO, money
from services.posting import EntryInput, post_transaction
from services import spinning_calc as calc
from routers.common import get_default_account, get_or_create_account


def _location(session: Session, tenant_id: int, code: str, ltype: str) -> StockLocation:
    loc = session.exec(
        select(StockLocation).where(
            StockLocation.tenant_id == tenant_id,
            StockLocation.code == code,
            StockLocation.is_active == True,  # noqa: E712
        )
    ).first()
    if not loc:
        loc = StockLocation(tenant_id=tenant_id, code=code, name=code, type=ltype, is_active=True)
        session.add(loc)
        session.flush()
    return loc


def _account(session: Session, tenant_id: int, code: str, name: str, atype: str):
    return get_or_create_account(session, tenant_id, code, name, atype)


def ensure_spinning_locations(session: Session, tenant_id: int) -> None:
    for code, name, ltype in (
        ("RAW", "Raw Cotton Store", "own"),
        ("WIP-CARD", "WIP Carding", "wip"),
        ("WIP-DRAW", "WIP Drawing", "wip"),
        ("WIP-SPIN", "WIP Spinning", "wip"),
        ("FG-YARN", "Finished Yarn", "own"),
    ):
        _location(session, tenant_id, code, ltype)


def _lot_costs(session: Session, lot: SpSpinLot) -> None:
    from models_spinning import SpBaleReceipt as BR, SpStageEntry as SE, SpWasteLog as WL

    tid = lot.tenant_id
    material = session.exec(
        select(func.coalesce(func.sum(BR.total_value), 0)).where(
            BR.tenant_id == tid, BR.spin_lot_id == lot.id, BR.status == "approved"
        )
    ).one()
    labour = session.exec(
        select(func.coalesce(func.sum(SE.labour_cost), 0)).where(
            SE.tenant_id == tid, SE.spin_lot_id == lot.id, SE.status == "posted"
        )
    ).one()
    overhead = session.exec(
        select(func.coalesce(func.sum(SE.overhead_cost), 0)).where(
            SE.tenant_id == tid, SE.spin_lot_id == lot.id, SE.status == "posted"
        )
    ).one()
    waste = session.exec(
        select(func.coalesce(func.sum(WL.cost_value), 0)).where(
            WL.tenant_id == tid, WL.spin_lot_id == lot.id, WL.status == "posted"
        )
    ).one()
    lot.material_cost = money(D(material))
    lot.labour_cost = money(D(labour))
    lot.overhead_cost = money(D(overhead))
    lot.waste_cost = money(D(waste))
    lot.total_cost = money(lot.material_cost + lot.labour_cost + lot.overhead_cost + lot.waste_cost)
    lot.cost_per_kg = calc.cost_per_kg(lot.total_cost, lot.output_kg)
    session.add(lot)


def approve_bale_receipt(session: Session, user: User, receipt: SpBaleReceipt) -> None:
    if receipt.status != "draft":
        raise HTTPException(400, "Only draft bale receipts can be approved")
    if receipt.net_kg <= 0:
        raise HTTPException(400, "net_kg must be positive")

    ensure_spinning_locations(session, user.tenant_id)
    raw_loc = _location(session, user.tenant_id, "RAW", "own")
    value = money(receipt.total_value or receipt.net_kg * receipt.rate_per_kg)
    receipt.total_value = value

    record_purchase(
        session,
        tenant_id=user.tenant_id,
        product_id=receipt.product_id,
        qty=receipt.net_kg,
        unit_cost=money(value / receipt.net_kg) if receipt.net_kg else ZERO,
        location_id=raw_loc.id,
        lot_no=receipt.lot_no,
        source_doc=receipt.number,
        source_doc_type="sp_bale_receipt",
        posted_to_gl=True,
    )

    rm = _account(session, user.tenant_id, "1200", "Raw Cotton / Fiber Inventory", "Asset")
    if receipt.bill_id:
        cr = get_default_account(
            session, user.tenant_id, "default_ap_account", "2100", "Accounts Payable", "Liability"
        )
        cr_entry = EntryInput(account_id=cr.id, credit=value, vendor_id=receipt.vendor_id)
    else:
        cr = get_default_account(
            session, user.tenant_id, "default_cash_account", "1000", "Cash", "Asset"
        )
        cr_entry = EntryInput(account_id=cr.id, credit=value)

    txn = post_transaction(
        session, user,
        date=receipt.date,
        description=f"{receipt.number} — bale receipt",
        entries=[
            EntryInput(account_id=rm.id, debit=value),
            cr_entry,
        ],
        audit_entity_type="sp_bale_receipt",
        audit_detail={"number": receipt.number, "net_kg": str(receipt.net_kg)},
    )
    receipt.transaction_id = txn.id
    receipt.status = "approved"

    if receipt.spin_lot_id:
        lot = session.get(SpSpinLot, receipt.spin_lot_id)
        if lot and lot.tenant_id == user.tenant_id:
            _lot_costs(session, lot)
    session.add(receipt)


def post_stage_entry(session: Session, user: User, entry: SpStageEntry) -> None:
    if entry.status != "draft":
        raise HTTPException(400, "Stage entry already posted")

    transfer_cost = money(entry.input_kg * (entry.labour_cost + entry.overhead_cost) / entry.output_kg
                          if entry.output_kg else ZERO)
    if transfer_cost == ZERO and entry.input_kg > 0:
        rm = _account(session, user.tenant_id, "1200", "Raw Cotton / Fiber Inventory", "Asset")
        transfer_cost = money(entry.input_kg * Decimal("1"))  # placeholder — real cost from RM avg

    wip_code = STAGE_WIP_ACCOUNTS.get(entry.stage, "1201")
    wip_names = {
        "1201": "WIP — Opening & Carding",
        "1202": "WIP — Drawing & Roving",
        "1203": "WIP — Ring Spinning",
    }
    wip_acc = _account(session, user.tenant_id, wip_code, wip_names.get(wip_code, "WIP"), "Asset")

    entries: list[EntryInput] = []
    if entry.stage in ("opening", "carding"):
        rm_acc = _account(session, user.tenant_id, "1200", "Raw Cotton / Fiber Inventory", "Asset")
        mat_cost = money(entry.input_kg * receipt_avg_cost(session, user.tenant_id, entry.spin_lot_id))
        if mat_cost > 0:
            entries.extend([
                EntryInput(account_id=wip_acc.id, debit=mat_cost),
                EntryInput(account_id=rm_acc.id, credit=mat_cost),
            ])
    else:
        prev_stages = {
            "drawing": "1201", "roving": "1201",
            "spinning": "1202", "winding": "1202",
        }
        prev_code = prev_stages.get(entry.stage, "1201")
        prev_acc = _account(
            session, user.tenant_id, prev_code,
            wip_names.get(prev_code, "WIP"), "Asset",
        )
        xfer = money(entry.input_kg * Decimal("1"))
        if xfer > 0:
            entries.extend([
                EntryInput(account_id=wip_acc.id, debit=xfer),
                EntryInput(account_id=prev_acc.id, credit=xfer),
            ])

    if entry.labour_cost > 0:
        lab = get_default_account(
            session, user.tenant_id, "default_mfg_labour_account", "5100", "Direct Labour", "Expense"
        )
        entries.extend([
            EntryInput(account_id=wip_acc.id, debit=entry.labour_cost),
            EntryInput(account_id=lab.id, credit=entry.labour_cost),
        ])
    if entry.overhead_cost > 0:
        oh = get_default_account(
            session, user.tenant_id, "default_mfg_overhead_account", "5200", "Manufacturing Overhead", "Expense"
        )
        entries.extend([
            EntryInput(account_id=wip_acc.id, debit=entry.overhead_cost),
            EntryInput(account_id=oh.id, credit=entry.overhead_cost),
        ])

    if entries:
        txn = post_transaction(
            session, user,
            date=entry.date,
            description=f"{entry.number} — stage {entry.stage}",
            entries=entries,
            audit_entity_type="sp_stage_entry",
            audit_detail={"number": entry.number, "stage": entry.stage},
        )
        entry.transaction_id = txn.id

    entry.status = "posted"
    session.add(entry)
    lot = session.get(SpSpinLot, entry.spin_lot_id)
    if lot:
        _lot_costs(session, lot)


def receipt_avg_cost(session: Session, tenant_id: int, spin_lot_id: Optional[int]) -> Decimal:
    from models_spinning import SpBaleReceipt as BR
    q = select(BR).where(BR.tenant_id == tenant_id, BR.status == "approved")
    if spin_lot_id:
        q = q.where(BR.spin_lot_id == spin_lot_id)
    rows = session.exec(q).all()
    total_kg = sum((D(r.net_kg) for r in rows), start=ZERO)
    total_val = sum((D(r.total_value) for r in rows), start=ZERO)
    if total_kg <= 0:
        return ZERO
    return money(total_val / total_kg)


def post_waste_log(session: Session, user: User, waste: SpWasteLog) -> None:
    if waste.status != "draft":
        raise HTTPException(400, "Waste log already posted")
    wt = session.get(SpWasteType, waste.waste_type_id)
    if not wt or wt.tenant_id != user.tenant_id:
        raise HTTPException(404, "Waste type not found")

    wip_code = STAGE_WIP_ACCOUNTS.get(waste.stage, "1201")
    wip_acc = _account(session, user.tenant_id, wip_code, "WIP", "Asset")
    scrap_acc = _account(session, user.tenant_id, wt.gl_account_code, wt.name, "Expense")

    cost = waste.cost_value
    if cost <= 0:
        avg = receipt_avg_cost(session, user.tenant_id, waste.spin_lot_id)
        cost = money(waste.qty_kg * avg)
        waste.cost_value = cost

    txn = post_transaction(
        session, user,
        date=waste.date,
        description=f"{waste.number} — waste",
        entries=[
            EntryInput(account_id=scrap_acc.id, debit=cost),
            EntryInput(account_id=wip_acc.id, credit=cost),
        ],
        audit_entity_type="sp_waste_log",
        audit_detail={"number": waste.number, "stage": waste.stage},
    )
    waste.transaction_id = txn.id
    waste.status = "posted"
    session.add(waste)
    lot = session.get(SpSpinLot, waste.spin_lot_id)
    if lot:
        _lot_costs(session, lot)


def approve_cone_output(session: Session, user: User, cone: SpConeOutput) -> None:
    if cone.status != "draft":
        raise HTTPException(400, "Only draft cone output can be approved")
    lot = session.get(SpSpinLot, cone.spin_lot_id)
    if not lot or lot.tenant_id != user.tenant_id:
        raise HTTPException(404, "Spin lot not found")

    _lot_costs(session, lot)
    spec = session.get(SpYarnSpec, lot.yarn_spec_id)
    product_id = spec.output_product_id if spec else None
    if not product_id:
        raise HTTPException(400, "Yarn spec has no output product — link a finished yarn SKU in Setup")

    ensure_spinning_locations(session, user.tenant_id)
    fg_loc = _location(session, user.tenant_id, "FG-YARN", "own")

    total_lot_cost = lot.total_cost
    total_out = lot.output_kg + cone.net_kg
    if total_out > 0 and lot.output_kg == ZERO:
        unit = money(total_lot_cost / total_out)
    elif lot.output_kg > 0:
        unit = lot.cost_per_kg
    else:
        unit = money(total_lot_cost / cone.net_kg) if cone.net_kg else ZERO

    cone.unit_cost = unit
    cone.total_cost = money(unit * cone.net_kg)

    record_purchase(
        session,
        tenant_id=user.tenant_id,
        product_id=product_id,
        qty=cone.net_kg,
        unit_cost=unit,
        location_id=fg_loc.id,
        lot_no=cone.lot_no,
        source_doc=cone.number,
        source_doc_type="sp_cone_output",
        posted_to_gl=True,
    )

    fg = _account(session, user.tenant_id, "1204", "Finished Yarn Inventory", "Asset")
    wip = _account(session, user.tenant_id, "1203", "WIP — Ring Spinning", "Asset")
    txn = post_transaction(
        session, user,
        date=cone.date,
        description=f"{cone.number} — cone output",
        entries=[
            EntryInput(account_id=fg.id, debit=cone.total_cost),
            EntryInput(account_id=wip.id, credit=cone.total_cost),
        ],
        audit_entity_type="sp_cone_output",
        audit_detail={"number": cone.number, "net_kg": str(cone.net_kg)},
    )
    cone.transaction_id = txn.id
    cone.status = "approved"
    lot.output_kg = money(lot.output_kg + cone.net_kg)
    _lot_costs(session, lot)
    session.add(cone)
    session.add(lot)


def approve_yarn_dispatch(session: Session, user: User, dispatch: SpYarnDispatch) -> None:
    if dispatch.status != "draft":
        raise HTTPException(400, "Only draft dispatches can be approved")

    spec = session.get(SpYarnSpec, dispatch.yarn_spec_id)
    product_id = dispatch.product_id or (spec.output_product_id if spec else None)
    if not product_id:
        raise HTTPException(400, "No product linked for dispatch")

    ensure_spinning_locations(session, user.tenant_id)
    fg_loc = _location(session, user.tenant_id, "FG-YARN", "own")

    try:
        consume_stock(
            session,
            tenant_id=user.tenant_id,
            product_id=product_id,
            qty=dispatch.net_kg,
            source_doc_type="sp_yarn_dispatch",
            source_doc_id=dispatch.id,
            block_negative=False,
        )
    except InventoryError as e:
        raise HTTPException(400, str(e)) from e

    cogs = get_default_account(
        session, user.tenant_id, "default_cogs_account", "5010", "Cost of Goods Sold", "Expense"
    )
    fg = _account(session, user.tenant_id, "1204", "Finished Yarn Inventory", "Asset")

    prod = session.get(Product, product_id)
    unit_cost = D(prod.avg_cost) if prod else ZERO
    cost = money(unit_cost * dispatch.net_kg)

    txn = post_transaction(
        session, user,
        date=dispatch.date,
        description=f"{dispatch.number} — yarn dispatch COGS",
        entries=[
            EntryInput(account_id=cogs.id, debit=cost),
            EntryInput(account_id=fg.id, credit=cost),
        ],
        audit_entity_type="sp_yarn_dispatch",
        audit_detail={"number": dispatch.number, "net_kg": str(dispatch.net_kg)},
    )
    dispatch.transaction_id = txn.id
    dispatch.status = "approved"
    dispatch.dispatch_value = calc.dispatch_value(dispatch.net_kg, dispatch.rate_per_kg)
    session.add(dispatch)


def start_spin_lot(session: Session, lot: SpSpinLot) -> None:
    if lot.status != "draft":
        raise HTTPException(400, "Only draft lots can be started")
    from datetime import datetime
    lot.status = "in_process"
    lot.started_at = datetime.utcnow()
    session.add(lot)


def complete_spin_lot(session: Session, lot: SpSpinLot) -> None:
    if lot.status != "in_process":
        raise HTTPException(400, "Lot must be in_process to complete")
    from datetime import datetime
    _lot_costs(session, lot)
    lot.status = "completed"
    lot.completed_at = datetime.utcnow()
    session.add(lot)


def close_spin_lot(session: Session, lot: SpSpinLot) -> None:
    if lot.status != "completed":
        raise HTTPException(400, "Lot must be completed before close")
    from datetime import datetime
    lot.status = "closed"
    lot.closed_at = datetime.utcnow()
    session.add(lot)
