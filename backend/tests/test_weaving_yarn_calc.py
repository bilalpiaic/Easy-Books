"""#196 — pure weaving/sizing yarn calculator engine (TDD)."""
from decimal import Decimal

from services.weaving_yarn_calc import (
    calculate_weaving,
    calculate_sizing,
    compare_to_contract,
    LB_TO_KG,
)


def test_weaving_worked_example():
    r = calculate_weaving(
        epi=60,
        ppi=50,
        width_in=60,
        length_yd=1000,
        warp_ne=40,
        weft_ne=30,
        warp_crimp_pct=10,
        weft_crimp_pct=5,
        visible_waste_pct=3,
        invisible_waste_pct=1,
    )
    assert abs(r["warp_lbs"] - 122.5714) < 0.01
    assert abs(r["weft_lbs"] - 130.0) < 0.01
    assert abs(r["total_lbs"] - 252.5714) < 0.01
    assert abs(r["warp_kg"] - 122.5714 * float(LB_TO_KG)) < 0.01
    assert abs(r["weft_kg"] - 130.0 * float(LB_TO_KG)) < 0.01
    assert "total" in r and r["total"]["kg"] > 0
    assert r["total"]["lbs"] > 0
    assert r["total"]["bags"] > 0
    assert r["waste_factor"] == 1.04
    assert abs(r["net_lbs_before_waste"] - (252.5714 / 1.04)) < 0.02


def test_weaving_zero_ne_safe():
    r = calculate_weaving(
        epi=60, ppi=50, width_in=60, length_yd=1000,
        warp_ne=0, weft_ne=30,
        warp_crimp_pct=0, weft_crimp_pct=0,
        visible_waste_pct=0, invisible_waste_pct=0,
    )
    assert r["warp_lbs"] == 0.0
    assert r["weft_lbs"] > 0


def test_waste_is_additive_not_compounded():
    """vis=3 inv=1 → factor 1.04, not 1.03*1.01."""
    r = calculate_weaving(
        epi=60, ppi=50, width_in=60, length_yd=1000,
        warp_ne=40, weft_ne=30,
        warp_crimp_pct=10, weft_crimp_pct=5,
        visible_waste_pct=3, invisible_waste_pct=1,
    )
    assert abs(r["waste_factor"] - 1.04) < 1e-9


def test_sizing_worked_example():
    r = calculate_sizing(
        unsized_kg=100,
        pickup_pct=12,
        stretch_pct=1.5,
        visible_waste_pct=0.7,
        invisible_waste_pct=1.0,
    )
    assert abs(r["net_before_waste_kg"] - 113.68) < 0.01
    assert abs(r["gross_kg"] - 115.61256) < 0.02
    assert r["gross"]["kg"] > 0
    assert r["gross"]["lbs"] > 0
    assert r["gross"]["bags"] > 0


def test_compare_first_assign_ok():
    calc = {"total_kg": 100.0, "warp_ne": 40.0, "weft_ne": 30.0}
    contract = {
        "planned_total_yarn_kg": None,
        "warp_count_ne": None,
        "weft_count_ne": None,
    }
    out = compare_to_contract(calc, contract, threshold=0.10)
    assert out["ok"] is True
    assert out["warnings"] == []


def test_compare_qty_mismatch_requires_override():
    calc = {"total_kg": 120.0, "warp_ne": 40.0, "weft_ne": 30.0}
    contract = {
        "planned_total_yarn_kg": Decimal("100"),
        "warp_count_ne": Decimal("40"),
        "weft_count_ne": Decimal("30"),
    }
    out = compare_to_contract(calc, contract, threshold=0.10)
    assert out["ok"] is False
    assert any("qty" in w.lower() or "quantity" in w.lower() for w in out["warnings"])


def test_compare_count_mismatch():
    calc = {"total_kg": 100.0, "warp_ne": 32.0, "weft_ne": 30.0}
    contract = {
        "planned_total_yarn_kg": Decimal("100"),
        "warp_count_ne": Decimal("40"),
        "weft_count_ne": Decimal("30"),
    }
    out = compare_to_contract(calc, contract, threshold=0.10)
    assert out["ok"] is False
    assert any("count" in w.lower() for w in out["warnings"])


def test_compare_within_threshold_ok():
    calc = {"total_kg": 105.0, "warp_ne": 40.0, "weft_ne": 30.0}
    contract = {
        "planned_total_yarn_kg": Decimal("100"),
        "warp_count_ne": Decimal("40"),
        "weft_count_ne": Decimal("30"),
    }
    out = compare_to_contract(calc, contract, threshold=0.10)
    assert out["ok"] is True
