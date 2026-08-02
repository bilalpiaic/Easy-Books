"""IFRS 16 lease accounting — PV, schedule, recognition, period post (#256).

All GL writes go through `services.posting.post_transaction`.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select

from models import LeaseContract, LeaseScheduleLine, User
from routers.common import get_or_create_account, next_number
from services.money import D, ZERO, money
from services.posting import EntryInput, PostingError, post_transaction


class LeaseError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class ScheduleRow:
    period_index: int
    period_date: str
    opening_liability: Decimal
    interest: Decimal
    payment: Decimal
    principal: Decimal
    closing_liability: Decimal
    depreciation: Decimal


def monthly_rate(annual_pct: Decimal) -> Decimal:
    """Convert annual percent (e.g. 8.00) to monthly decimal rate."""
    return D(annual_pct) / Decimal("100") / Decimal("12")


def present_value_of_lease(
    payment: Decimal,
    term_months: int,
    annual_pct: Decimal,
    timing: str = "arrears",
) -> Decimal:
    """PV of fixed lease payments (ordinary annuity or annuity-due)."""
    pmt = D(payment)
    n = int(term_months)
    if n <= 0 or pmt == ZERO:
        return ZERO
    r = monthly_rate(annual_pct)
    if r == ZERO:
        return money(pmt * n)
    # factor = (1 - (1+r)^-n) / r
    one_plus = Decimal("1") + r
    factor = (Decimal("1") - (one_plus ** Decimal(str(-n)))) / r
    if timing == "advance":
        # First payment at commencement (undiscounted) + annuity for n-1
        if n == 1:
            return money(pmt)
        factor_n1 = (Decimal("1") - (one_plus ** Decimal(str(-(n - 1))))) / r
        return money(pmt + pmt * factor_n1)
    return money(pmt * factor)


def _add_months(iso: str, months: int) -> str:
    d = date.fromisoformat(iso[:10])
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day).isoformat()


def build_schedule(
    *,
    commencement: str,
    payment: Decimal,
    term_months: int,
    annual_pct: Decimal,
    timing: str,
    rou_cost: Decimal,
    opening_liability: Decimal,
) -> list[ScheduleRow]:
    """Build amortisation + straight-line RoU depreciation schedule."""
    n = int(term_months)
    pmt = money(payment)
    r = monthly_rate(annual_pct)
    depr_each = money(D(rou_cost) / n) if n > 0 else ZERO
    rows: list[ScheduleRow] = []
    opening = money(opening_liability)
    depr_accum = ZERO

    for i in range(1, n + 1):
        offset = (i - 1) if timing == "advance" else i
        period_date = _add_months(commencement, offset)

        if i < n:
            interest = money(opening * r) if r else ZERO
            principal = money(pmt - interest)
            closing = money(opening + interest - pmt)
            depr = depr_each
            depr_accum = money(depr_accum + depr)
        else:
            # Final period clears liability; residual RoU depr takes the remainder.
            # interest chosen so opening + interest - payment = 0.
            interest = money(pmt - opening)
            if interest < ZERO:
                interest = ZERO
            closing = money(opening + interest - pmt)
            if closing != ZERO:
                interest = money(interest - closing)
                closing = ZERO
            principal = money(pmt - interest)
            depr = money(D(rou_cost) - depr_accum)

        rows.append(ScheduleRow(
            period_index=i, period_date=period_date,
            opening_liability=opening, interest=interest, payment=pmt,
            principal=principal, closing_liability=closing, depreciation=depr,
        ))
        opening = closing

    return rows


def preview_lease(
    payment: Decimal,
    term_months: int,
    annual_pct: Decimal,
    timing: str = "arrears",
    initial_direct_costs: Decimal = ZERO,
    commencement: str = "2026-01-01",
) -> dict:
    pv = present_value_of_lease(payment, term_months, annual_pct, timing)
    idc = money(initial_direct_costs)
    rou = money(pv + idc)
    schedule = build_schedule(
        commencement=commencement,
        payment=payment,
        term_months=term_months,
        annual_pct=annual_pct,
        timing=timing,
        rou_cost=rou,
        opening_liability=pv,
    )
    return {
        "present_value": float(pv),
        "rou_cost": float(rou),
        "liability_opening": float(pv),
        "schedule": [
            {
                "period_index": r.period_index,
                "period_date": r.period_date,
                "opening_liability": float(r.opening_liability),
                "interest": float(r.interest),
                "payment": float(r.payment),
                "principal": float(r.principal),
                "closing_liability": float(r.closing_liability),
                "depreciation": float(r.depreciation),
            }
            for r in schedule
        ],
    }


def _resolve_accounts(session: Session, lease: LeaseContract, tenant_id: int, payment_account_id: Optional[int]):
    from models import Account

    rou = get_or_create_account(session, tenant_id, "1510", "Right-of-use Asset", "Asset")
    accum = get_or_create_account(session, tenant_id, "1511", "Accum. Dep. — RoU", "Asset")
    depr = get_or_create_account(session, tenant_id, "5050", "Depreciation Expense", "Expense")
    liab = get_or_create_account(session, tenant_id, "2510", "Lease Liability", "Liability")
    interest = get_or_create_account(session, tenant_id, "5125", "Lease Interest Expense", "Expense")
    if payment_account_id:
        pay = session.exec(
            select(Account).where(Account.id == payment_account_id, Account.tenant_id == tenant_id)
        ).first()
        if not pay:
            raise LeaseError("payment_account_id not found for this tenant")
    else:
        pay = get_or_create_account(session, tenant_id, "1010", "Bank", "Asset")
    lease.rou_account_id = rou.id
    lease.accum_depr_account_id = accum.id
    lease.depr_expense_account_id = depr.id
    lease.liability_account_id = liab.id
    lease.interest_expense_account_id = interest.id
    lease.payment_account_id = pay.id
    return rou, accum, depr, liab, interest, pay


def activate_lease(
    session: Session,
    user: User,
    lease: LeaseContract,
    *,
    payment_account_id: Optional[int] = None,
) -> LeaseContract:
    if lease.status != "draft":
        raise LeaseError("Only draft leases can be activated")
    if lease.term_months <= 0:
        raise LeaseError("term_months must be > 0")
    if D(lease.payment_amount) <= ZERO:
        raise LeaseError("payment_amount must be > 0")

    timing = lease.payment_timing or "arrears"
    pv = present_value_of_lease(
        lease.payment_amount, lease.term_months, lease.annual_discount_rate, timing,
    )
    idc = money(lease.initial_direct_costs)
    rou_cost = money(pv + idc)

    rou, accum, depr, liab, interest, pay = _resolve_accounts(
        session, lease, user.tenant_id, payment_account_id or lease.payment_account_id,
    )

    # Initial recognition JE
    entries = [
        EntryInput(account_id=rou.id, debit=rou_cost),
        EntryInput(account_id=liab.id, credit=pv),
    ]
    if idc > ZERO:
        entries.append(EntryInput(account_id=pay.id, credit=idc))
    # If idc == 0, Rou == PV and entries balance. If idc > 0, Dr Rou / Cr Liab / Cr Bank.

    try:
        txn = post_transaction(
            session, user,
            date=lease.commencement_date,
            description=f"Lease commencement — {lease.number} {lease.name}",
            entries=entries,
            voucher_type="JV",
            audit_entity_type="lease",
            audit_detail={"lease_id": lease.id, "pv": str(pv), "rou": str(rou_cost)},
        )
    except PostingError as e:
        raise LeaseError(str(e)) from e

    lease.present_value = pv
    lease.rou_cost = rou_cost
    lease.liability_opening = pv
    lease.liability_carrying = pv
    lease.accumulated_depreciation = ZERO
    lease.initial_transaction_id = txn.id
    lease.status = "active"

    # Persist schedule
    for row in build_schedule(
        commencement=lease.commencement_date,
        payment=D(lease.payment_amount),
        term_months=lease.term_months,
        annual_pct=D(lease.annual_discount_rate),
        timing=timing,
        rou_cost=rou_cost,
        opening_liability=pv,
    ):
        session.add(LeaseScheduleLine(
            tenant_id=user.tenant_id,
            lease_id=lease.id,
            period_index=row.period_index,
            period_date=row.period_date,
            opening_liability=row.opening_liability,
            interest=row.interest,
            payment=row.payment,
            principal=row.principal,
            closing_liability=row.closing_liability,
            depreciation=row.depreciation,
            status="pending",
        ))

    session.add(lease)
    session.commit()
    session.refresh(lease)
    return lease


def post_period(
    session: Session,
    user: User,
    lease: LeaseContract,
    line: LeaseScheduleLine,
) -> LeaseScheduleLine:
    if lease.status != "active":
        raise LeaseError("Lease is not active")
    if line.status != "pending":
        raise LeaseError("Period already posted")
    if line.lease_id != lease.id:
        raise LeaseError("Schedule line mismatch")

    # Prior periods must be posted in order
    prior = session.exec(
        select(LeaseScheduleLine).where(
            LeaseScheduleLine.lease_id == lease.id,
            LeaseScheduleLine.period_index < line.period_index,
            LeaseScheduleLine.status == "pending",
        )
    ).first()
    if prior:
        raise LeaseError(f"Post period {prior.period_index} first")

    try:
        # 1) Interest accretion
        if D(line.interest) > ZERO:
            t_int = post_transaction(
                session, user,
                date=line.period_date,
                description=f"{lease.number} interest P{line.period_index}",
                entries=[
                    EntryInput(account_id=lease.interest_expense_account_id, debit=D(line.interest)),
                    EntryInput(account_id=lease.liability_account_id, credit=D(line.interest)),
                ],
                audit_entity_type="lease",
                audit_detail={"lease_id": lease.id, "period": line.period_index, "kind": "interest"},
            )
            line.interest_transaction_id = t_int.id

        # 2) Payment
        if D(line.payment) > ZERO:
            t_pay = post_transaction(
                session, user,
                date=line.period_date,
                description=f"{lease.number} payment P{line.period_index}",
                entries=[
                    EntryInput(account_id=lease.liability_account_id, debit=D(line.payment)),
                    EntryInput(account_id=lease.payment_account_id, credit=D(line.payment)),
                ],
                audit_entity_type="lease",
                audit_detail={"lease_id": lease.id, "period": line.period_index, "kind": "payment"},
            )
            line.payment_transaction_id = t_pay.id

        # 3) RoU depreciation
        if D(line.depreciation) > ZERO:
            t_dep = post_transaction(
                session, user,
                date=line.period_date,
                description=f"{lease.number} RoU depreciation P{line.period_index}",
                entries=[
                    EntryInput(account_id=lease.depr_expense_account_id, debit=D(line.depreciation)),
                    EntryInput(account_id=lease.accum_depr_account_id, credit=D(line.depreciation)),
                ],
                audit_entity_type="lease",
                audit_detail={"lease_id": lease.id, "period": line.period_index, "kind": "depreciation"},
            )
            line.depr_transaction_id = t_dep.id
    except PostingError as e:
        raise LeaseError(str(e)) from e

    line.status = "posted"
    line.posted_at = datetime.utcnow()
    lease.liability_carrying = money(line.closing_liability)
    lease.accumulated_depreciation = money(
        D(lease.accumulated_depreciation) + D(line.depreciation)
    )
    session.add(line)
    session.add(lease)
    session.commit()
    session.refresh(line)
    return line


def terminate_lease(
    session: Session,
    user: User,
    lease: LeaseContract,
    *,
    termination_date: str,
) -> LeaseContract:
    """Simplified early termination — clear remaining RoU NBV and liability to P&L."""
    if lease.status != "active":
        raise LeaseError("Only active leases can be terminated")

    remaining_liab = money(lease.liability_carrying)
    rou_nbv = money(D(lease.rou_cost) - D(lease.accumulated_depreciation))
    gain_loss = money(remaining_liab - rou_nbv)  # positive = gain (Cr P&L)

    other = get_or_create_account(
        session, user.tenant_id, "5900", "Other Expenses", "Expense",
    )
    income = get_or_create_account(
        session, user.tenant_id, "4900", "Other Income", "Revenue",
    )

    entries: list[EntryInput] = []
    # Clear liability
    if remaining_liab > ZERO:
        entries.append(EntryInput(account_id=lease.liability_account_id, debit=remaining_liab))
    elif remaining_liab < ZERO:
        entries.append(EntryInput(account_id=lease.liability_account_id, credit=-remaining_liab))
    # Clear accum depr + RoU
    if D(lease.accumulated_depreciation) > ZERO:
        entries.append(
            EntryInput(account_id=lease.accum_depr_account_id, debit=D(lease.accumulated_depreciation))
        )
    if D(lease.rou_cost) > ZERO:
        entries.append(EntryInput(account_id=lease.rou_account_id, credit=D(lease.rou_cost)))
    # Balancing gain/loss
    # Net of above: Dr Liab + Dr Accum - Cr RoU = remaining_liab + accum - rou = remaining_liab - rou_nbv = gain_loss
    # If gain_loss > 0 we have excess debit → Cr income; if < 0 excess credit → Dr expense
    if gain_loss > ZERO:
        entries.append(EntryInput(account_id=income.id, credit=gain_loss))
    elif gain_loss < ZERO:
        entries.append(EntryInput(account_id=other.id, debit=-gain_loss))

    # Drop zero-side noise
    entries = [e for e in entries if D(e.debit) > ZERO or D(e.credit) > ZERO]
    if not entries:
        lease.status = "terminated"
        lease.terminated_at = termination_date
        session.add(lease)
        session.commit()
        session.refresh(lease)
        return lease

    try:
        txn = post_transaction(
            session, user,
            date=termination_date,
            description=f"Lease termination — {lease.number}",
            entries=entries,
            audit_entity_type="lease",
            audit_detail={"lease_id": lease.id, "kind": "terminate"},
        )
    except PostingError as e:
        raise LeaseError(str(e)) from e

    # Cancel pending schedule lines
    pending = session.exec(
        select(LeaseScheduleLine).where(
            LeaseScheduleLine.lease_id == lease.id,
            LeaseScheduleLine.status == "pending",
        )
    ).all()
    for p in pending:
        session.delete(p)

    lease.status = "terminated"
    lease.terminated_at = termination_date
    lease.termination_transaction_id = txn.id
    lease.liability_carrying = ZERO
    session.add(lease)
    session.commit()
    session.refresh(lease)
    return lease


def maturity_analysis(session: Session, tenant_id: int, as_of: Optional[str] = None) -> dict:
    """Disclosure: undiscounted lease payments by maturity bucket (IFRS 16.58)."""
    as_of = as_of or date.today().isoformat()
    lines = session.exec(
        select(LeaseScheduleLine, LeaseContract)
        .join(LeaseContract, LeaseContract.id == LeaseScheduleLine.lease_id)
        .where(
            LeaseScheduleLine.tenant_id == tenant_id,
            LeaseScheduleLine.status == "pending",
            LeaseContract.status == "active",
            LeaseScheduleLine.period_date >= as_of,
        )
        .order_by(LeaseScheduleLine.period_date)
    ).all()

    buckets = {
        "within_1_year": ZERO,
        "years_1_to_5": ZERO,
        "after_5_years": ZERO,
        "total": ZERO,
    }
    detail = []
    as_of_d = date.fromisoformat(as_of[:10])
    for line, lease in lines:
        pmt = D(line.payment)
        buckets["total"] += pmt
        pd = date.fromisoformat(line.period_date[:10])
        days = (pd - as_of_d).days
        if days <= 365:
            buckets["within_1_year"] += pmt
            bucket = "within_1_year"
        elif days <= 365 * 5:
            buckets["years_1_to_5"] += pmt
            bucket = "years_1_to_5"
        else:
            buckets["after_5_years"] += pmt
            bucket = "after_5_years"
        detail.append({
            "lease_id": lease.id,
            "lease_number": lease.number,
            "lease_name": lease.name,
            "period_date": line.period_date,
            "payment": float(pmt),
            "bucket": bucket,
        })

    return {
        "as_of": as_of,
        "buckets": {k: float(v) for k, v in buckets.items()},
        "detail": detail,
    }


def allocate_number(session: Session, tenant_id: int) -> str:
    year = date.today().year
    return next_number(
        session, tenant_id, f"lease_{year}", f"LS-{year}", width=4,
    )
