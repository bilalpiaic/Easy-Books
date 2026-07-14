"""Multi-provider LLM registry for the AI Financial Assistant (#117).

Single source of truth for which providers/models exist, how their API
keys resolve (tenant Settings KV wins; ANTHROPIC_API_KEY env is a
dev/demo fallback for the anthropic provider only), and what the chat
UI's model dropdown may offer. All key material stays server-side —
callers that need to show key state use mask_key()."""
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
}

DEFAULT_MODEL = "anthropic/claude-sonnet-5"

# Settings keys that must never leave the server unredacted.
AI_SECRET_SETTINGS_KEYS = frozenset(
    cfg["settings_key"] for cfg in PROVIDERS.values()
)


def _setting(session: Session, tenant_id: int, key: str) -> Optional[str]:
    row = session.exec(
        select(Settings).where(Settings.tenant_id == tenant_id, Settings.key == key)
    ).first()
    return row.value if row and row.value else None


def resolve_api_key(session: Session, tenant_id: int, provider: str) -> Optional[str]:
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return None
    tenant_key = _setting(session, tenant_id, cfg["settings_key"])
    if tenant_key:
        return tenant_key
    if cfg["env_fallback"]:
        return os.environ.get(cfg["env_fallback"]) or None
    return None


def configured_providers(session: Session, tenant_id: int) -> list[dict]:
    """Providers with a resolvable key — the /api/ai/models payload."""
    default_model = _setting(session, tenant_id, "ai_default_model") or DEFAULT_MODEL
    out = []
    for provider, cfg in PROVIDERS.items():
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


def validate_model(session: Session, tenant_id: int, model: str) -> tuple[str, str]:
    """Return (litellm_model_string, api_key) or raise ValueError."""
    if "/" not in model:
        raise ValueError(f"Unknown model: {model!r}")
    provider, _, model_id = model.partition("/")
    cfg = PROVIDERS.get(provider)
    if not cfg or model_id not in cfg["models"]:
        raise ValueError(f"Unknown model: {model!r}")
    key = resolve_api_key(session, tenant_id, provider)
    if not key:
        raise ValueError(f"Provider '{provider}' is not configured")
    return model, key


def mask_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if len(value) <= 8:
        return "•" * 4
    return "•" * 4 + value[-4:]
