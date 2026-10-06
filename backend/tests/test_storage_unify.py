"""#426 — unified object keys for logos, avatars, attachments, PDFs."""
from __future__ import annotations

from fastapi.testclient import TestClient

from services.storage import object_key

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f"
    b"\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _auth(client: TestClient, email: str) -> dict:
    client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": "Store Co",
            "business_model": "simple",
        },
    )
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    token = r.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_object_key_shape():
    assert object_key(7, "logo", "a.png") == "tenants/7/logo/a.png"
    assert object_key(7, "attachment", "../x.pdf") == "tenants/7/attachment/x.pdf"


def test_logo_uses_canonical_key(client: TestClient):
    auth = _auth(client, "store-logo@co.test")
    r = client.post(
        "/api/settings/logo",
        headers=auth,
        files={"file": ("logo.png", _PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    url = r.json()["logo_url"]
    assert "/api/files/tenants/" in url
    assert "/logo/" in url
    got = client.get(url, headers=auth)
    assert got.status_code == 200
    assert got.content.startswith(b"\x89PNG")


def test_avatar_roundtrip_via_storage(client: TestClient):
    auth = _auth(client, "store-av@co.test")
    r = client.post(
        "/api/auth/me/avatar",
        headers=auth,
        files={"file": ("me.png", _PNG, "image/png")},
    )
    assert r.status_code == 200, r.text
    url = r.json()["avatar_url"]
    assert "/api/files/tenants/" in url
    assert "/avatar/" in url
    me = client.get("/api/auth/me", headers=auth).json()
    got = client.get(f"/api/auth/users/{me['id']}/avatar", headers=auth)
    assert got.status_code == 200
    assert got.content.startswith(b"\x89PNG")
    files = client.get(url.split("?")[0], headers=auth)
    assert files.status_code == 200


def test_attachment_works_without_supabase(client: TestClient):
    auth = _auth(client, "store-att@co.test")
    inv = client.post(
        "/api/invoices",
        headers=auth,
        json={
            "issue_date": "2026-01-01",
            "customer_name": "Att Co",
            "lines": [{"description": "svc", "qty": 1, "rate": 10}],
        },
    )
    assert inv.status_code == 201, inv.text
    iid = inv.json()["id"]
    r = client.post(
        "/api/attachments",
        headers=auth,
        data={"parent_type": "invoice", "parent_id": str(iid)},
        files={"file": ("note.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["file_path"].startswith("tenants/")
    assert "/attachment/" in body["file_path"]
    preview = client.get(f"/api/attachments/{body['id']}/preview", headers=auth)
    assert preview.status_code == 200
    assert preview.content.startswith(b"%PDF")
    listed = client.get(
        "/api/attachments",
        headers=auth,
        params={"parent_type": "invoice", "parent_id": iid},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert client.delete(f"/api/attachments/{body['id']}", headers=auth).status_code == 204


def test_migrate_storage_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setenv("EB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    from importlib import reload
    import local_config
    import services.storage as storage
    reload(local_config)
    reload(storage)
    from scripts.migrate_storage import migrate_local_files
    root = local_config.uploads_dir()
    legacy = root / "3" / "pdfs"
    legacy.mkdir(parents=True)
    (legacy / "INV-1.pdf").write_bytes(b"%PDF-old")
    first = migrate_local_files(dry_run=False)
    assert first["copied"] >= 1
    assert storage.download_file("tenants/3/pdf/INV-1.pdf") == b"%PDF-old"
    second = migrate_local_files(dry_run=False)
    assert second["copied"] == 0
    assert second["exists"] >= 1
