"""#418 — logos/PDFs are not public; uploads sniff content, never the filename."""
from __future__ import annotations

from fastapi.testclient import TestClient

# 1×1 PNG
_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
    b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _auth(client: TestClient, email: str = "files-a@co.test") -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": "Files Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_logo_upload_and_authenticated_fetch(client: TestClient):
    auth = _auth(client)
    r = client.post(
        "/api/settings/logo",
        headers=auth,
        files={"file": ("logo.png", _PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    url = r.json()["logo_url"]
    assert url.startswith("/api/files/")
    assert "/uploads/" not in url

    got = client.get(url, headers=auth)
    assert got.status_code == 200
    assert got.content.startswith(b"\x89PNG")
    assert got.headers.get("x-content-type-options") == "nosniff"
    assert "image/png" in got.headers.get("content-type", "")

    client.cookies.clear()
    anon = client.get(url)
    assert anon.status_code in (401, 403)

    public = client.get("/uploads/1/anything.png")
    assert public.status_code in (401, 404)


def test_html_named_png_is_rejected(client: TestClient):
    auth = _auth(client, "files-html@co.test")
    r = client.post(
        "/api/settings/logo",
        headers=auth,
        files={"file": ("x.html", b"<html><script>alert(1)</script></html>", "image/png")},
    )
    assert r.status_code == 400, r.text


def test_svg_logo_rejected(client: TestClient):
    auth = _auth(client, "files-svg@co.test")
    r = client.post(
        "/api/settings/logo",
        headers=auth,
        files={"file": ("logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "image/svg+xml")},
    )
    assert r.status_code == 400, r.text


def test_cross_tenant_file_is_404(client: TestClient):
    auth_a = _auth(client, "files-ta@co.test")
    auth_b = _auth(client, "files-tb@co.test")
    r = client.post(
        "/api/settings/logo",
        headers=auth_a,
        files={"file": ("logo.png", _PNG, "image/png")},
    )
    url = r.json()["logo_url"]
    stolen = client.get(url, headers=auth_b)
    assert stolen.status_code == 404


def test_generated_pdf_key_is_not_public(client: TestClient, tmp_path, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    from importlib import reload
    import local_config
    import services.storage as storage
    reload(local_config)
    reload(storage)
    storage.upload_file("99/pdfs/INV-1.pdf", b"%PDF-fake", "application/pdf")
    public = client.get("/uploads/99/pdfs/INV-1.pdf")
    assert public.status_code in (401, 404)
