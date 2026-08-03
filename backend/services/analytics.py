"""Analytic dimension helpers (#260).

Maps up to 3 dimension slots onto JournalEntry.analytic_account_id /
analytic_2_id / analytic_3_id, and provides document-level packing helpers.
"""
from __future__ import annotations

from typing import Optional, Sequence

from sqlmodel import Session, select

from models import AnalyticAccount, AnalyticDimension


def pack_analytics(
    *,
    analytic_account_id: Optional[int] = None,
    analytic_2_id: Optional[int] = None,
    analytic_3_id: Optional[int] = None,
    analytic_ids: Optional[Sequence[Optional[int]]] = None,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Resolve the three JE analytic slots from explicit fields and/or a list.

    `analytic_ids` fills empty slots by index (0→slot1, 1→slot2, 2→slot3).
    Explicit non-None fields win over list positions.
    """
    a1, a2, a3 = analytic_account_id, analytic_2_id, analytic_3_id
    if analytic_ids is not None:
        ids = list(analytic_ids)[:3]
        while len(ids) < 3:
            ids.append(None)
        if a1 is None:
            a1 = ids[0]
        if a2 is None:
            a2 = ids[1]
        if a3 is None:
            a3 = ids[2]
    return a1, a2, a3


def slot_for_sort_order(sort_order: int, a1, a2, a3) -> Optional[int]:
    if sort_order == 0:
        return a1
    if sort_order == 1:
        return a2
    if sort_order == 2:
        return a3
    return None


def ensure_legacy_dimension(session: Session, tenant_id: int) -> list[AnalyticDimension]:
    """If the tenant has analytic accounts but no dimensions, create Cost Center
    and attach existing values. Idempotent."""
    dims = list(
        session.exec(
            select(AnalyticDimension)
            .where(AnalyticDimension.tenant_id == tenant_id)
            .order_by(AnalyticDimension.sort_order)
        ).all()
    )
    if dims:
        return dims
    accounts = session.exec(
        select(AnalyticAccount).where(AnalyticAccount.tenant_id == tenant_id)
    ).all()
    if not accounts:
        return []
    dim = AnalyticDimension(
        tenant_id=tenant_id,
        code="CC",
        name="Cost Center",
        required=False,
        sort_order=0,
        is_active=True,
    )
    session.add(dim)
    session.flush()
    for aa in accounts:
        if aa.dimension_id is None:
            aa.dimension_id = dim.id
            session.add(aa)
    session.flush()
    return [dim]


def required_dimensions(session: Session, tenant_id: int) -> list[AnalyticDimension]:
    return list(
        session.exec(
            select(AnalyticDimension).where(
                AnalyticDimension.tenant_id == tenant_id,
                AnalyticDimension.is_active == True,  # noqa: E712
                AnalyticDimension.required == True,  # noqa: E712
            )
        ).all()
    )
