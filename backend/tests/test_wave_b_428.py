"""#428 — Fernet settings, SSRF, self-update off, PATCH modules can_install."""
from __future__ import annotations

from sqlmodel import Session, select

from models import Settings, WebhookDelivery, WebhookEndpoint
from services.crypto_secrets import PREFIX, decrypt_secret, encrypt_secret
from services.entitlements import PLAN_DENIED
from services.events import drain_once
from services.ssrf import public_url_error


def _signup(client, email: str, *, company: str = "Sec Co") -> dict:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "password": "password123",
            "full_name": "Owner",
            "company_name": company,
            "business_model": "simple",
        },
    )
    assert r.status_code == 200, r.text
    tok = client.post(
        "/api/auth/login",
        data={"username": email, "password": "password123"},
    )
    assert tok.status_code == 200, tok.text
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


def _session(client) -> Session:
    return Session(client.app.state.engine)


def test_get_settings_never_returns_pra_api_token(client, monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "wave-b-428-data-key")
    auth = _signup(client, "pra-secret@co.test")
    r = client.patch(
        "/api/settings",
        headers=auth,
        json={"pra_api_token": "super-secret-pra-token"},
    )
    assert r.status_code == 200, r.text
    body = client.get("/api/settings", headers=auth).json()
    assert "pra_api_token" not in body
    assert "super-secret-pra-token" not in str(body)
    with _session(client) as s:
        row = s.exec(select(Settings).where(Settings.key == "pra_api_token")).first()
        assert row is not None
        assert row.value.startswith(PREFIX)
        assert decrypt_secret(row.value) == "super-secret-pra-token"
        assert "super-secret-pra-token" not in row.value


def test_totp_survives_jwt_rotate_when_data_key_set(monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "dedicated-fernet-passphrase")
    cipher = encrypt_secret("JBSWY3DPEHPK3PXP")
    assert cipher.startswith(PREFIX)
    monkeypatch.setattr("services.crypto_secrets.SECRET_KEY", "rotated-jwt-secret-value")
    assert decrypt_secret(cipher) == "JBSWY3DPEHPK3PXP"


def test_legacy_jwt_ciphertext_still_decrypts_after_data_key(monkeypatch):
    monkeypatch.delenv("DATA_ENCRYPTION_KEY", raising=False)
    from services.crypto_secrets import _jwt_fernet

    legacy = _jwt_fernet().encrypt(b"legacy-totp-secret").decode()
    assert not legacy.startswith(PREFIX)
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "new-primary-after-jwt")
    assert decrypt_secret(legacy) == "legacy-totp-secret"


def test_webhook_metadata_ip_rejected_on_save(client, admin_headers):
    r = client.post(
        "/api/webhooks",
        headers=admin_headers,
        json={"url": "http://169.254.169.254/latest/meta-data/", "events": ["invoice.created"]},
    )
    assert r.status_code == 400, r.text
    assert "private" in r.json()["detail"].lower() or "metadata" in r.json()["detail"].lower()


def test_webhook_ssrf_blocked_at_send_time(client, admin_headers):
    created = client.post(
        "/api/webhooks",
        headers=admin_headers,
        json={"url": "https://hooks.example/eb", "events": ["customer.created"]},
    )
    assert created.status_code == 201, created.text
    client.post("/api/customers", headers=admin_headers, json={"name": "SSRF Co"})
    posted = []

    def fake_post(url, body, headers):
        posted.append(url)
        return 200, ""

    with _session(client) as s:
        ep = s.get(WebhookEndpoint, created.json()["id"])
        ep.url = "http://169.254.169.254/latest/meta-data/"
        s.add(ep)
        s.commit()
        n = drain_once(s, post=fake_post)
        assert n == 1
        d = s.exec(select(WebhookDelivery)).one()
        assert posted == []
        assert d.status == "pending"
        assert "SSRF" in (d.last_error or "")


def test_self_update_404_in_production(client, admin_headers, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("REQUIRE_OWNER_TOTP", "false")
    monkeypatch.delenv("ENABLE_SELF_UPDATE", raising=False)
    r = client.post("/api/system/update", headers=admin_headers)
    assert r.status_code == 404
    status = client.get("/api/system/update/status", headers=admin_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "up_to_date"
    assert status.json()["behind"] is False


def test_self_update_disabled_when_app_role_set(monkeypatch):
    from services.app_runtime import self_update_enabled

    monkeypatch.delenv("ENABLE_SELF_UPDATE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("ENV", raising=False)
    monkeypatch.setenv("APP_ROLE", "api")
    assert self_update_enabled() is False
    monkeypatch.delenv("APP_ROLE", raising=False)
    monkeypatch.setenv("ENABLE_SELF_UPDATE", "true")
    assert self_update_enabled() is True


def test_free_plan_patch_modules_spinning_403(client, monkeypatch):
    monkeypatch.setenv("ENFORCE_MODULE_PLANS", "true")
    auth = _signup(client, "free-patch-mod@test.com")
    r = client.patch(
        "/api/settings/modules",
        headers=auth,
        json={"enabled_modules": ["base", "spinning"]},
    )
    assert r.status_code == 403, r.text
    assert PLAN_DENIED in r.json()["detail"]


def test_ssrf_allows_unresolved_public_host_and_ollama_loopback():
    assert public_url_error("https://hooks.example/eb") is None
    assert public_url_error("http://localhost:11434", allow_loopback=True) is None
    assert public_url_error("http://127.0.0.1:11434") is not None
    assert public_url_error("http://169.254.169.254/") is not None
    assert public_url_error("ftp://example.com") is not None


def test_settings_url_fields_reject_metadata(client, admin_headers):
    r = client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"marketplace_catalog_url": "http://169.254.169.254/catalog.json"},
    )
    assert r.status_code == 400, r.text
    ok = client.patch(
        "/api/settings",
        headers=admin_headers,
        json={"ai_ollama_base_url": "http://localhost:11434"},
    )
    assert ok.status_code == 200, ok.text


def test_encrypt_settings_script_is_idempotent(client, monkeypatch):
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "script-seal-key")
    auth = _signup(client, "seal-script@co.test")
    client.patch("/api/settings", headers=auth, json={"pra_api_token": "tok-plain"})
    from scripts.encrypt_settings import encrypt_settings_rows

    with _session(client) as s:
        first = encrypt_settings_rows(s, dry_run=False)
        # PATCH already sealed; script must no-op.
        assert first["sealed"] == 0
        row = s.exec(select(Settings).where(Settings.key == "pra_api_token")).one()
        row.value = "still-plain"
        s.add(row)
        s.commit()
        second = encrypt_settings_rows(s, dry_run=False)
        assert second["sealed"] == 1
        row = s.exec(select(Settings).where(Settings.key == "pra_api_token")).one()
        assert row.value.startswith(PREFIX)
        assert decrypt_secret(row.value) == "still-plain"
        third = encrypt_settings_rows(s, dry_run=False)
        assert third["sealed"] == 0


def test_ensure_notice_table_skips_runtime_ddl_in_production(monkeypatch):
    import services.update_notices as un

    monkeypatch.setenv("APP_ENV", "production")
    un._notice_table_ready = False
    un.ensure_notice_table(session=None)
    assert un._notice_table_ready is True
    un._notice_table_ready = False
