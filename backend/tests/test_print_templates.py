"""Print template clones + report-builder x.* columns (#374)."""
from __future__ import annotations

from jinja2 import TemplateNotFound

from services.permissions import PERMISSION_RESOURCES
from services.print_templates import render_sandboxed_html


def _signup(client, email, company="Co"):
    r = client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "Owner", "company_name": company, "business_model": "simple",
    })
    assert r.status_code == 200, r.text
    tok = client.post("/api/auth/login", data={
        "username": email, "password": "password123",
    })
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


def test_studio_print_resource_registered():
    assert "studio.print" in PERMISSION_RESOURCES
    assert PERMISSION_RESOURCES["studio.print"]["category"] == "System"


def test_list_includes_virtual_standard(client, admin_headers):
    r = client.get("/api/studio/print-templates?entity=invoice", headers=admin_headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    std = next(x for x in rows if x["key"] == "standard")
    assert std["is_builtin"] is True
    assert std["id"] is None
    assert std["is_default"] is True


def test_clone_key_must_be_x_dot(client, admin_headers):
    r = client.post("/api/studio/print-templates", headers=admin_headers, json={
        "entity": "invoice", "key": "mill_packing", "label": "Packing",
    })
    assert r.status_code == 400, r.text


def test_clone_copies_html_and_renders_custom_fields(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.gate_pass_no",
        "label": "Gate pass",
        "type": "text",
        "show_on_print": True,
    })
    assert field.status_code == 201, field.text

    cloned = client.post("/api/studio/print-templates", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.mill_packing",
        "label": "Mill packing",
        "is_default": True,
    })
    assert cloned.status_code == 201, cloned.text
    body = cloned.json()
    assert body["key"] == "x.mill_packing"
    assert body["is_default"] is True
    assert "{{ invoice.number }}" in (body["html"] or "")
    assert body["id"] is not None

    patched = client.put(
        f"/api/studio/print-templates/{body['id']}",
        headers=admin_headers,
        json={"html": "<p>GP {{ custom_fields['x.gate_pass_no'] }}</p>"},
    )
    assert patched.status_code == 200, patched.text

    html = render_sandboxed_html(
        patched.json()["html"],
        {"custom_fields": {"x.gate_pass_no": "GP-42"}},
    )
    assert "GP-42" in html

    inv = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "GP-42"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text

    captured = {}

    def _fake(*a, **k):
        captured.update(k)
        if a:
            captured.setdefault("invoice", a[0] if "invoice" not in k else k.get("invoice"))
        return b"%PDF-1.4 clone-fake"

    import services.pdf as pdf_mod
    orig = pdf_mod.render_invoice_pdf
    pdf_mod.render_invoice_pdf = _fake
    try:
        pdf = client.get(f"/api/invoices/{inv.json()['id']}/pdf", headers=admin_headers)
    finally:
        pdf_mod.render_invoice_pdf = orig
    assert pdf.status_code == 200, pdf.text
    assert pdf.content.startswith(b"%PDF")
    assert captured.get("custom_fields", {}).get("x.gate_pass_no") == "GP-42"
    assert captured.get("html") and "GP {{ custom_fields['x.gate_pass_no'] }}" in captured["html"]
    fields = captured.get("print_fields") or []
    assert any(f.get("key") == "x.gate_pass_no" and f.get("value") == "GP-42" for f in fields)


def test_sandbox_rejects_filesystem_include():
    try:
        render_sandboxed_html("{% include 'invoice.html' %} hi", {})
        assert False, "expected TemplateNotFound"
    except TemplateNotFound:
        pass


def test_default_pdf_still_200(client, admin_headers, monkeypatch):
    monkeypatch.setattr("services.pdf.render_invoice_pdf", lambda *a, **k: b"%PDF-1.4 default-fake")
    inv = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text
    r = client.get(f"/api/invoices/{inv.json()['id']}/pdf", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")


def test_tenant_b_cannot_fetch_a_template(client):
    a = _signup(client, "mill-a@pt.test", "Mill A")
    b = _signup(client, "clinic-b@pt.test", "Clinic B")
    cloned = client.post("/api/studio/print-templates", headers=a, json={
        "entity": "invoice", "key": "x.mill_packing", "label": "Packing",
    })
    assert cloned.status_code == 201, cloned.text
    tid = cloned.json()["id"]
    leak = client.get(f"/api/studio/print-templates/{tid}", headers=b)
    assert leak.status_code == 404, leak.text
    listed = client.get("/api/studio/print-templates?entity=invoice", headers=b)
    ids = [x.get("id") for x in listed.json() if x.get("id")]
    assert tid not in ids


def test_report_builder_x_column_and_unknown_rejected(client, admin_headers):
    field = client.post("/api/studio/fields", headers=admin_headers, json={
        "entity": "invoice",
        "key": "x.gate_pass_no",
        "label": "Gate pass",
        "type": "text",
    })
    assert field.status_code == 201, field.text
    inv = client.post("/api/invoices", headers=admin_headers, json={
        "customer_name": "Walk-in",
        "issue_date": "2026-03-01",
        "gst_rate": 0,
        "custom_fields": {"x.gate_pass_no": "GP-77"},
        "lines": [{"description": "Yarn", "qty": 1, "rate": 10}],
    })
    assert inv.status_code == 201, inv.text

    sources = client.get("/api/report-builder/sources", headers=admin_headers)
    assert sources.status_code == 200, sources.text
    inv_src = next(s for s in sources.json() if s["key"] == "invoices")
    assert any(f["key"] == "x.gate_pass_no" for f in inv_src["fields"])

    ok = client.post("/api/report-builder/run", headers=admin_headers, json={
        "source_key": "invoices",
        "config": {"columns": ["number", "x.gate_pass_no"]},
    })
    assert ok.status_code == 200, ok.text
    vals = {row.get("x.gate_pass_no") for row in ok.json()["rows"]}
    assert "GP-77" in vals

    bad = client.post("/api/report-builder/run", headers=admin_headers, json={
        "source_key": "invoices",
        "config": {"columns": ["x.nope"]},
    })
    assert bad.status_code == 400, bad.text
