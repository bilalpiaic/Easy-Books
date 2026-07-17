"""Multi-provider LLM registry for the AI Financial Assistant (#117).

Single source of truth for which providers/models exist, how their API
keys resolve (tenant Settings KV wins; ANTHROPIC_API_KEY env is a
dev/demo fallback for the anthropic provider only), and what the chat
UI's model dropdown may offer. All key material stays server-side —
callers that need to show key state use mask_key().

Ollama is a self-hosted provider, not a cloud one: no secret key, and no
fixed model catalog — a tenant tags whichever local models they've pulled
(GET /api/tags on their own Ollama server) via Settings -> AI, stored as a
comma-separated `ai_ollama_models` string. `PROVIDERS["ollama"]["models"]`
is deliberately empty; ollama_models()/ollama_base_url() resolve the
tenant-specific list instead."""
import os
from typing import Optional

from sqlmodel import Session, select

from models import Settings

PROVIDERS: dict[str, dict] = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "settings_key": "ai_api_key_anthropic",
        "env_fallback": "ANTHROPIC_API_KEY",
        # claude-sonnet-4-6 kept selectable for tenants already using it
        "models": ["claude-sonnet-5", "claude-sonnet-4-6", "claude-haiku-4-5"],
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "settings_key": "ai_api_key_openai",
        "env_fallback": None,
        "models": ["gpt-4o-mini", "gpt-4o"],
    },
    "gemini": {
        "label": "Google (Gemini)",
        "settings_key": "ai_api_key_gemini",
        "env_fallback": None,
        # Dated gemini-2.5-* IDs are being sunset by Google for newer API
        # keys ("model ... is no longer available to new users" -- a 404
        # from the Gemini API itself, confirmed live 2026-07-14). The
        # "-latest" aliases are Google's own auto-updating pointer to the
        # current recommended model and stay available regardless of
        # account age; dated IDs kept selectable for tenants whose key
        # still has access to them.
        "models": ["gemini-flash-latest", "gemini-pro-latest", "gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.5-pro"],
    },
    "ollama": {
        "label": "Ollama (Local)",
        "settings_key": None,   # no secret -- self-hosted, gated by tagged models instead
        "env_fallback": None,
        "models": [],           # dynamic per tenant; see ollama_models()
    },
}

DEFAULT_MODEL = "anthropic/claude-sonnet-5"

OLLAMA_BASE_URL_SETTING = "ai_ollama_base_url"
OLLAMA_MODELS_SETTING = "ai_ollama_models"
OLLAMA_DEFAULT_BASE_URL = "http://localhost:11434"

# Settings keys that must never leave the server unredacted.
AI_SECRET_SETTINGS_KEYS = frozenset(
    cfg["settings_key"] for cfg in PROVIDERS.values() if cfg["settings_key"]
)


def _setting(session: Session, tenant_id: int, key: str) -> Optional[str]:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row and row.value else None


def resolve_api_key(session: Session, tenant_id: int, provider: str) -> Optional[str]:
    cfg = PROVIDERS.get(provider)
    if not cfg or not cfg["settings_key"]:
        return None
    tenant_key = _setting(session, tenant_id, cfg["settings_key"])
    if tenant_key:
        return tenant_key
    if cfg["env_fallback"]:
        return os.environ.get(cfg["env_fallback"]) or None
    return None


def ollama_models(session: Session, tenant_id: int) -> list[str]:
    """Tenant-tagged local model names (Settings -> AI), comma-separated in
    storage. Order preserved, duplicates dropped, blanks filtered."""
    raw = _setting(session, tenant_id, OLLAMA_MODELS_SETTING) or ""
    seen: dict[str, None] = {}
    for tag in raw.split(","):
        tag = tag.strip()
        if tag:
            seen.setdefault(tag, None)
    return list(seen)


def ollama_base_url(session: Session, tenant_id: int) -> str:
    return _setting(session, tenant_id, OLLAMA_BASE_URL_SETTING) or OLLAMA_DEFAULT_BASE_URL


def configured_providers(session: Session, tenant_id: int) -> list[dict]:
    """Providers ready to use — the /api/ai/models payload. Cloud providers
    need a resolvable key; Ollama needs at least one tagged model."""
    default_model = _setting(session, tenant_id, "ai_default_model") or DEFAULT_MODEL
    out = []
    for provider, cfg in PROVIDERS.items():
        if provider == "ollama":
            tags = ollama_models(session, tenant_id)
            if not tags:
                continue
            out.append({
                "provider": provider,
                "label": cfg["label"],
                "models": [f"ollama/{m}" for m in tags],
            })
            continue
        if resolve_api_key(session, tenant_id, provider) is None:
            continue
        out.append({
            "provider": provider,
            "label": cfg["label"],
            "models": [f"{provider}/{m}" for m in cfg["models"]],
        })
    # The tenant default only counts if its provider is configured;
    # otherwise fall back to the FIRST configured provider's FIRST model
    # (registry order — deliberately not sorted(), which would put
    # "gpt-4o" ahead of "gpt-4o-mini").
    valid = {m for p in out for m in p["models"]}
    fallback = out[0]["models"][0] if out else None
    for p in out:
        p["default"] = default_model if default_model in valid else fallback
    return out


def validate_model(session: Session, tenant_id: int, model: str) -> tuple[str, Optional[str], Optional[str]]:
    """Return (litellm_model_string, api_key, api_base) or raise ValueError.

    api_key is None for Ollama (no cloud credential); api_base is None for
    every provider except Ollama (which needs it to reach the tenant's own
    server instead of a public API endpoint)."""
    if "/" not in model:
        raise ValueError(f"Unknown model: {model!r}")
    provider, _, model_id = model.partition("/")
    cfg = PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"Unknown model: {model!r}")
    if provider == "ollama":
        if model_id not in ollama_models(session, tenant_id):
            raise ValueError(f"Unknown model: {model!r}")
        return model, None, ollama_base_url(session, tenant_id)
    if model_id not in cfg["models"]:
        raise ValueError(f"Unknown model: {model!r}")
    key = resolve_api_key(session, tenant_id, provider)
    if not key:
        raise ValueError(f"Provider '{provider}' is not configured")
    return model, key, None


# Cheap/fast model per provider — used by the AI chat pipeline's triage
# (routing) and drafting (formatting) stages so only the specialist stage's
# actual analysis pays for the (possibly much pricier) model the user
# selected. No entry for ollama: self-hosted has no cost-tiering concept, so
# those stages just fall through to whatever model the user picked.
CHEAP_TIER: dict[str, str] = {
    "anthropic": "claude-haiku-4-5",
    "openai": "gpt-4o-mini",
    # "-latest" alias, not a dated ID — see the sunset note on PROVIDERS above.
    "gemini": "gemini-flash-latest",
}


def resolve_cheap_tier(
    session: Session, tenant_id: int,
    litellm_model: str, api_key: Optional[str], api_base: Optional[str],
) -> tuple[str, Optional[str], Optional[str]]:
    """Cheap-tier (model, key, base) for the same provider as `litellm_model`,
    falling back to the exact triple passed in if there's no cheap-tier entry
    for that provider (ollama) or the mapped model is no longer valid (e.g.
    removed from PROVIDERS) — never raises, always returns something usable.
    """
    provider = litellm_model.partition("/")[0]
    cheap_model_id = CHEAP_TIER.get(provider)
    if not cheap_model_id:
        return litellm_model, api_key, api_base
    try:
        return validate_model(session, tenant_id, f"{provider}/{cheap_model_id}")
    except ValueError:
        return litellm_model, api_key, api_base


def mask_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if len(value) <= 8:
        return "•" * 4
    return "•" * 4 + value[-4:]
