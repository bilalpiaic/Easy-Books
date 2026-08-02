"""Multi-entity consolidation engine (IFRS 10 / IAS 27) — #255.

Worksheet-only: aggregations and eliminations never post to member GLs.
Account codes are assumed aligned across the group (shared CoA skeleton).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from models import (
    Account,
    AccountingPeriod,
    ConsolidationElimination,
    ConsolidationMember,
    ConsolidationRun,
    JournalEntry,
    Settings,
    Tenant,
    TenantMembership,
    Transaction,
    User,
)
from services.account_tree import build_account_tree
from services.money import D, ZERO, money


OVERRIDE_ROLES = frozenset({"owner", "admin"})
NCI_CODE = "NCI"
NCI_NAME = "Non-controlling interests"
ASSOC_INV_CODE = "ASSOC-INV"
ASSOC_INV_NAME = "Investment in associates (equity method)"


class ConsolError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class LeafAgg:
    code: str
    name: str
    type: str
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    account_id: Optional[int] = None  # holding CoA id when known


@dataclass
class MemberSnapshot:
    member: ConsolidationMember
    tenant_name: str
    leaves: dict[str, LeafAgg] = field(default_factory=dict)
    net_assets: Decimal = ZERO  # equity + RE-CUR (credit-normal)
    period_pnl: Decimal = ZERO


def _setting(session: Session, tenant_id: int, key: str, default: str = "") -> str:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return (row.value if row else default) or default


def user_can_access_tenant(session: Session, user_id: int, tenant_id: int) -> bool:
    return session.exec(
        select(TenantMembership).where(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
    ).first() is not None


def ensure_parent_member(session: Session, holding_tenant_id: int) -> ConsolidationMember:
    row = session.exec(
        select(ConsolidationMember).where(
            ConsolidationMember.holding_tenant_id == holding_tenant_id,
            ConsolidationMember.member_tenant_id == holding_tenant_id,
        )
    ).first()
    if row:
        return row
    t = session.get(Tenant, holding_tenant_id)
    row = ConsolidationMember(
        holding_tenant_id=holding_tenant_id,
        member_tenant_id=holding_tenant_id,
        relationship="parent",
        ownership_pct=Decimal("100"),
        label=(t.name if t else None) or "Parent",
        is_active=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_members(session: Session, holding_tenant_id: int) -> list[ConsolidationMember]:
    ensure_parent_member(session, holding_tenant_id)
    return list(session.exec(
        select(ConsolidationMember)
        .where(ConsolidationMember.holding_tenant_id == holding_tenant_id)
        .order_by(ConsolidationMember.id)
    ).all())


def eligible_tenants(session: Session, user: User) -> list[dict]:
    """Tenants the user can attach as consolidation members (via membership)."""
    rows = session.exec(
        select(TenantMembership, Tenant)
        .join(Tenant, Tenant.id == TenantMembership.tenant_id)
        .where(TenantMembership.user_id == user.id)
        .order_by(Tenant.id)
    ).all()
    existing = {
        m.member_tenant_id
        for m in session.exec(
            select(ConsolidationMember).where(
                ConsolidationMember.holding_tenant_id == user.tenant_id
            )
        ).all()
    }
    out = []
    for mem, tenant in rows:
        out.append({
            "tenant_id": tenant.id,
            "name": tenant.name,
            "role": mem.role,
            "already_member": tenant.id in existing,
            "is_holding": tenant.id == user.tenant_id,
        })
    return out


def _tb_rows(session: Session, tenant_id: int, start: str, end: str):
    q = (
        select(
            Account.id,
            Account.code,
            Account.name,
            Account.type,
            func.sum(JournalEntry.debit).label("total_debit"),
            func.sum(JournalEntry.credit).label("total_credit"),
        )
        .join(JournalEntry, JournalEntry.account_id == Account.id)
        .join(Transaction, Transaction.id == JournalEntry.transaction_id)
        .where(Transaction.tenant_id == tenant_id)
        .where(Transaction.date >= start)
        .where(Transaction.date <= end)
        .group_by(Account.id)
    )
    return session.exec(q).all()


def _signed_balance(atype: str, debit: Decimal, credit: Decimal) -> Decimal:
    """Normal balance sign: Asset/Expense debit-normal; others credit-normal."""
    if atype in ("Asset", "Expense"):
        return debit - credit
    return credit - debit


def snapshot_member(
    session: Session, member: ConsolidationMember, start: str, end: str,
) -> MemberSnapshot:
    tenant = session.get(Tenant, member.member_tenant_id)
    snap = MemberSnapshot(
        member=member,
        tenant_name=(tenant.name if tenant else None) or f"Tenant {member.member_tenant_id}",
    )
    for r in _tb_rows(session, member.member_tenant_id, start, end):
        debit, credit = D(r.total_debit or 0), D(r.total_credit or 0)
        if debit == ZERO and credit == ZERO:
            continue
        snap.leaves[r.code] = LeafAgg(
            code=r.code, name=r.name, type=r.type,
            debit=debit, credit=credit, account_id=r.id,
        )
        if r.type in ("Equity",):
            snap.net_assets += credit - debit
        elif r.type == "Revenue":
            snap.period_pnl += credit - debit
        elif r.type == "Expense":
            snap.period_pnl -= debit - credit
        elif r.type == "Liability":
            # liabilities reduce net assets when computing NCI from BS view —
            # we use equity + period P&L only (standard for ownership of equity).
            pass
        elif r.type == "Asset":
            pass
    # Net assets for NCI ≈ equity book + current-period P&L (RE-CUR)
    # Plus we also need liability/asset? IFRS NCI = share of net assets = A - L.
    # Compute proper net assets = assets - liabilities (= equity + RE-CUR).
    assets = sum(
        (_signed_balance("Asset", L.debit, L.credit) for L in snap.leaves.values() if L.type == "Asset"),
        ZERO,
    )
    liabilities = sum(
        (_signed_balance("Liability", L.debit, L.credit) for L in snap.leaves.values() if L.type == "Liability"),
        ZERO,
    )
    equity = sum(
        (_signed_balance("Equity", L.debit, L.credit) for L in snap.leaves.values() if L.type == "Equity"),
        ZERO,
    )
    # Prefer A−L; falls back to equity+pnl when BS incomplete
    net = assets - liabilities
    if net == ZERO and (equity != ZERO or snap.period_pnl != ZERO):
        net = equity + snap.period_pnl
    else:
        # A−L already embeds P&L through retained earnings movements in the period
        # when start is fiscal open; for a mid-year window A−L is period-only.
        # For consolidation packages we use equity + period P&L when the window
        # is P&L-scoped; when start is None-like empty, A−L is better.
        # Here period is always bounded — use equity + period_pnl for NCI base.
        net = equity + snap.period_pnl
    snap.net_assets = money(net)
    return snap


def _holding_accounts_by_code(session: Session, holding_tenant_id: int) -> dict[str, Account]:
    return {
        a.code: a
        for a in session.exec(
            select(Account).where(Account.tenant_id == holding_tenant_id)
        ).all()
    }


def aggregate_line_by_line(
    snaps: list[MemberSnapshot],
) -> dict[str, LeafAgg]:
    """Sum parent + subsidiary leaves by account code. Associates excluded."""
    agg: dict[str, LeafAgg] = {}
    for snap in snaps:
        rel = snap.member.relationship
        if rel == "associate":
            continue
        for code, leaf in snap.leaves.items():
            cur = agg.get(code)
            if not cur:
                agg[code] = LeafAgg(
                    code=leaf.code, name=leaf.name, type=leaf.type,
                    debit=leaf.debit, credit=leaf.credit,
                )
            else:
                cur.debit += leaf.debit
                cur.credit += leaf.credit
                if not cur.name:
                    cur.name = leaf.name
    return agg


def apply_associate_pickups(
    agg: dict[str, LeafAgg], snaps: list[MemberSnapshot],
) -> list[tuple[str, Decimal]]:
    """Equity-method one-liner: ownership % of associate net assets → investment asset."""
    pickups: list[tuple[str, Decimal]] = []
    total = ZERO
    for snap in snaps:
        if snap.member.relationship != "associate" or not snap.member.is_active:
            continue
        pct = D(snap.member.ownership_pct or 0) / Decimal("100")
        amt = money(snap.net_assets * pct)
        if amt == ZERO:
            continue
        total += amt
        pickups.append((snap.tenant_name, amt))
    if total != ZERO:
        cur = agg.get(ASSOC_INV_CODE)
        if not cur:
            agg[ASSOC_INV_CODE] = LeafAgg(
                code=ASSOC_INV_CODE, name=ASSOC_INV_NAME, type="Asset",
                debit=total if total > ZERO else ZERO,
                credit=(-total if total < ZERO else ZERO),
            )
        else:
            if total > ZERO:
                cur.debit += total
            else:
                cur.credit += -total
    return pickups


def _elim_line(
    *,
    holding_tenant_id: int,
    run_id: int,
    kind: str,
    description: str,
    account_code: str,
    account_name: str,
    account_type: str,
    debit: Decimal = ZERO,
    credit: Decimal = ZERO,
    member_tenant_id: Optional[int] = None,
    sort_order: int = 0,
) -> ConsolidationElimination:
    return ConsolidationElimination(
        holding_tenant_id=holding_tenant_id,
        run_id=run_id,
        kind=kind,
        description=description,
        account_code=account_code,
        account_name=account_name,
        account_type=account_type,
        debit=money(debit),
        credit=money(credit),
        member_tenant_id=member_tenant_id,
        sort_order=sort_order,
    )


def propose_eliminations(
    session: Session,
    run: ConsolidationRun,
    snaps: list[MemberSnapshot],
) -> list[ConsolidationElimination]:
    """Replace auto-kinds on a draft run; keep manual lines."""
    if run.status != "draft":
        raise ConsolError("Can only propose eliminations on a draft run")

    # Drop prior auto lines
    existing = session.exec(
        select(ConsolidationElimination).where(
            ConsolidationElimination.run_id == run.id,
        )
    ).all()
    for row in existing:
        if row.kind != "manual":
            session.delete(row)
    session.flush()

    lines: list[ConsolidationElimination] = []
    sort_i = 0
    holding_id = run.holding_tenant_id

    # ── IC balances (pair AR/AP codes across members) ─────────────────────
    # Match each member's IC AR against every other member's IC AP at the
    # smaller absolute balance (worksheet elim).
    members_with_ic = [
        s for s in snaps
        if s.member.is_active and s.member.relationship != "associate"
        and (s.member.ic_ar_code or s.member.ic_ap_code)
    ]
    for a in members_with_ic:
        ar_code = (a.member.ic_ar_code or "").strip()
        if not ar_code:
            continue
        ar_leaf = a.leaves.get(ar_code)
        ar_bal = _signed_balance("Asset", ar_leaf.debit, ar_leaf.credit) if ar_leaf else ZERO
        if ar_bal <= ZERO:
            continue
        for b in members_with_ic:
            if a.member.id == b.member.id:
                continue
            ap_code = (b.member.ic_ap_code or "").strip()
            if not ap_code:
                continue
            ap_leaf = b.leaves.get(ap_code)
            ap_bal = _signed_balance("Liability", ap_leaf.debit, ap_leaf.credit) if ap_leaf else ZERO
            if ap_bal <= ZERO:
                continue
            amt = money(min(ar_bal, ap_bal))
            if amt <= ZERO:
                continue
            desc = (
                f"Eliminate IC balance {a.tenant_name} AR {ar_code} ↔ "
                f"{b.tenant_name} AP {ap_code}"
            )
            lines.append(_elim_line(
                holding_tenant_id=holding_id, run_id=run.id, kind="ic_balance",
                description=desc, account_code=ap_code,
                account_name=ap_leaf.name if ap_leaf else ap_code,
                account_type="Liability", debit=amt,
                member_tenant_id=b.member.member_tenant_id, sort_order=sort_i,
            ))
            sort_i += 1
            lines.append(_elim_line(
                holding_tenant_id=holding_id, run_id=run.id, kind="ic_balance",
                description=desc, account_code=ar_code,
                account_name=ar_leaf.name if ar_leaf else ar_code,
                account_type="Asset", credit=amt,
                member_tenant_id=a.member.member_tenant_id, sort_order=sort_i,
            ))
            sort_i += 1
            # Consume so we don't double-elim the same balances
            ar_bal -= amt
            # Mutate leaf copies for subsequent pairs
            if ar_leaf:
                ar_leaf.debit = money(max(ZERO, ar_leaf.debit - amt))
            if ap_leaf:
                # liability credit-normal: reduce credit
                ap_leaf.credit = money(max(ZERO, ap_leaf.credit - amt))
            if ar_bal <= ZERO:
                break

    # ── IC sales (optional settings codes) ────────────────────────────────
    rev_code = _setting(session, holding_id, "consol_ic_revenue_code").strip()
    cogs_code = _setting(session, holding_id, "consol_ic_cogs_code").strip()
    if rev_code and cogs_code:
        # Sum revenue on rev_code and expense on cogs_code across line-by-line members
        rev_total = ZERO
        cogs_total = ZERO
        rev_name, cogs_name = rev_code, cogs_code
        for s in snaps:
            if s.member.relationship == "associate":
                continue
            if rev_code in s.leaves:
                L = s.leaves[rev_code]
                rev_total += _signed_balance("Revenue", L.debit, L.credit)
                rev_name = L.name
            if cogs_code in s.leaves:
                L = s.leaves[cogs_code]
                cogs_total += _signed_balance("Expense", L.debit, L.credit)
                cogs_name = L.name
        amt = money(min(max(rev_total, ZERO), max(cogs_total, ZERO)))
        if amt > ZERO:
            desc = f"Eliminate IC sales {rev_code} / purchases {cogs_code}"
            lines.append(_elim_line(
                holding_tenant_id=holding_id, run_id=run.id, kind="ic_sales",
                description=desc, account_code=rev_code, account_name=rev_name,
                account_type="Revenue", debit=amt, sort_order=sort_i,
            ))
            sort_i += 1
            lines.append(_elim_line(
                holding_tenant_id=holding_id, run_id=run.id, kind="ic_sales",
                description=desc, account_code=cogs_code, account_name=cogs_name,
                account_type="Expense", credit=amt, sort_order=sort_i,
            ))
            sort_i += 1

    # ── NCI ───────────────────────────────────────────────────────────────
    for s in snaps:
        if s.member.relationship != "subsidiary" or not s.member.is_active:
            continue
        pct = D(s.member.ownership_pct or 100)
        if pct >= Decimal("100"):
            continue
        nci_pct = (Decimal("100") - pct) / Decimal("100")
        nci_amt = money(s.net_assets * nci_pct)
        if nci_amt == ZERO:
            continue
        desc = f"NCI {s.tenant_name} ({float(100 - pct):.2f}% of net assets)"
        # Reclassify: Dr group equity / Cr NCI
        lines.append(_elim_line(
            holding_tenant_id=holding_id, run_id=run.id, kind="nci",
            description=desc, account_code="3100",
            account_name="Retained Earnings (NCI reclass)",
            account_type="Equity", debit=nci_amt if nci_amt > ZERO else ZERO,
            credit=(-nci_amt if nci_amt < ZERO else ZERO),
            member_tenant_id=s.member.member_tenant_id, sort_order=sort_i,
        ))
        sort_i += 1
        lines.append(_elim_line(
            holding_tenant_id=holding_id, run_id=run.id, kind="nci",
            description=desc, account_code=NCI_CODE, account_name=NCI_NAME,
            account_type="Equity",
            debit=(-nci_amt if nci_amt < ZERO else ZERO),
            credit=nci_amt if nci_amt > ZERO else ZERO,
            member_tenant_id=s.member.member_tenant_id, sort_order=sort_i,
        ))
        sort_i += 1

    for line in lines:
        session.add(line)
    session.commit()
    return list(session.exec(
        select(ConsolidationElimination)
        .where(ConsolidationElimination.run_id == run.id)
        .order_by(ConsolidationElimination.sort_order, ConsolidationElimination.id)
    ).all())


def _apply_elims_to_agg(
    agg: dict[str, LeafAgg], elims: list[ConsolidationElimination],
) -> None:
    for e in elims:
        cur = agg.get(e.account_code)
        if not cur:
            agg[e.account_code] = LeafAgg(
                code=e.account_code,
                name=e.account_name or e.account_code,
                type=e.account_type or "Equity",
                debit=D(e.debit),
                credit=D(e.credit),
            )
        else:
            cur.debit += D(e.debit)
            cur.credit += D(e.credit)


class _SynthAccount:
    """Minimal account-like object for build_account_tree when codes aren't on holding CoA."""
    def __init__(self, id, code, name, type, parent_id=None, is_group=False):
        self.id = id
        self.code = code
        self.name = name
        self.type = type
        self.parent_id = parent_id
        self.is_group = is_group


def build_statements(
    session: Session,
    run: ConsolidationRun,
    *,
    snaps: Optional[list[MemberSnapshot]] = None,
    elims: Optional[list[ConsolidationElimination]] = None,
) -> dict:
    """Aggregate TB → apply elims → hierarchical BS + P&L."""
    if snaps is None:
        members = [
            m for m in list_members(session, run.holding_tenant_id) if m.is_active
        ]
        snaps = [
            snapshot_member(session, m, run.period_start, run.period_end)
            for m in members
        ]
    if elims is None:
        elims = list(session.exec(
            select(ConsolidationElimination)
            .where(ConsolidationElimination.run_id == run.id)
            .order_by(ConsolidationElimination.sort_order, ConsolidationElimination.id)
        ).all())

    agg = aggregate_line_by_line(snaps)
    associate_pickups = apply_associate_pickups(agg, snaps)
    _apply_elims_to_agg(agg, elims)

    holding_coa = _holding_accounts_by_code(session, run.holding_tenant_id)

    # Map aggregated codes onto holding CoA ids; synthesize missing leaves
    values_bs: dict[int, dict] = {}
    values_pl: dict[int, dict] = {}
    accounts_bs: list = []
    accounts_pl: list = []
    seen_ids: set[int] = set()
    synth_id = -1
    net_income = ZERO

    for code, leaf in agg.items():
        acct = holding_coa.get(code)
        if acct is None:
            acct = _SynthAccount(synth_id, code, leaf.name, leaf.type)
            synth_id -= 1
        if acct.id not in seen_ids:
            seen_ids.add(acct.id)
            if leaf.type in ("Asset", "Liability", "Equity"):
                accounts_bs.append(acct)
            if leaf.type in ("Revenue", "Expense"):
                accounts_pl.append(acct)

        debit, credit = leaf.debit, leaf.credit
        if leaf.type == "Asset":
            values_bs[acct.id] = {"balance": debit - credit}
        elif leaf.type in ("Liability", "Equity"):
            values_bs[acct.id] = {"balance": credit - debit}
        elif leaf.type == "Revenue":
            amt = credit - debit
            values_pl[acct.id] = {"amount": amt}
            net_income += amt
        elif leaf.type == "Expense":
            amt = debit - credit
            values_pl[acct.id] = {"amount": amt}
            net_income -= amt

    # Include holding CoA group skeleton so trees roll up when codes match
    for a in holding_coa.values():
        if a.id in seen_ids:
            continue
        if a.type in ("Asset", "Liability", "Equity") and a.is_group:
            accounts_bs.append(a)
            seen_ids.add(a.id)
        elif a.type in ("Revenue", "Expense") and a.is_group:
            accounts_pl.append(a)
            seen_ids.add(a.id)

    assets = build_account_tree(
        [a for a in accounts_bs if a.type == "Asset"], values_bs, ["balance"],
    )
    liabilities = build_account_tree(
        [a for a in accounts_bs if a.type == "Liability"], values_bs, ["balance"],
    )
    equity = build_account_tree(
        [a for a in accounts_bs if a.type == "Equity"], values_bs, ["balance"],
    )
    if net_income != ZERO:
        equity.append({
            "id": None, "code": "RE-CUR", "name": "Retained Earnings (Current Period)",
            "type": "Equity", "is_group": False, "level": 0,
            "balance": net_income, "children": [],
        })

    rev_accts = [a for a in accounts_pl if a.type == "Revenue"]
    exp_accts = [a for a in accounts_pl if a.type == "Expense"]
    revenue = build_account_tree(rev_accts, values_pl, ["amount"])
    expenses = build_account_tree(exp_accts, values_pl, ["amount"])

    def _tot(nodes, key):
        return sum((D(n[key]) for n in nodes), ZERO)

    # Flat worksheet for UI
    worksheet = []
    for code in sorted(agg.keys()):
        leaf = agg[code]
        worksheet.append({
            "code": code,
            "name": leaf.name,
            "type": leaf.type,
            "debit": float(leaf.debit),
            "credit": float(leaf.credit),
            "balance": float(_signed_balance(leaf.type, leaf.debit, leaf.credit)),
        })

    return {
        "period_start": run.period_start,
        "period_end": run.period_end,
        "members": [
            {
                "id": s.member.id,
                "tenant_id": s.member.member_tenant_id,
                "name": s.tenant_name,
                "relationship": s.member.relationship,
                "ownership_pct": float(s.member.ownership_pct or 0),
                "net_assets": float(s.net_assets),
                "period_pnl": float(s.period_pnl),
            }
            for s in snaps
        ],
        "associate_pickups": [
            {"name": n, "amount": float(a)} for n, a in associate_pickups
        ],
        "eliminations": [
            {
                "id": e.id,
                "kind": e.kind,
                "description": e.description,
                "account_code": e.account_code,
                "account_name": e.account_name,
                "account_type": e.account_type,
                "debit": float(e.debit or 0),
                "credit": float(e.credit or 0),
                "member_tenant_id": e.member_tenant_id,
            }
            for e in elims
        ],
        "worksheet": worksheet,
        "balance_sheet": {
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "totals": {
                "assets": float(_tot(assets, "balance")),
                "liabilities": float(_tot(liabilities, "balance")),
                "equity": float(_tot(equity, "balance")),
            },
        },
        "income_statement": {
            "revenue": revenue,
            "expenses": expenses,
            "totals": {
                "revenue": float(_tot(revenue, "amount")),
                "expenses": float(_tot(expenses, "amount")),
                "net_profit": float(_tot(revenue, "amount") - _tot(expenses, "amount")),
            },
        },
    }


def period_is_locked(session: Session, tenant_id: int, start: str, end: str) -> bool:
    row = session.exec(
        select(AccountingPeriod).where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.is_locked == True,  # noqa: E712
            AccountingPeriod.period_start <= end,
            AccountingPeriod.period_end >= start,
        )
    ).first()
    return row is not None


def _json_safe(obj):
    """Recursively coerce Decimals (and nested trees) for JSON columns."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def post_run(session: Session, run: ConsolidationRun, user: User) -> ConsolidationRun:
    if run.status != "draft":
        raise ConsolError("Only draft runs can be posted")
    # Balanced eliminations check
    elims = list(session.exec(
        select(ConsolidationElimination).where(ConsolidationElimination.run_id == run.id)
    ).all())
    td = sum((D(e.debit) for e in elims), ZERO)
    tc = sum((D(e.credit) for e in elims), ZERO)
    if money(td) != money(tc):
        raise ConsolError(
            f"Eliminations must balance (debit {td} ≠ credit {tc})"
        )

    if period_is_locked(session, run.holding_tenant_id, run.period_start, run.period_end):
        if user.role not in OVERRIDE_ROLES:
            raise ConsolError(
                "Period is locked — posting a consolidation package requires an owner/admin override",
                status_code=403,
            )

    package = _json_safe(build_statements(session, run, elims=elims))
    run.package_json = package
    run.status = "posted"
    run.posted_at = datetime.utcnow()
    run.posted_by_id = user.id
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def void_run(session: Session, run: ConsolidationRun, user: User) -> ConsolidationRun:
    if run.status != "posted":
        raise ConsolError("Only posted runs can be voided")
    run.status = "void"
    run.voided_at = datetime.utcnow()
    run.voided_by_id = user.id
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
