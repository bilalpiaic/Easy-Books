"""Cash-flow comparative period tests.

Task 1 of 2026-06-06-comparative-statements plan:
  - no-compare call returns the flat shape (back-compat)
  - with compare_start + compare_end returns {current, comparison}
    with each side reconciling net_cash_change == operating + investing + financing
    and having beginning_balance / ending_balance
"""


def test_cashflow_no_compare_is_flat(client, admin_headers):
    r = client.get(
        "/api/reports/cash-flow?start=2026-01-01&end=2026-01-31",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    # back-compat: flat shape (has net_cash_change at top level, not nested current/comparison)
    assert "net_cash_change" in body
    assert "comparison" not in body


def test_cashflow_with_compare_returns_current_and_comparison(client, admin_headers):
    r = client.get(
        "/api/reports/cash-flow?start=2026-02-01&end=2026-02-28"
        "&compare_start=2026-01-01&compare_end=2026-01-31",
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "current" in body and "comparison" in body
    for side in (body["current"], body["comparison"]):
        # each side reconciles: net = operating + investing + financing
        assert side["net_cash_change"] == side["operating_cash"] + side["investing_cash"] + side["financing_cash"]
        assert "beginning_balance" in side and "ending_balance" in side
