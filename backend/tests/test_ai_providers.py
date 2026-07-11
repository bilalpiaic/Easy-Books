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


def test_env_fallback_applies_to_anthropic_only(client, monkeypatch):
    from services.ai_providers import configured_providers, resolve_api_key
    tid = _tenant(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    with Session(_db.engine) as s:
        provs = configured_providers(s, tid)
        assert [p["provider"] for p in provs] == ["anthropic"]
        assert resolve_api_key(s, tid, "anthropic") == "sk-ant-env"
        assert resolve_api_key(s, tid, "openai") is None
        assert resolve_api_key(s, tid, "gemini") is None


def test_tenant_key_wins_over_env(client, monkeypatch):
    from services.ai_providers import resolve_api_key
    tid = _tenant(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-env")
    _set_key(tid, "ai_api_key_anthropic", "sk-ant-tenant")
    with Session(_db.engine) as s:
        assert resolve_api_key(s, tid, "anthropic") == "sk-ant-tenant"


def test_validate_model_happy_and_sad_paths(client, monkeypatch):
    from services.ai_providers import validate_model
    tid = _tenant(monkeypatch)
    _set_key(tid, "ai_api_key_gemini", "AIza-test")
    with Session(_db.engine) as s:
        litellm_model, key = validate_model(s, tid, "gemini/gemini-2.5-flash")
        assert litellm_model == "gemini/gemini-2.5-flash"
        assert key == "AIza-test"
        with pytest.raises(ValueError):
            validate_model(s, tid, "openai/gpt-4o-mini")     # provider not configured
        with pytest.raises(ValueError):
            validate_model(s, tid, "gemini/not-a-model")     # unknown model id
        with pytest.raises(ValueError):
            validate_model(s, tid, "made-up-string")         # bad format


def test_mask_key_shows_tail_only(client):
    from services.ai_providers import mask_key
    assert mask_key("sk-ant-abcdefgx4Kb") == "••••x4Kb"
    assert mask_key("abc") == "••••"  # too short to expose a tail
    assert mask_key("") is None
    assert mask_key(None) is None
