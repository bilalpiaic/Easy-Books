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

from services.report_sources import FieldDef, FieldType, OPS_BY_TYPE, ReportSource


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
