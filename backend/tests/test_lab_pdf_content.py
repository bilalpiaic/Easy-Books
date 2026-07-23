"""Lab PDF HTML content — distinct results + serial SVG trends."""
from __future__ import annotations

from fastapi.testclient import TestClient

from services.lab_pdf_charts import build_trend_svg, serial_trends_for_items
from services.pdf import render_template_html


def _auth(client: TestClient, email: str) -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Lab Tech",
            "company_name": "Lab Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_hc(client: TestClient, auth: dict) -> None:
    r = client.post("/api/modules/healthcare/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def _capture_pdf_html(monkeypatch):
    """Replace PDF renderer with HTML capture of the lab report context."""
    captured: dict = {}

    def _fake(report: dict, company_name: str, tagline: str = "") -> bytes:
        captured["html"] = render_template_html(
            "lab_report.html",
            {"report": report, "company_name": company_name, "tagline": tagline},
        )
        captured["report"] = report
        return b"%PDF-1.4 content-test"

    monkeypatch.setattr("services.pdf.render_lab_report_pdf", _fake)
    return captured


def test_build_trend_svg_geometry():
    points = [
        {"numeric_value": 12.0, "order_date": "2026-01-01", "is_current": False, "is_abnormal": False},
        {"numeric_value": 14.5, "order_date": "2026-02-01", "is_current": False, "is_abnormal": False},
        {"numeric_value": 18.0, "order_date": "2026-03-01", "is_current": True, "is_abnormal": True},
    ]
    svg = build_trend_svg(points, reference_interval={"low": 12.0, "high": 16.0})
    assert svg is not None
    assert svg["band"] is not None
    assert svg["band"]["width"] > 0
    assert len(svg["markers"]) == 3
    assert svg["markers"][-1]["is_current"] is True
    assert svg["markers"][-1]["is_abnormal"] is True
    assert "," in svg["polyline"]
    assert build_trend_svg(points[:1]) is None


def test_serial_trends_splits_numeric_vs_qualitative():
    items = [
        {
            "test_id": 1,
            "test_code": "HB",
            "test_name": "Hemoglobin",
            "result_unit": "g/dL",
            "reference_range": "12-16",
            "reference_interval": {"low": 12.0, "high": 16.0},
            "history": [
                {"numeric_value": 13.0, "order_date": "2026-01-01", "result_value": "13.0", "is_current": False},
                {"numeric_value": 14.0, "order_date": "2026-02-01", "result_value": "14.0", "is_current": True},
            ],
        },
        {
            "test_id": 2,
            "test_code": "HIV",
            "test_name": "HIV Ab",
            "history": [
                {"numeric_value": None, "order_date": "2026-01-01", "result_value": "Non-Reactive", "is_current": False},
                {"numeric_value": None, "order_date": "2026-02-01", "result_value": "Non-Reactive", "is_current": True},
            ],
        },
        {
            "test_id": 3,
            "test_name": "One-shot",
            "history": [
                {"numeric_value": 5.0, "order_date": "2026-02-01", "result_value": "5.0", "is_current": True},
            ],
        },
    ]
    serial = serial_trends_for_items(items)
    assert len(serial["chartable"]) == 1
    assert serial["chartable"][0]["test_code"] == "HB"
    assert serial["chartable"][0]["svg"]["polyline"]
    assert len(serial["table_only"]) == 1
    assert serial["table_only"][0]["test_code"] == "HIV"


def test_lab_pdf_html_distinct_results_and_serial_svg(client: TestClient, monkeypatch):
    auth = _auth(client, "pdf-content@co.test")
    _install_hc(client, auth)
    captured = _capture_pdf_html(monkeypatch)

    r = client.post(
        "/api/healthcare/patients",
        headers=auth,
        json={"name": "Serial Patient", "gender": "female", "email": "serial@ex.com"},
    )
    assert r.status_code == 201, r.text
    patient_id = r.json()["id"]

    r = client.post(
        "/api/healthcare/lab/tests",
        headers=auth,
        json={
            "code": "HB",
            "name": "Hemoglobin",
            "category": "hematology",
            "unit": "g/dL",
            "normal_range": "12-16",
            "standard_fee": 300,
        },
    )
    assert r.status_code == 201, r.text
    test_id = r.json()["id"]

    def _order(date: str, value: str) -> dict:
        r = client.post(
            "/api/healthcare/lab/orders",
            headers=auth,
            json={
                "patient_id": patient_id,
                "order_date": date,
                "source": "walkin",
                "test_ids": [test_id],
            },
        )
        assert r.status_code == 201, r.text
        order = r.json()
        detail = client.get(f"/api/healthcare/lab/orders/{order['id']}", headers=auth).json()
        item_id = detail["items"][0]["id"]
        r = client.put(
            f"/api/healthcare/lab/orders/{order['id']}/items/{item_id}/result",
            headers=auth,
            json={
                "result_value": value,
                "result_unit": "g/dL",
                "reference_range": "12-16",
                "is_abnormal": False,
            },
        )
        assert r.status_code == 200, r.text
        return order

    o1 = _order("2026-06-01", "11.1")
    r = client.get(f"/api/healthcare/lab/orders/{o1['id']}/pdf", headers=auth)
    assert r.status_code == 200
    html1 = captured["html"]
    assert o1["order_number"] in html1
    assert "11.1" in html1
    assert "15.9" not in html1
    # Single visit — no serial section yet
    assert "Serial Results" not in html1

    o2 = _order("2026-07-01", "15.9")
    r = client.get(f"/api/healthcare/lab/orders/{o2['id']}/pdf", headers=auth)
    assert r.status_code == 200
    html2 = captured["html"]
    report2 = captured["report"]

    assert o2["order_number"] in html2
    assert "15.9" in html2
    assert "11.1" in html2  # Prev + serial history
    assert "Prev" in html2
    assert report2.get("has_serial_trends") is True
    assert "Serial Results" in html2
    assert "<svg" in html2
    assert "polyline" in html2
    assert "Hemoglobin" in html2

    # Older order PDF still excludes the later visit's unique result as current-only
    r = client.get(f"/api/healthcare/lab/orders/{o1['id']}/pdf", headers=auth)
    assert r.status_code == 200
    html1_again = captured["html"]
    assert "11.1" in html1_again
    assert "15.9" not in html1_again
    assert o1["order_number"] in html1_again
