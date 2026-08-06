"""#117 completion — provider registry: key resolution, masking, model validation."""
import pytest
from sqlmodel import Session

import db as _db
from models import Settings, Tenant


def _tenant(monkeypatch) -> int:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with Session(_db.engine) as s:
        t = Tenant(name="ProvCo")
        s.add(t); s.commit(); s.refresh(t)
        return t.id


def _set_key(tenant_id: int, key: str, value: str) -> None:
    with Session(_db.engine) as s:
        s.add(Settings(tenant_id=tenant_id, key=key, value=value))
        s.commit()


def test_no_keys_no_env_means_no_providers(client, monkeypatch):
    from services.ai_providers import configured_providers
    tid = _tenant(monkeypatch)
    with Session(_db.engine) as s:
        assert configured_providers(s, tid) == []


def test_env_fallback_applies_to_anthropic_and_xai(client, monkeypatch):
    from services.ai_providers import configured_providers, resolve_api_key
    tid = _tenant(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    monkeypatch.setenv("XAI_API_KEY", "xai-env-key")
    with Session(_db.engine) as s:
        provs = configured_providers(s, tid)
        assert [p["provider"] for p in provs] == ["anthropic", "xai"]
        assert resolve_api_key(s, tid, "anthropic") == "sk-ant-env"
        assert resolve_api_key(s, tid, "xai") == "xai-env-key"
        assert resolve_api_key(s, tid, "openai") is None
        assert resolve_api_key(s, tid, "gemini") is None


def test_xai_cursor_grok_provider_models_and_cheap_tier(client, monkeypatch):
    """xAI / Cursor Grok is a first-class cloud provider alongside Claude/GPT/Gemini."""
    from services.ai_providers import (
        CHEAP_TIER, PROVIDERS, configured_providers, resolve_cheap_tier, validate_model,
    )
    assert "xai" in PROVIDERS
    assert "grok-4.5" in PROVIDERS["xai"]["models"]
    assert CHEAP_TIER["xai"] == "grok-4-1-fast-non-reasoning"

    tid = _tenant(monkeypatch)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    _set_key(tid, "ai_api_key_xai", "xai-tenant-key-abc1")
    with Session(_db.engine) as s:
        litellm_model, key, api_base = validate_model(s, tid, "xai/grok-4.5")
        assert litellm_model == "xai/grok-4.5"
        assert key == "xai-tenant-key-abc1"
        assert api_base is None

        cheap_model, cheap_key, _ = resolve_cheap_tier(
            s, tid, litellm_model, key, api_base,
        )
        assert cheap_model == "xai/grok-4-1-fast-non-reasoning"
        assert cheap_key == "xai-tenant-key-abc1"

        provs = configured_providers(s, tid)
        assert any(p["provider"] == "xai" for p in provs)
        xai = next(p for p in provs if p["provider"] == "xai")
        assert xai["label"] == "xAI / Cursor Grok"
        assert "xai/grok-4.5" in xai["models"]
        assert "xai/grok-code-fast" in xai["models"]


def test_tenant_key_wins_over_env(client, monkeypatch):
    from services.ai_providers import resolve_api_key
    tid = _tenant(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    monkeypatch.setenv("XAI_API_KEY", "xai-env")
    _set_key(tid, "ai_api_key_anthropic", "sk-ant-tenant")
    _set_key(tid, "ai_api_key_xai", "xai-tenant")
    with Session(_db.engine) as s:
        assert resolve_api_key(s, tid, "anthropic") == "sk-ant-tenant"
        assert resolve_api_key(s, tid, "xai") == "xai-tenant"


def test_validate_model_happy_and_sad_paths(client, monkeypatch):
    from services.ai_providers import validate_model
    tid = _tenant(monkeypatch)
    _set_key(tid, "ai_api_key_gemini", "AIza-test")
    with Session(_db.engine) as s:
        litellm_model, key, api_base = validate_model(s, tid, "gemini/gemini-2.5-flash")
        assert litellm_model == "gemini/gemini-2.5-flash"
        assert key == "AIza-test"
        assert api_base is None
        with pytest.raises(ValueError):
            validate_model(s, tid, "openai/gpt-4o-mini")     # provider not configured
        with pytest.raises(ValueError):
            validate_model(s, tid, "gemini/not-a-model")     # unknown model id
        with pytest.raises(ValueError):
            validate_model(s, tid, "made-up-string")         # bad format


def test_ollama_models_are_tenant_tagged_not_a_fixed_catalog(client, monkeypatch):
    """Ollama has no cloud key and no fixed model list -- it's configured once
    the tenant tags at least one locally-pulled model name, and validate_model
    must check against that tenant-specific tag list, not PROVIDERS[...]["models"]
    (which is deliberately empty for ollama)."""
    from services.ai_providers import (
        configured_providers, ollama_base_url, ollama_models, validate_model,
    )
    tid = _tenant(monkeypatch)
    with Session(_db.engine) as s:
        assert ollama_models(s, tid) == []
        assert ollama_base_url(s, tid) == "http://localhost:11434"
        assert configured_providers(s, tid) == []   # no tags yet -> not configured
        with pytest.raises(ValueError):
            validate_model(s, tid, "ollama/llama3.1")

    _set_key(tid, "ai_ollama_models", "llama3.1:8b, mistral,, llama3.1:8b")  # dupes/blank collapse
    _set_key(tid, "ai_ollama_base_url", "http://gpu-box.local:11434")
    with Session(_db.engine) as s:
        assert ollama_models(s, tid) == ["llama3.1:8b", "mistral"]
        assert ollama_base_url(s, tid) == "http://gpu-box.local:11434"

        provs = configured_providers(s, tid)
        assert [p["provider"] for p in provs] == ["ollama"]
        assert provs[0]["models"] == ["ollama/llama3.1:8b", "ollama/mistral"]
        assert provs[0]["default"] == "ollama/llama3.1:8b"

        litellm_model, key, api_base = validate_model(s, tid, "ollama/mistral")
        assert litellm_model == "ollama/mistral"
        assert key is None
        assert api_base == "http://gpu-box.local:11434"

        with pytest.raises(ValueError):
            validate_model(s, tid, "ollama/not-tagged")


def test_mask_key_shows_tail_only(client):
    from services.ai_providers import mask_key
    assert mask_key("sk-ant-abcdefgx4Kb") == "••••x4Kb"
    assert mask_key("abc") == "••••"  # too short to expose a tail
    assert mask_key("") is None
    assert mask_key(None) is None


def _signup(client, email):
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_ai(client, auth):
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def test_settings_get_redacts_ai_keys(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "prov1@t.com")
    r = client.patch("/api/settings", headers=auth, json={
        "ai_api_key_openai": "sk-openai-supersecret-x9Zq",
        "ai_default_model": "openai/gpt-4o-mini",
    })
    assert r.status_code == 200, r.text
    settings = client.get("/api/settings", headers=auth).json()
    assert "ai_api_key_openai" not in settings          # redacted entirely
    assert settings["ai_default_model"] == "openai/gpt-4o-mini"
    # and no raw secret anywhere in the payload
    assert "supersecret" not in str(settings)


def test_models_endpoint_lists_only_configured_providers(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "prov2@t.com")
    _install_ai(client, auth)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_gemini": "AIza-test"})

    data = client.get("/api/ai/models", headers=auth).json()
    assert [p["provider"] for p in data["providers"]] == ["gemini"]
    assert "gemini/gemini-2.5-flash" in data["providers"][0]["models"]
    # gemini-2.5-flash/-pro are being sunset by Google for newer API keys
    # ("no longer available to new users" -- a live 404 from the Gemini
    # API). The auto-updating "-latest" alias must be the default a fresh
    # tenant gets, not a dated ID that may already be dead for their key.
    assert data["providers"][0]["default"] == "gemini/gemini-flash-latest"


def test_key_status_masked_and_admin_only(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    auth = _signup(client, "prov3@t.com")
    _install_ai(client, auth)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-openai-secret-x9Zq"})

    status = client.get("/api/ai/key-status", headers=auth).json()
    assert status["openai"] == "••••x9Zq"
    assert status["anthropic"] is None
    assert status["xai"] is None
    assert "secret" not in str(status)

    # viewer-role user cannot read key status
    client.post("/api/users", headers=auth, json={
        "email": "prov3v@t.com", "password": "password123",
        "full_name": "V", "role": "viewer",
    })
    r = client.post("/api/auth/login", data={"username": "prov3v@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/ai/key-status", headers=viewer).status_code == 403


def test_xai_key_round_trip_via_settings_and_models(client, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    auth = _signup(client, "prov-xai@t.com")
    _install_ai(client, auth)
    r = client.patch("/api/settings", headers=auth, json={
        "ai_api_key_xai": "xai-live-secret-9Zq1",
        "ai_default_model": "xai/grok-4.5",
    })
    assert r.status_code == 200, r.text

    settings = client.get("/api/settings", headers=auth).json()
    assert "ai_api_key_xai" not in settings
    assert settings["ai_default_model"] == "xai/grok-4.5"

    status = client.get("/api/ai/key-status", headers=auth).json()
    assert status["xai"] == "••••9Zq1"

    data = client.get("/api/ai/models", headers=auth).json()
    assert any(p["provider"] == "xai" for p in data["providers"])
    xai = next(p for p in data["providers"] if p["provider"] == "xai")
    assert "xai/grok-4.5" in xai["models"]
    assert data["default_model"] == "xai/grok-4.5"


def test_ai_key_write_requires_admin(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "prov4@t.com")  # tenant creator is owner
    client.post("/api/users", headers=auth, json={
        "email": "prov4a@t.com", "password": "password123",
        "full_name": "A", "role": "accountant",
    })
    r = client.post("/api/auth/login", data={"username": "prov4a@t.com", "password": "password123"})
    accountant = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # accountant (below admin) cannot set an AI provider key
    r = client.patch("/api/settings", headers=accountant, json={"ai_api_key_openai": "sk-blocked"})
    assert r.status_code == 403, r.text
    assert client.get("/api/ai/key-status", headers=auth).json()["openai"] is None

    # accountant CAN still write ordinary, non-secret settings
    r = client.patch("/api/settings", headers=accountant, json={"company_name": "Renamed Co"})
    assert r.status_code == 200, r.text

    # owner can set the key
    r = client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-owner-set-x9Zq"})
    assert r.status_code == 200, r.text
    assert client.get("/api/ai/key-status", headers=auth).json()["openai"] == "••••x9Zq"
