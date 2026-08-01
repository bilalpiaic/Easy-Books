"""Multi-jurisdiction tax calculation (#263).

Resolves effective-dated rates from TaxRateHistory, computes line tax
(exclusive/inclusive, reverse-charge, exempt), and aggregates GL legs.
Document routers snapshot results onto InvoiceLine / BillLine — never
re-derive historical tax from the live catalog.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable, Optional

from sqlmodel import Session, select

from models import TaxCode, TaxRateHistory
from services.money import ZERO, money


D = Decimal


@dataclass(frozen=True)
class LineTaxResult:
    """Result of taxing one document line."""

    net: Decimal
    tax: Decimal
    rate: Decimal
    include_in_total: bool
    """False for reverse-charge — tax is reported but not added to doc total / GL."""
    gl_account_id: Optional[int]
    """None when no GL tax leg should post (RC, exempt with zero, or no code)."""
    is_reverse_charge: bool
    is_exempt: bool
    is_zero_rated: bool


@dataclass(frozen=True)
class DocumentTaxAggregate:
    per_gl_tax: dict[int, Decimal]
    total_tax_in_total: Decimal
    total_tax_rc_only: Decimal
    taxable_base: Decimal


def _as_date_str(on_date: date | str) -> str:
    if isinstance(on_date, date):
        return on_date.isoformat()
    return str(on_date)[:10]


def resolve_rate(
    session: Session,
    tax_code_id: int,
    on_date: date | str,
    *,
    fallback_rate: Optional[Decimal] = None,
) -> Decimal:
    """Pick the TaxRateHistory row covering on_date; fall back to TaxCode.rate."""
    d = _as_date_str(on_date)
    rows = session.exec(
        select(TaxRateHistory)
        .where(TaxRateHistory.tax_code_id == tax_code_id)
        .order_by(TaxRateHistory.effective_from.desc())
    ).all()
    for row in rows:
        if row.effective_from <= d and (row.effective_to is None or d <= row.effective_to):
            return D(row.rate)
    if fallback_rate is not None:
        return D(fallback_rate)
    tc = session.get(TaxCode, tax_code_id)
    if tc is None:
        return ZERO
    return D(tc.rate)


def compute_line_tax(
    amount: Decimal,
    rate: Decimal,
    *,
    inclusive: bool = False,
    reverse_charge: bool = False,
    exempt: bool = False,
    zero_rated: bool = False,
    gl_account_id: Optional[int] = None,
) -> LineTaxResult:
    """Split net/tax from a line amount.

    `amount` is the stored line amount (qty×rate×discount). When inclusive,
    that figure is gross; otherwise it is net.
    """
    amt = D(amount)
    r = D(rate)
    if exempt or zero_rated:
        r = ZERO

    if inclusive and r > 0:
        net = money(amt * D("100") / (D("100") + r))
        tax = money(amt - net)
    elif r > 0:
        net = money(amt)
        tax = money(amt * r / D("100"))
    else:
        net = money(amt)
        tax = ZERO

    include_in_total = not reverse_charge
    # RC: report tax but no payable/receivable leg on this document.
    post_gl = gl_account_id if (tax > 0 and not reverse_charge) else None

    return LineTaxResult(
        net=net,
        tax=tax,
        rate=r,
        include_in_total=include_in_total,
        gl_account_id=post_gl,
        is_reverse_charge=reverse_charge,
        is_exempt=exempt,
        is_zero_rated=zero_rated or (r == 0 and not exempt),
    )


def tax_line_from_code(
    session: Session,
    *,
    tax_code: TaxCode,
    amount: Decimal,
    on_date: date | str,
    inclusive: bool = False,
) -> LineTaxResult:
    rate = resolve_rate(session, tax_code.id, on_date, fallback_rate=D(tax_code.rate))
    return compute_line_tax(
        amount,
        rate,
        inclusive=inclusive,
        reverse_charge=bool(tax_code.is_reverse_charge),
        exempt=bool(tax_code.is_exempt),
        zero_rated=bool(tax_code.is_zero_rated),
        gl_account_id=tax_code.gl_account_id,
    )


def aggregate_document_taxes(results: Iterable[LineTaxResult]) -> DocumentTaxAggregate:
    per_gl: dict[int, Decimal] = {}
    in_total = ZERO
    rc_only = ZERO
    base = ZERO
    for r in results:
        base = money(base + r.net)
        if r.include_in_total:
            in_total = money(in_total + r.tax)
        elif r.tax > 0:
            rc_only = money(rc_only + r.tax)
        if r.gl_account_id is not None and r.tax > 0:
            per_gl[r.gl_account_id] = money(per_gl.get(r.gl_account_id, ZERO) + r.tax)
    return DocumentTaxAggregate(
        per_gl_tax=per_gl,
        total_tax_in_total=in_total,
        total_tax_rc_only=rc_only,
        taxable_base=base,
    )


def set_tax_code_rate(
    session: Session,
    tax_code: TaxCode,
    new_rate: Decimal,
    *,
    effective_from: str,
) -> TaxRateHistory:
    """Close the open history row and open a new one; sync TaxCode.rate."""
    d = _as_date_str(effective_from)
    open_rows = session.exec(
        select(TaxRateHistory).where(
            TaxRateHistory.tax_code_id == tax_code.id,
            TaxRateHistory.effective_to.is_(None),  # type: ignore[attr-defined]
        )
    ).all()
    # effective_to is day before new from (string dates YYYY-MM-DD sortable).
    from datetime import datetime, timedelta

    prev_end = (datetime.strptime(d, "%Y-%m-%d").date() - timedelta(days=1)).isoformat()
    for row in open_rows:
        if row.effective_from >= d:
            # Same-day replace: delete superseding open row
            session.delete(row)
        else:
            row.effective_to = prev_end
            session.add(row)

    hist = TaxRateHistory(
        tax_code_id=tax_code.id,
        rate=money(D(new_rate)),
        effective_from=d,
        effective_to=None,
    )
    session.add(hist)
    tax_code.rate = money(D(new_rate))
    session.add(tax_code)
    session.flush()
    return hist


def ensure_initial_rate_history(session: Session, tax_code: TaxCode) -> None:
    """Ensure a new TaxCode has an open-ended history row."""
    exists = session.exec(
        select(TaxRateHistory).where(TaxRateHistory.tax_code_id == tax_code.id)
    ).first()
    if exists:
        return
    session.add(
        TaxRateHistory(
            tax_code_id=tax_code.id,
            rate=money(D(tax_code.rate)),
            effective_from="1900-01-01",
            effective_to=None,
        )
    )
    session.flush()


def prepare_line_taxes(
    session: Session,
    tenant_id: int,
    on_date: date | str,
    line_specs: Iterable[tuple[Decimal, Optional[int], bool]],
) -> tuple[list[LineTaxResult | None], DocumentTaxAggregate, bool]:
    """For each (amount, tax_code_id|None, inclusive) return per-line results.

    Returns (results_aligned_with_specs, aggregate, use_per_line_tax).
    When no line has a tax_code_id, use_per_line_tax is False and results are all None
    — caller should fall back to header gst_rate.
    """
    results: list[LineTaxResult | None] = []
    any_code = False
    for amount, tax_code_id, inclusive in line_specs:
        if not tax_code_id:
            results.append(None)
            continue
        tc = session.exec(
            select(TaxCode).where(
                TaxCode.id == tax_code_id,
                TaxCode.tenant_id == tenant_id,
            )
        ).first()
        if not tc:
            results.append(None)
            continue
        any_code = True
        results.append(
            tax_line_from_code(
                session,
                tax_code=tc,
                amount=D(amount),
                on_date=on_date,
                inclusive=inclusive,
            )
        )
    concrete = [r for r in results if r is not None]
    agg = aggregate_document_taxes(concrete)
    return results, agg, any_code and bool(concrete)
