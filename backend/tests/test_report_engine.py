"""Engine helpers — pure logic, no HTTP/DB."""
from decimal import Decimal
import pytest
from services.report_engine import coerce_value, ReportConfig, FilterClause, build_predicate, ReportError
from services.report_sources import FieldType, INVOICES


def test_coerce_money_to_decimal():
    assert coerce_value(FieldType.MONEY, "12.50") == Decimal("12.50")

def test_coerce_number_to_decimal():
    assert coerce_value(FieldType.NUMBER, 3) == Decimal("3")

def test_coerce_date_validates_iso():
    assert coerce_value(FieldType.DATE, "2026-05-01") == "2026-05-01"
    with pytest.raises(ValueError):
        coerce_value(FieldType.DATE, "not-a-date")

def test_reportconfig_defaults_empty():
    c = ReportConfig(columns=["total"])
    assert c.filters == [] and c.sort == [] and c.group_by == [] and c.aggregates == []


def test_build_predicate_money_gte():
    f = INVOICES.field("total")
    pred = build_predicate(f, "gte", coerce_value(f.type, "1000"))
    assert pred is not None  # compiles to a SQLAlchemy expression

def test_build_predicate_rejects_bad_op_for_type():
    f = INVOICES.field("total")  # MONEY
    with pytest.raises(ReportError):
        build_predicate(f, "contains", Decimal("1"))

def test_build_predicate_between_needs_two_values():
    f = INVOICES.field("total")
    with pytest.raises(ReportError):
        build_predicate(f, "between", [Decimal("1")])
