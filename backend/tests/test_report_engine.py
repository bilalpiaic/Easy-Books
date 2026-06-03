"""Engine helpers — pure logic, no HTTP/DB."""
from decimal import Decimal
import pytest
from services.report_engine import coerce_value, ReportConfig, FilterClause
from services.report_sources import FieldType


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
