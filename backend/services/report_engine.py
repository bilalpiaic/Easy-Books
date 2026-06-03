"""Report engine: ReportConfig schema + tenant-safe query builder.

Read-only. The caller never commits. Every identifier is resolved through the
registry; tenant_id is injected unconditionally."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from services.report_sources import FieldDef, FieldType, OPS_BY_TYPE, REGISTRY, ReportSource


class FilterClause(BaseModel):
    field: str
    op: str
    value: Any = None


class SortClause(BaseModel):
    field: str
    dir: str = "asc"


class Aggregate(BaseModel):
    field: str
    fn: str  # sum | avg | count | min | max


class DateRange(BaseModel):
    preset: Optional[str] = None      # this_month | this_quarter | this_year | ytd
    start: Optional[str] = None
    end: Optional[str] = None


class ReportConfig(BaseModel):
    columns: list[str] = Field(default_factory=list)
    filters: list[FilterClause] = Field(default_factory=list)
    sort: list[SortClause] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    aggregates: list[Aggregate] = Field(default_factory=list)
    date_range: Optional[DateRange] = None


class ReportError(ValueError):
    """Engine validation failure → HTTP 400 at the router."""


def coerce_value(ftype: FieldType, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, list):
        return [coerce_value(ftype, v) for v in value]
    if ftype in (FieldType.MONEY, FieldType.NUMBER):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ReportError(f"not a number: {value!r}")
    if ftype == FieldType.DATE:
        try:
            _date.fromisoformat(str(value))
        except ValueError:
            raise ReportError(f"not an ISO date: {value!r}")
        return str(value)
    if ftype == FieldType.BOOL:
        return bool(value)
    return str(value)


def build_predicate(f: FieldDef, op: str, value: Any):
    if op not in OPS_BY_TYPE[f.type]:
        raise ReportError(f"operator {op!r} not allowed on {f.type.value} field {f.key!r}")
    col = f.column
    if op == "equals":
        return col == value
    if op == "contains":
        return col.contains(value)
    if op == "starts_with":
        return col.startswith(value)
    if op == "in":
        vals = value if isinstance(value, list) else [value]
        return col.in_(vals)
    if op == "gt":
        return col > value
    if op == "gte":
        return col >= value
    if op == "lt":
        return col < value
    if op == "lte":
        return col <= value
    if op == "before":
        return col < value
    if op == "after":
        return col > value
    if op == "between":
        if not isinstance(value, list) or len(value) != 2:
            raise ReportError("between requires exactly two values")
        return col.between(value[0], value[1])
    raise ReportError(f"unknown operator {op!r}")


@dataclass
class ColumnMeta:
    key: str
    label: str
    type: str
    aggregatable: bool


@dataclass
class ReportResult:
    columns: list[ColumnMeta]
    rows: list[dict]
    group_by: list[str]
    footers: Optional[dict]
    page: int
    page_size: int
    total_count: int


_AGG_FN = {
    "sum": func.sum, "avg": func.avg, "count": func.count,
    "min": func.min, "max": func.max,
}
MAX_EXPORT_ROWS = 10_000


def _ser(v: Any) -> Any:
    return format(v, "f") if isinstance(v, Decimal) else v


def _money_str(v: Any) -> str:
    return format(Decimal(str(v or 0)).quantize(Decimal("0.01")), "f")


def _preset_range(preset: str) -> tuple[str, str]:
    from datetime import date
    t = date.today()
    if preset == "this_month":
        start = t.replace(day=1)
    elif preset == "this_quarter":
        start = t.replace(month=((t.month - 1) // 3) * 3 + 1, day=1)
    elif preset in ("this_year", "ytd"):
        start = t.replace(month=1, day=1)
    else:
        raise ReportError(f"unknown date preset {preset!r}")
    return start.isoformat(), t.isoformat()


def _apply_date_range(stmt, date_field: FieldDef, dr: DateRange):
    if dr.preset:
        start, end = _preset_range(dr.preset)
    else:
        start, end = dr.start, dr.end
    if start:
        stmt = stmt.where(date_field.column >= start)
    if end:
        stmt = stmt.where(date_field.column <= end)
    return stmt


def _collect_joins(source: ReportSource, fields: list[FieldDef]):
    # Dedup by the join's structural identity, not the JoinPath object id: each
    # _f(...) builds a distinct JoinPath, so two fields off the same related
    # table (e.g. account_code + account_name) would otherwise emit duplicate
    # JOINs and crash with "ambiguous column name".
    seen, joins = set(), []
    for f in fields:
        if not f.join:
            continue
        key = (id(f.join.local), f.join.target, id(f.join.target_key))
        if key not in seen:
            seen.add(key)
            joins.append(f.join)
    return joins


def run_report(session: Session, *, tenant_id: int, source_key: str,
               config: ReportConfig, page: int, page_size: int) -> ReportResult:
    source = REGISTRY.get(source_key)
    if source is None:
        raise ReportError(f"unknown source {source_key!r}")

    try:
        sel_fields = [source.field(k) for k in (config.columns or source.default_columns)]
        filt_fields = [source.field(c.field) for c in config.filters]
        grp_fields = [source.field(k) for k in config.group_by]
        agg_fields = [(source.field(a.field), a) for a in config.aggregates]
        sort_fields = [(source.field(s.field), s) for s in config.sort]
    except KeyError as e:
        raise ReportError(f"unknown field {e.args[0]!r}")

    for agg_field, a in agg_fields:
        if a.fn not in _AGG_FN:
            raise ReportError(f"unknown aggregate function {a.fn!r}")
        if not agg_field.aggregatable:
            raise ReportError(f"field {a.field!r} is not aggregatable")

    date_f = source.field(source.date_field) if (config.date_range and source.date_field) else None
    all_used = sel_fields + filt_fields + grp_fields + [f for f, _ in agg_fields] + \
        [f for f, _ in sort_fields] + ([date_f] if date_f else [])
    joins = _collect_joins(source, all_used)

    def base(stmt):
        stmt = stmt.select_from(source.model)
        for j in joins:
            stmt = stmt.join(j.target, j.local == j.target_key)
        stmt = stmt.where(source.model.tenant_id == tenant_id)   # ALWAYS injected
        for c in config.filters:
            f = source.field(c.field)
            stmt = stmt.where(build_predicate(f, c.op, coerce_value(f.type, c.value)))
        if date_f:
            stmt = _apply_date_range(stmt, date_f, config.date_range)
        return stmt

    if config.group_by:
        cols = [source.field(k).column.label(k) for k in config.group_by]
        for f, a in agg_fields:
            cols.append(_AGG_FN[a.fn](f.column).label(f.key))
        q = base(select(*cols)).group_by(*[source.field(k).column for k in config.group_by])
        col_keys = config.group_by + [f.key for f, _ in agg_fields]
    else:
        q = base(select(*[f.column.label(f.key) for f in sel_fields]))
        col_keys = [f.key for f in sel_fields]

    for f, s in sort_fields:
        q = q.order_by(f.column.desc() if s.dir == "desc" else f.column.asc())

    total = session.scalar(select(func.count()).select_from(q.subquery()))
    # Use session.execute (SQLAlchemy) for multi-column queries — session.exec (SQLModel)
    # returns ScalarResult which does not support .mappings().
    rows_raw = session.execute(q.offset(page * page_size).limit(page_size)).mappings().all()

    key_type = {f.key: f.type for f in all_used}
    rows = [{k: (_money_str(r[k]) if key_type.get(k) == FieldType.MONEY else _ser(r[k]))
             for k in col_keys} for r in rows_raw]

    footers = None
    if config.aggregates and not config.group_by:
        fcols = [_AGG_FN[a.fn](source.field(a.field).column).label(a.field) for a in config.aggregates]
        frow = session.execute(base(select(*fcols))).mappings().first()
        footers = {a.field: (_money_str(frow[a.field]) if source.field(a.field).type == FieldType.MONEY
                             else _ser(frow[a.field])) for a in config.aggregates}

    meta = [ColumnMeta(f.key, f.label, f.type.value, f.aggregatable)
            for f in (sel_fields if not config.group_by
                      else grp_fields + [f for f, _ in agg_fields])]
    return ReportResult(meta, rows, config.group_by, footers, page, page_size, total or 0)
