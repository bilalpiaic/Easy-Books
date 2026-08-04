"""Pure maths helpers for the Textile Processing module."""
from __future__ import annotations

from decimal import Decimal

from services.money import D, ZERO, money


def ready_mtr(
    grey_mtr: Decimal | float | str,
    l_kami_mtr: Decimal | float | str = ZERO,
    rejection_mtr: Decimal | float | str = ZERO,
    safai_mtr: Decimal | float | str = ZERO,
) -> Decimal:
    """Safi / ready = grey − L-Kami − Rejection − Safai (mending loss)."""
    g = D(grey_mtr)
    ready = g - D(l_kami_mtr) - D(rejection_mtr) - D(safai_mtr)
    if ready < ZERO:
        raise ValueError("ready_mtr cannot be negative — check mending components")
    return money(ready)


def stage_balance_ok(
    input_mtr: Decimal | float | str,
    output_mtr: Decimal | float | str,
    visible_wastage_mtr: Decimal | float | str = ZERO,
    invisible_wastage_mtr: Decimal | float | str = ZERO,
    *,
    tolerance: Decimal | float | str = Decimal("0.01"),
) -> bool:
    """input ≈ output + visible + invisible (± tolerance)."""
    left = D(input_mtr)
    right = D(output_mtr) + D(visible_wastage_mtr) + D(invisible_wastage_mtr)
    return abs(left - right) <= D(tolerance)


def loss_mtr(
    visible_wastage_mtr: Decimal | float | str = ZERO,
    invisible_wastage_mtr: Decimal | float | str = ZERO,
) -> Decimal:
    return money(D(visible_wastage_mtr) + D(invisible_wastage_mtr))


def settlement_credit(
    total_grey_received: Decimal | float | str,
    fresh_dispatch_mtr: Decimal | float | str,
    visible_wastage_mtr: Decimal | float | str,
    invisible_wastage_mtr: Decimal | float | str,
    grey_rate: Decimal | float | str,
) -> tuple[Decimal, Decimal]:
    """
    credit_qty = total − fresh_dispatch − (Σ visible + Σ invisible)
    credit_value = credit_qty × grey_rate
    """
    process_wastage = D(visible_wastage_mtr) + D(invisible_wastage_mtr)
    credit_qty = D(total_grey_received) - D(fresh_dispatch_mtr) - process_wastage
    if credit_qty < ZERO:
        raise ValueError("credit_qty_mtr cannot be negative — check settlement inputs")
    credit_value = money(credit_qty * D(grey_rate))
    return money(credit_qty), credit_value


def rej_note_balance(issued_mtr: Decimal | float | str, lifted_mtr: Decimal | float | str) -> Decimal:
    bal = D(issued_mtr) - D(lifted_mtr)
    if bal < ZERO:
        raise ValueError("lifted_mtr cannot exceed issued_mtr")
    return money(bal)


def rej_note_status(issued_mtr: Decimal | float | str, lifted_mtr: Decimal | float | str) -> str:
    issued = D(issued_mtr)
    lifted = D(lifted_mtr)
    if lifted <= ZERO:
        return "issued"
    if lifted + Decimal("0.0001") >= issued:
        return "lifted"
    return "partially_lifted"
