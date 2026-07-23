"""WeasyPrint-friendly SVG geometry for lab serial trend charts (CLSI cumulative)."""
from __future__ import annotations

from typing import Any, Optional


SVG_W = 280
SVG_H = 120
PAD_L = 36
PAD_R = 12
PAD_T = 10
PAD_B = 28


def _fmt_date(iso: Optional[str]) -> str:
    """ISO YYYY-MM-DD (or datetime) → dd-mm-yy for PDF axis labels."""
    if not iso:
        return "—"
    s = str(iso)[:10]
    parts = s.split("-")
    if len(parts) != 3:
        return s
    y, m, d = parts
    return f"{d}-{m}-{y[2:]}"


def build_trend_svg(
    points: list[dict[str, Any]],
    *,
    reference_interval: Optional[dict] = None,
) -> Optional[dict[str, Any]]:
    """Build SVG geometry for numeric serial history points.

    Each point needs ``numeric_value``, ``order_date``, and optionally
    ``is_current`` / ``is_abnormal`` / ``result_value`` / ``flag``.

    Returns None when fewer than 2 numeric points.
    """
    nums = [p for p in points if p.get("numeric_value") is not None]
    if len(nums) < 2:
        return None

    interval = reference_interval or {}
    low = interval.get("low")
    high = interval.get("high")

    values = [float(p["numeric_value"]) for p in nums]
    data_min = min(values + ([float(low)] if low is not None else []))
    data_max = max(values + ([float(high)] if high is not None else []))
    span = data_max - data_min
    pad = span * 0.15 if span > 0 else 1.0
    y_min = data_min - pad
    y_max = data_max + pad
    y_span = y_max - y_min or 1.0

    plot_w = SVG_W - PAD_L - PAD_R
    plot_h = SVG_H - PAD_T - PAD_B
    n = len(nums)

    def x_at(i: int) -> float:
        if n == 1:
            return PAD_L + plot_w / 2
        return PAD_L + (plot_w * i / (n - 1))

    def y_at(v: float) -> float:
        # SVG y grows downward
        return PAD_T + plot_h * (1.0 - (v - y_min) / y_span)

    band = None
    if low is not None or high is not None:
        band_lo = float(low) if low is not None else y_min
        band_hi = float(high) if high is not None else y_max
        y_top = y_at(band_hi)
        y_bot = y_at(band_lo)
        band = {
            "x": PAD_L,
            "y": min(y_top, y_bot),
            "width": plot_w,
            "height": abs(y_bot - y_top),
        }

    coords = [(x_at(i), y_at(values[i])) for i in range(n)]
    polyline = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)

    markers = []
    for i, p in enumerate(nums):
        x, y = coords[i]
        markers.append({
            "cx": round(x, 1),
            "cy": round(y, 1),
            "r": 4.5 if p.get("is_current") else 3.0,
            "is_current": bool(p.get("is_current")),
            "is_abnormal": bool(p.get("is_abnormal")),
        })

    x_labels = [
        {"x": round(x_at(i), 1), "y": SVG_H - 8, "text": _fmt_date(p.get("order_date"))}
        for i, p in enumerate(nums)
    ]
    # Three y ticks: min, mid, max of scale
    y_ticks = []
    for frac, val in ((0.0, y_max), (0.5, (y_min + y_max) / 2), (1.0, y_min)):
        y_ticks.append({
            "x": PAD_L - 4,
            "y": round(PAD_T + plot_h * frac + 3, 1),
            "text": f"{val:.1f}" if abs(val) < 1000 else f"{val:.0f}",
        })

    return {
        "width": SVG_W,
        "height": SVG_H,
        "band": band,
        "polyline": polyline,
        "markers": markers,
        "x_labels": x_labels,
        "y_ticks": y_ticks,
        "view_box": f"0 0 {SVG_W} {SVG_H}",
    }


def serial_trends_for_items(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Split items with multi-visit history into chartable vs qualitative table-only."""
    chartable: list[dict[str, Any]] = []
    table_only: list[dict[str, Any]] = []

    for item in items:
        history = item.get("history") or []
        if len(history) < 2:
            continue
        numeric_pts = [p for p in history if p.get("numeric_value") is not None]
        unit = item.get("result_unit") or item.get("catalogue_unit") or ""
        ref = item.get("reference_range") or item.get("catalogue_normal_range") or ""
        base = {
            "test_id": item.get("test_id"),
            "test_code": item.get("test_code"),
            "test_name": item.get("test_name"),
            "unit": unit,
            "reference_range": ref,
            "history": history,
        }
        if len(numeric_pts) >= 2:
            svg = build_trend_svg(
                numeric_pts,
                reference_interval=item.get("reference_interval") or {},
            )
            if svg:
                chartable.append({
                    **base,
                    "svg": svg,
                    "numeric_history": numeric_pts,
                })
                continue
        table_only.append(base)

    return {"chartable": chartable, "table_only": table_only}
