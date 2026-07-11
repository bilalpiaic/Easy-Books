# AI Chat L1 Completion Implementation Plan — Multi-Provider, SSE, Sessions (#117)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close #117's remaining acceptance criteria — SSE streaming, persisted chat sessions, rate limiting, an `/agent` page — and add multi-provider model selection (Anthropic/OpenAI/Gemini) via LiteLLM with per-tenant keys.

**Architecture:** The agent loop in `routers/ai_chat.py` is rewritten once around `litellm.acompletion(..., stream=True)` in the OpenAI message/tool format (the 7 existing tool definitions convert at import time; their executor functions are reused unchanged). `POST /api/ai/chat` becomes an `async def` SSE endpoint (`token`/`tool_start`/`tool_end`/`done`/`error` events); history moves server-side into new `AiChatSession`/`AiChatMessage` tables (per-user private). Provider keys live in the per-tenant Settings KV, redacted from every read path; a registry service (`services/ai_providers.py`) is the single source for the settings card and the chat dropdown. Spec: `docs/superpowers/specs/2026-07-11-ai-chat-l1-completion-design.md`.

**Tech Stack:** FastAPI + SQLModel + Alembic + LiteLLM (backend), Next.js 16 App Router + Tailwind v4 (frontend), pytest with mocked `litellm.acompletion`.

## Global Constraints

- **Execution prerequisite: PR #145 (Purchase/Store Phase 3+4) must be merged and the branch created from the updated main.** Migration `0033_ai_chat_sessions` revises `0032_store_issue`, which exists only on that PR's branch today. Verify before Task 1: `ls backend/alembic/versions/ | grep 0032` in the execution worktree.
- Run backend tests from `backend/` as: `PYTHONPATH=. uv run pytest tests/<file> -q`, FOREGROUND only.
- 2 documented pre-existing failures on main (`test_account_hierarchy.py::test_cannot_create_child_under_posted_account`, `test_update_migration.py::test_upgrade_over_create_all_db_is_safe`) — not yours, don't chase. `tests/test_local_packaging.py` has 2 order-dependent failures when `database.db` doesn't pre-exist — also pre-existing.
- All new tables tenant-scoped AND user-scoped: every AiChatSession/AiChatMessage query filters `tenant_id` **and** `user_id` (sessions are per-user private — same-tenant colleagues must NOT see each other's chats).
- Migration: new file `0033_ai_chat_sessions.py`, revises `0032_store_issue`; `bind.dialect.has_table(...)` guards per repo convention.
- Provider registry model IDs (pinned; litellm string = `<provider>/<id>`): anthropic → `claude-sonnet-4-6`, `claude-haiku-4-5`; openai → `gpt-4o-mini`, `gpt-4o`; gemini → `gemini-2.5-flash`, `gemini-2.5-pro`. Default model (no setting): `anthropic/claude-sonnet-4-6`.
- Settings keys: `ai_api_key_anthropic`, `ai_api_key_openai`, `ai_api_key_gemini` (secrets — REDACTED from `GET /api/settings`), `ai_default_model`, `ai_rate_limit_per_hour` (default 20). Existing `ANTHROPIC_API_KEY` env var remains the fallback for the anthropic provider ONLY.
- The 7 tool executors (`_execute_tool` and the report functions it calls) are reused as-is — do NOT re-implement business logic; only the wire format around them changes.
- Existing behavior gates keep their semantics: module gate (`ai_assistant` installed → else 403), `MAX_MESSAGE_CHARS = 4000` (→ 400), `MAX_HISTORY = 20` (now applied server-side when loading session messages), `MAX_STEPS = 6`.
- SSE endpoint: pre-stream failures are plain HTTP errors (403/400/404/429/503); after streaming starts, failures are `{"type":"error"}` events. Every `data:` line is JSON with a `type` field.
- Frontend: every new route in BOTH `NAV` and `SUB_NAV` (+`SECTION_PREFIXES` when the path prefix is new) in `frontend/src/lib/nav.ts`; page titles in `frontend/src/lib/navTitles.ts` (NOT layout.tsx — TITLE_MAP moved there); dates via `fmtDate()`; icons lucide-react only. `apiFetch` cannot consume SSE — the stream reader uses raw `fetch` + `getAuthHeader()` from `@/lib/auth`.
- Frontend verification per task: from worktree's `frontend/`: `npx tsc --noEmit` + scoped `npx eslint` on changed files.
- Commit after every task with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Subagent dispatch hygiene (controller): pin the exact worktree path + `git rev-parse --show-toplevel` check in EVERY dispatch prompt, implementers AND fixers.

---

### Task 1: LiteLLM dependency + provider registry service

**Files:**
- Modify: `backend/pyproject.toml` (add `"litellm>=1.55.0"` to `dependencies`)
- Create: `backend/services/ai_providers.py`
- Test: `backend/tests/test_ai_providers.py` (new)

**Interfaces:**
- Produces: `PROVIDERS` dict; `resolve_api_key(session, tenant_id, provider) -> Optional[str]`; `configured_providers(session, tenant_id) -> list[dict]` (the `/api/ai/models` payload builder); `validate_model(session, tenant_id, model) -> tuple[str, str]` returning `(litellm_model_string, api_key)` or raising `ValueError`; `mask_key(value) -> str`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_providers.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_providers.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.ai_providers'`

- [ ] **Step 3: Add the dependency**

In `backend/pyproject.toml`, append to `dependencies` after the `anthropic` line:

```toml
    "litellm>=1.55.0",
```

Run: `uv sync` (from `backend/`). Then `git checkout -- uv.lock && uv lock` if the lock churns unrelated packages — commit whatever `uv lock` produces (the lockfile change IS part of this task).

- [ ] **Step 4: Implement `backend/services/ai_providers.py`**

```python
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
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5"],
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
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
    },
}

DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"

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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_providers.py -q`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/services/ai_providers.py backend/tests/test_ai_providers.py
git commit -m "feat(ai): litellm dependency + multi-provider registry service (#117)"
```

---

### Task 2: Chat session models + migration 0033 + session CRUD endpoints

**Files:**
- Modify: `backend/models.py` (append after `StoreIssueLine`)
- Create: `backend/alembic/versions/0033_ai_chat_sessions.py`
- Modify: `backend/routers/ai_chat.py` (session CRUD endpoints only — the chat rewrite is Task 4)
- Test: `backend/tests/test_ai_sessions.py` (new)

**Interfaces:**
- Produces: `models.AiChatSession` (`id, tenant_id, user_id, title, created_at, updated_at`), `models.AiChatMessage` (`id, session_id, role, content, model, created_at`); endpoints `GET/POST /api/ai/sessions`, `PATCH/DELETE /api/ai/sessions/{id}`, `GET /api/ai/sessions/{id}/messages`; helper `_get_session_or_404(session, user, session_id) -> AiChatSession` (Task 4 reuses it).

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ai_sessions.py`:

```python
"""#117 completion — chat sessions: CRUD, per-user privacy, cascade."""
from fastapi.testclient import TestClient


def _signup(client: TestClient, email: str) -> dict:
    client.post("/api/auth/signup", json={
        "email": email, "password": "password123",
        "full_name": "U", "company_name": "Co", "business_model": "simple",
    })
    r = client.post("/api/auth/login", data={"username": email, "password": "password123"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _install_ai(client: TestClient, auth: dict) -> None:
    r = client.post("/api/modules/ai_assistant/install", headers=auth)
    assert r.status_code in (200, 201), r.text


def test_session_crud_lifecycle(client: TestClient):
    auth = _signup(client, "ai1@t.com")
    _install_ai(client, auth)

    r = client.post("/api/ai/sessions", headers=auth, json={})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["title"] == "New chat"

    rows = client.get("/api/ai/sessions", headers=auth).json()
    assert [s["id"] for s in rows] == [sid]

    r = client.patch(f"/api/ai/sessions/{sid}", headers=auth, json={"title": "Renamed"})
    assert r.status_code == 200
    assert client.get("/api/ai/sessions", headers=auth).json()[0]["title"] == "Renamed"

    assert client.get(f"/api/ai/sessions/{sid}/messages", headers=auth).json() == []

    r = client.delete(f"/api/ai/sessions/{sid}", headers=auth)
    assert r.status_code == 200
    assert client.get("/api/ai/sessions", headers=auth).json() == []


def test_sessions_are_private_per_user_even_same_tenant(client: TestClient):
    auth_owner = _signup(client, "ai2@t.com")
    _install_ai(client, auth_owner)
    sid = client.post("/api/ai/sessions", headers=auth_owner, json={}).json()["id"]

    # second user in the SAME tenant
    client.post("/api/users", headers=auth_owner, json={
        "email": "ai2b@t.com", "password": "password123",
        "full_name": "Colleague", "role": "admin",
    })
    r = client.post("/api/auth/login", data={"username": "ai2b@t.com", "password": "password123"})
    auth_colleague = {"Authorization": f"Bearer {r.json()['access_token']}"}

    assert client.get("/api/ai/sessions", headers=auth_colleague).json() == []
    assert client.get(f"/api/ai/sessions/{sid}/messages", headers=auth_colleague).status_code == 404
    assert client.patch(f"/api/ai/sessions/{sid}", headers=auth_colleague, json={"title": "x"}).status_code == 404
    assert client.delete(f"/api/ai/sessions/{sid}", headers=auth_colleague).status_code == 404


def test_sessions_gated_by_module(client: TestClient):
    auth = _signup(client, "ai3@t.com")  # ai_assistant NOT installed
    assert client.get("/api/ai/sessions", headers=auth).status_code == 403
    assert client.post("/api/ai/sessions", headers=auth, json={}).status_code == 403
```

(Verified at plan time: the install endpoint is `POST /api/modules/{module_id}/install` — `routers/modules.py:159`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_sessions.py -q`
Expected: FAIL — 404s (routes don't exist).

- [ ] **Step 3: Add models**

In `backend/models.py`, directly after `class StoreIssueLine`:

```python
class AiChatSession(SQLModel, table=True):
    """One AI-assistant conversation (#117). Per-user private: every query
    filters tenant_id AND user_id — same-tenant colleagues never see each
    other's chats."""
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(default="New chat")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AiChatMessage(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_ai_msg_role"),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="aichatsession.id", ondelete="CASCADE", index=True)
    role: str
    content: str
    model: Optional[str] = None          # litellm model string, assistant rows
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

- [ ] **Step 4: Create migration `backend/alembic/versions/0033_ai_chat_sessions.py`**

```python
"""ai chat sessions (#117 completion)

Revision ID: 0033_ai_chat_sessions
Revises: 0032_store_issue
Create Date: 2026-07-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '0033_ai_chat_sessions'
down_revision: Union[str, Sequence[str], None] = '0032_store_issue'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if not bind.dialect.has_table(bind, 'aichatsession'):
        op.create_table('aichatsession',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_aichatsession_tenant_id'), 'aichatsession', ['tenant_id'], unique=False)
        op.create_index(op.f('ix_aichatsession_user_id'), 'aichatsession', ['user_id'], unique=False)

    if not bind.dialect.has_table(bind, 'aichatmessage'):
        op.create_table('aichatmessage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('content', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('model', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("role IN ('user','assistant')", name='ck_ai_msg_role'),
        sa.ForeignKeyConstraint(['session_id'], ['aichatsession.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_aichatmessage_session_id'), 'aichatmessage', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_table('aichatmessage')
    op.drop_table('aichatsession')
```

- [ ] **Step 5: Add session CRUD to `backend/routers/ai_chat.py`**

Add imports (merge into the existing blocks): `from models import AiChatMessage, AiChatSession, Settings, Tenant` and `from datetime import datetime`.

Extract the existing inline module-gate into a reusable dependency-style helper and add the CRUD (place after the Pydantic schemas, before the tool registry):

```python
def _require_ai_module(session, user) -> None:
    tenant = session.get(Tenant, user.tenant_id)
    if tenant is None or "ai_assistant" not in _get_enabled(tenant):
        raise HTTPException(
            status_code=403,
            detail="The AI Financial Assistant module is not installed. Install it from System → Apps.",
        )


def _get_session_or_404(session, user, session_id: int) -> AiChatSession:
    row = session.exec(
        select(AiChatSession).where(
            AiChatSession.id == session_id,
            AiChatSession.tenant_id == user.tenant_id,
            AiChatSession.user_id == user.id,
        )
    ).first()
    if not row:
        raise HTTPException(404, "Chat session not found")
    return row


class SessionPatch(BaseModel):
    title: str


@router.get("/sessions")
def list_sessions(session: SessionDep, user: CurrentUserDep):
    _require_ai_module(session, user)
    rows = session.exec(
        select(AiChatSession).where(
            AiChatSession.tenant_id == user.tenant_id,
            AiChatSession.user_id == user.id,
        ).order_by(AiChatSession.updated_at.desc())
    ).all()
    return [{"id": r.id, "title": r.title, "updated_at": r.updated_at} for r in rows]


@router.post("/sessions", status_code=201)
def create_session(session: SessionDep, user: CurrentUserDep):
    _require_ai_module(session, user)
    row = AiChatSession(tenant_id=user.tenant_id, user_id=user.id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return {"id": row.id, "title": row.title, "updated_at": row.updated_at}


@router.patch("/sessions/{session_id}")
def rename_session(session: SessionDep, user: CurrentUserDep, session_id: int, body: SessionPatch):
    _require_ai_module(session, user)
    row = _get_session_or_404(session, user, session_id)
    row.title = body.title.strip()[:120] or row.title
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    return {"id": row.id, "title": row.title}


@router.delete("/sessions/{session_id}")
def delete_session(session: SessionDep, user: CurrentUserDep, session_id: int):
    _require_ai_module(session, user)
    row = _get_session_or_404(session, user, session_id)
    session.delete(row)
    session.commit()
    return {"success": True}


@router.get("/sessions/{session_id}/messages")
def session_messages(session: SessionDep, user: CurrentUserDep, session_id: int):
    _require_ai_module(session, user)
    _get_session_or_404(session, user, session_id)
    rows = session.exec(
        select(AiChatMessage).where(AiChatMessage.session_id == session_id)
        .order_by(AiChatMessage.id)
    ).all()
    return [
        {"id": m.id, "role": m.role, "content": m.content, "model": m.model}
        for m in rows
    ]
```

Also replace the inline module-gate block inside the existing `ai_chat` endpoint with a call to `_require_ai_module(session, user)` (behavior identical — Task 4 rewrites that endpoint anyway).

- [ ] **Step 6: Run tests + migration**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_sessions.py -q` → 3 passed.
Run: `PYTHONPATH=. uv run alembic upgrade head` → `0033_ai_chat_sessions` applied.

- [ ] **Step 7: Commit**

```bash
git add backend/models.py backend/alembic/versions/0033_ai_chat_sessions.py backend/routers/ai_chat.py backend/tests/test_ai_sessions.py
git commit -m "feat(ai): chat session models + migration 0033 + session CRUD (#117)"
```

---

### Task 3: Settings key storage, redaction, key-status + models endpoints

**Files:**
- Modify: `backend/routers/settings.py` (`SettingsUpdate` fields + GET redaction)
- Modify: `backend/routers/ai_chat.py` (append `GET /models`, `GET /key-status`)
- Test: `backend/tests/test_ai_providers.py` (append)

**Interfaces:**
- Produces: `GET /api/ai/models` → `{"providers": [{provider,label,models[],default}], "default_model": str|null}`; `GET /api/ai/key-status` (admin+) → `{"anthropic": "••••x4Kb"|null, "openai": ..., "gemini": ...}`; settings PATCH accepts the 5 new keys; settings GET never returns raw `ai_api_key_*` values.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_ai_providers.py`:

```python
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


def test_key_status_masked_and_admin_only(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "prov3@t.com")
    _install_ai(client, auth)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-openai-secret-x9Zq"})

    status = client.get("/api/ai/key-status", headers=auth).json()
    assert status["openai"] == "••••x9Zq"
    assert status["anthropic"] is None
    assert "secret" not in str(status)

    # viewer-role user cannot read key status
    client.post("/api/users", headers=auth, json={
        "email": "prov3v@t.com", "password": "password123",
        "full_name": "V", "role": "viewer",
    })
    r = client.post("/api/auth/login", data={"username": "prov3v@t.com", "password": "password123"})
    viewer = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/api/ai/key-status", headers=viewer).status_code == 403
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_providers.py -q`
Expected: the 3 new tests FAIL (unknown settings fields are dropped silently or endpoints 404).

- [ ] **Step 3: Settings changes**

In `backend/routers/settings.py`:

(a) Add to `SettingsUpdate` (after the existing optional fields):

```python
    # AI assistant (#117) — key values are write-only; GET redacts them
    ai_api_key_anthropic: Optional[str] = None
    ai_api_key_openai: Optional[str] = None
    ai_api_key_gemini: Optional[str] = None
    ai_default_model: Optional[str] = None
    ai_rate_limit_per_hour: Optional[str] = None
```

(b) In `get_settings`, redact before returning:

```python
    from services.ai_providers import AI_SECRET_SETTINGS_KEYS
    for k in AI_SECRET_SETTINGS_KEYS:
        out.pop(k, None)
```

Note: writing an empty string via PATCH clears a key (the existing PATCH loop stores `""`, and `resolve_api_key` treats empty as unset because `_setting` returns None for falsy values).

- [ ] **Step 4: New endpoints in `backend/routers/ai_chat.py`**

Add import: `from services.ai_providers import PROVIDERS, configured_providers, mask_key, resolve_api_key` and `from .common import AdminUserDep` (merge into existing import lines).

```python
@router.get("/models")
def list_models(session: SessionDep, user: CurrentUserDep):
    _require_ai_module(session, user)
    providers = configured_providers(session, user.tenant_id)
    default = providers[0]["default"] if providers else None
    return {"providers": providers, "default_model": default}


@router.get("/key-status")
def key_status(session: SessionDep, user: AdminUserDep):
    return {
        provider: mask_key(resolve_api_key(session, user.tenant_id, provider))
        for provider in PROVIDERS
    }
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_providers.py -q` → 8 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/settings.py backend/routers/ai_chat.py backend/tests/test_ai_providers.py
git commit -m "feat(ai): per-tenant provider keys with redaction + models/key-status endpoints (#117)"
```

---

### Task 4: SSE chat endpoint — LiteLLM agent loop + rate limiting

**Files:**
- Modify: `backend/routers/ai_chat.py` (rewrite the `/chat` endpoint + tool conversion + rate limiter; keep `TOOLS`, `_execute_tool`, `_build_system_prompt`, `_json_safe`, `_get_company_name` unchanged)
- Test: `backend/tests/test_ai_chat_stream.py` (new)

**Interfaces:**
- Produces: `POST /api/ai/chat` body `{"session_id": int, "message": str, "model": str|null}` → `text/event-stream`; events `{"type":"token","text"}`, `{"type":"tool_start","label"}`, `{"type":"tool_end"}`, `{"type":"done","session_id","message_id"}`, `{"type":"error","detail"}`.
- Consumes: `validate_model`/`DEFAULT_MODEL` (Task 1), `_get_session_or_404`/`AiChatMessage` (Task 2).

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ai_chat_stream.py`:

```python
"""#117 completion — SSE chat: event sequence, persistence, rate limit, pre-stream errors.

litellm.acompletion is mocked; no network calls."""
import json

from fastapi.testclient import TestClient


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


def _new_session(client, auth) -> int:
    return client.post("/api/ai/sessions", headers=auth, json={}).json()["id"]


def _setup(client, email, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, email)
    _install_ai(client, auth)
    client.patch("/api/settings", headers=auth, json={"ai_api_key_openai": "sk-test"})
    return auth, _new_session(client, auth)


# ── litellm stream fakes (OpenAI chunk shape) ────────────────────────────────

class _Fn:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments

class _ToolCallDelta:
    def __init__(self, index, id=None, name=None, arguments=None):
        self.index = index
        self.id = id
        self.function = _Fn(name, arguments)

class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

class _Choice:
    def __init__(self, content=None, tool_calls=None, finish_reason=None):
        self.delta = _Delta(content, tool_calls)
        self.finish_reason = finish_reason

class _Chunk:
    def __init__(self, **kw):
        self.choices = [_Choice(**kw)]


def _stream_from(chunks):
    async def gen():
        for c in chunks:
            yield c
    return gen()


def _events(resp_text_lines):
    out = []
    for line in resp_text_lines:
        if line.startswith("data: "):
            out.append(json.loads(line[len("data: "):]))
    return out


def test_plain_text_stream_and_persistence(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st1@t.com", monkeypatch)

    calls = []
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _stream_from([
            _Chunk(content="Hel"),
            _Chunk(content="lo!"),
            _Chunk(finish_reason="stop"),
        ])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "hi"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        events = _events(list(r.iter_lines()))

    types = [e["type"] for e in events]
    assert types == ["token", "token", "done"]
    assert "".join(e["text"] for e in events if e["type"] == "token") == "Hello!"
    assert calls[0]["model"] == "openai/gpt-4o-mini"   # tenant default = first configured
    assert calls[0]["api_key"] == "sk-test"

    msgs = client.get(f"/api/ai/sessions/{sid}/messages", headers=auth).json()
    assert [(m["role"], m["content"]) for m in msgs] == [("user", "hi"), ("assistant", "Hello!")]
    assert msgs[1]["model"] == "openai/gpt-4o-mini"
    # session title auto-set from first message
    assert client.get("/api/ai/sessions", headers=auth).json()[0]["title"] == "hi"


def test_tool_call_round_trip_events(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st2@t.com", monkeypatch)

    responses = [
        _stream_from([
            _Chunk(tool_calls=[_ToolCallDelta(0, id="call_1", name="get_ar_aging", arguments="")]),
            _Chunk(tool_calls=[_ToolCallDelta(0, arguments="{}")]),
            _Chunk(finish_reason="tool_calls"),
        ]),
        _stream_from([
            _Chunk(content="You are owed money."),
            _Chunk(finish_reason="stop"),
        ]),
    ]
    captured = []
    async def fake_acompletion(**kwargs):
        captured.append(kwargs["messages"])
        return responses.pop(0)
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    with client.stream("POST", "/api/ai/chat", headers=auth,
                       json={"session_id": sid, "message": "who owes me?"}) as r:
        events = _events(list(r.iter_lines()))

    types = [e["type"] for e in events]
    assert types == ["tool_start", "tool_end", "token", "done"]
    assert "receivable" in events[0]["label"].lower() or "owe" in events[0]["label"].lower()
    # second call carried the tool result back in OpenAI format
    second_msgs = captured[1]
    assert second_msgs[-1]["role"] == "tool"
    assert second_msgs[-1]["tool_call_id"] == "call_1"
    assert second_msgs[-2]["role"] == "assistant"
    assert second_msgs[-2]["tool_calls"][0]["function"]["name"] == "get_ar_aging"


def test_pre_stream_errors(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st3@t.com", monkeypatch)

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": sid, "message": "hi", "model": "openai/not-real"})
    assert r.status_code == 400

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": sid, "message": "hi", "model": "gemini/gemini-2.5-flash"})
    assert r.status_code == 400          # provider not configured

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": 999999, "message": "hi"})
    assert r.status_code == 404

    r = client.post("/api/ai/chat", headers=auth,
                    json={"session_id": sid, "message": "x" * 4001})
    assert r.status_code == 400


def test_no_providers_returns_503(client: TestClient, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    auth = _signup(client, "st4@t.com")
    _install_ai(client, auth)
    sid = _new_session(client, auth)
    r = client.post("/api/ai/chat", headers=auth, json={"session_id": sid, "message": "hi"})
    assert r.status_code == 503


def test_rate_limit_429(client: TestClient, monkeypatch):
    auth, sid = _setup(client, "st5@t.com", monkeypatch)
    client.patch("/api/settings", headers=auth, json={"ai_rate_limit_per_hour": "2"})

    async def fake_acompletion(**kwargs):
        return _stream_from([_Chunk(content="ok"), _Chunk(finish_reason="stop")])
    monkeypatch.setattr("routers.ai_chat.litellm.acompletion", fake_acompletion)

    for _ in range(2):
        with client.stream("POST", "/api/ai/chat", headers=auth,
                           json={"session_id": sid, "message": "hi"}) as r:
            assert r.status_code == 200
            list(r.iter_lines())
    r = client.post("/api/ai/chat", headers=auth, json={"session_id": sid, "message": "hi"})
    assert r.status_code == 429
```

- [ ] **Step 2: Run to verify failure**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_chat_stream.py -q`
Expected: FAIL — `AttributeError: routers.ai_chat has no attribute 'litellm'` (or 422s on the new body shape).

- [ ] **Step 3: Rewrite the chat endpoint**

In `backend/routers/ai_chat.py`:

(a) Imports: add `import time`, `import litellm`, `from collections import defaultdict, deque`, `from fastapi.responses import StreamingResponse`, `from services.ai_providers import DEFAULT_MODEL, configured_providers, validate_model` (merge with Task 3's import line). Remove `import anthropic` and the `anthropic.*` exception handlers (the SDK stays installed as LiteLLM's transport; this file no longer touches it directly).

(b) Replace `ChatRequest` and add the tool conversion + labels + limiter:

```python
class ChatRequest(BaseModel):
    session_id: int
    message: str
    model: str | None = None


# One-time conversion: Anthropic tool format → OpenAI function format.
OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["input_schema"],
        },
    }
    for t in TOOLS
]

TOOL_LABELS = {
    "get_dashboard_summary": "Checking your dashboard…",
    "get_income_statement": "Checking your P&L…",
    "get_ar_aging": "Checking who owes you (receivables)…",
    "get_ap_aging": "Checking what you owe (payables)…",
    "get_trial_balance": "Checking your trial balance…",
    "get_cash_flow": "Checking your cash flow…",
    "get_top_customers": "Checking your top customers…",
}

# Sliding-hour rate limiter. Per-process by design (single-process deploy);
# resets on restart — acceptable, documented in the spec.
_RATE: dict[tuple[int, int], deque] = defaultdict(deque)
DEFAULT_RATE_LIMIT = 20


def _check_rate_limit(session, user) -> None:
    row = session.exec(
        select(Settings).where(
            Settings.tenant_id == user.tenant_id,
            Settings.key == "ai_rate_limit_per_hour",
        )
    ).first()
    try:
        limit = int(row.value) if row and row.value else DEFAULT_RATE_LIMIT
    except ValueError:
        limit = DEFAULT_RATE_LIMIT
    bucket = _RATE[(user.tenant_id, user.id)]
    now = time.monotonic()
    while bucket and now - bucket[0] > 3600:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"AI request limit reached ({limit}/hour). Try again in a few minutes.",
        )
    bucket.append(now)
```

(c) Replace the `/chat` endpoint entirely:

```python
def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat")
async def ai_chat(body: ChatRequest, session: SessionDep, user: CurrentUserDep):
    # ── Pre-stream validation: plain HTTP errors ────────────────────────
    _require_ai_module(session, user)
    chat_session = _get_session_or_404(session, user, body.session_id)

    if len(body.message) > MAX_MESSAGE_CHARS:
        raise HTTPException(400, f"Message too long (max {MAX_MESSAGE_CHARS} characters).")

    providers = configured_providers(session, user.tenant_id)
    if not providers:
        raise HTTPException(
            503,
            "AI assistant is not configured. Add a provider API key in Settings → AI "
            "(or set ANTHROPIC_API_KEY in the backend environment).",
        )
    model = body.model or providers[0]["default"] or DEFAULT_MODEL
    try:
        litellm_model, api_key = validate_model(session, user.tenant_id, model)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    _check_rate_limit(session, user)

    # Server-side history (last MAX_HISTORY turns), then persist the new user msg.
    history_rows = session.exec(
        select(AiChatMessage).where(AiChatMessage.session_id == chat_session.id)
        .order_by(AiChatMessage.id.desc()).limit(MAX_HISTORY)
    ).all()
    messages: list[dict] = [{"role": "system", "content": _build_system_prompt(_get_company_name(session, user))}]
    messages += [
        {"role": m.role, "content": m.content[:MAX_MESSAGE_CHARS]}
        for m in reversed(history_rows)
    ]
    messages.append({"role": "user", "content": body.message})

    user_msg = AiChatMessage(session_id=chat_session.id, role="user", content=body.message)
    session.add(user_msg)
    if chat_session.title == "New chat":
        chat_session.title = body.message.strip()[:60]
    chat_session.updated_at = datetime.utcnow()
    session.add(chat_session)
    session.commit()

    async def stream():
        assistant_text_parts: list[str] = []
        try:
            for _ in range(MAX_STEPS):
                response = await litellm.acompletion(
                    model=litellm_model,
                    api_key=api_key,
                    max_tokens=2048,
                    messages=messages,
                    tools=OPENAI_TOOLS,
                    stream=True,
                )
                # Accumulate this round's text + tool calls from the chunk stream.
                round_text_parts: list[str] = []
                tool_calls: dict[int, dict] = {}
                finish_reason = None
                async for chunk in response:
                    choice = chunk.choices[0]
                    delta = choice.delta
                    if getattr(delta, "content", None):
                        round_text_parts.append(delta.content)
                        yield _sse({"type": "token", "text": delta.content})
                    for tc in getattr(delta, "tool_calls", None) or []:
                        slot = tool_calls.setdefault(
                            tc.index, {"id": None, "name": None, "arguments": ""}
                        )
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function.name:
                            slot["name"] = tc.function.name
                        if tc.function.arguments:
                            slot["arguments"] += tc.function.arguments
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason
                assistant_text_parts += round_text_parts

                if finish_reason != "tool_calls" or not tool_calls:
                    break  # done — plain answer (or provider stopped)

                # Echo the assistant tool-call turn, execute, append results.
                ordered = [tool_calls[i] for i in sorted(tool_calls)]
                messages.append({
                    "role": "assistant",
                    "content": "".join(round_text_parts) or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"] or "{}"},
                        }
                        for c in ordered
                    ],
                })
                for c in ordered:
                    yield _sse({
                        "type": "tool_start",
                        "label": TOOL_LABELS.get(c["name"], f"Running {c['name']}…"),
                    })
                    try:
                        tool_input = json.loads(c["arguments"] or "{}")
                    except json.JSONDecodeError:
                        tool_input = {}
                    result_text, _is_error = _execute_tool(c["name"], tool_input, session, user)
                    yield _sse({"type": "tool_end"})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "content": result_text,
                    })

            reply = "".join(assistant_text_parts) or \
                "I wasn't able to complete the analysis. Please try a more specific question."
            assistant_msg = AiChatMessage(
                session_id=chat_session.id, role="assistant",
                content=reply, model=litellm_model,
            )
            chat_session.updated_at = datetime.utcnow()
            session.add(assistant_msg)
            session.add(chat_session)
            session.commit()
            yield _sse({
                "type": "done",
                "session_id": chat_session.id,
                "message_id": assistant_msg.id,
            })
        except Exception as exc:  # mid-stream: headers already sent → error event
            yield _sse({
                "type": "error",
                "detail": f"The AI service failed mid-response: {type(exc).__name__}. Please try again.",
            })

    return StreamingResponse(stream(), media_type="text/event-stream")
```

Implementation notes for this step (read before coding):
- `MODEL = "claude-sonnet-4-6"` module constant becomes dead — delete it (the registry owns model ids now).
- The old sync endpoint's Anthropic-typed exception mapping is deleted with it; pre-stream provider errors can no longer occur before streaming (the first provider call happens inside `stream()`), which is why mid-stream failures are error events.
- `session` (DB) usage inside the generator is safe under TestClient and uvicorn's default behavior for this app (single request scope); do not add threading.

- [ ] **Step 4: Run tests**

Run: `PYTHONPATH=. uv run pytest tests/test_ai_chat_stream.py tests/test_ai_sessions.py tests/test_ai_providers.py -q`
Expected: all pass (6 + 3 + 8 = 17).

- [ ] **Step 5: Full-suite regression**

Run: `PYTHONPATH=. uv run pytest -q`
Expected: only the documented pre-existing failures.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/ai_chat.py backend/tests/test_ai_chat_stream.py
git commit -m "feat(ai): SSE chat endpoint — LiteLLM agent loop, per-tool events, rate limit (#117)"
```

---

### Task 5: Frontend — SSE client + shared ChatCore + FAB rework

**Files:**
- Create: `frontend/src/lib/aiStream.ts` (SSE consumption helper)
- Create: `frontend/src/components/ai/ChatCore.tsx`
- Modify: `frontend/src/components/AIChat.tsx` (becomes a thin panel shell around ChatCore)

**Interfaces:**
- Produces: `streamChat(body: {session_id, message, model?}, handlers: {onToken, onToolStart, onToolEnd, onDone, onError}): Promise<void>` in aiStream.ts; `<ChatCore sessionId={number} models={ModelsPayload} />` rendering thread + input + model dropdown + quick prompts.
- Consumes: `POST /api/ai/chat` SSE protocol (Task 4), `GET /api/ai/models`, `GET /api/ai/sessions`, `POST /api/ai/sessions`, `GET /api/ai/sessions/{id}/messages` (Tasks 2-3).

- [ ] **Step 1: `aiStream.ts`**

`apiFetch` JSON-parses responses, so SSE needs raw `fetch`. Pattern (complete file):

```ts
import { apiBase } from "@/lib/api"
import { getAuthHeader } from "@/lib/auth"

export interface StreamHandlers {
  onToken: (text: string) => void
  onToolStart: (label: string) => void
  onToolEnd: () => void
  onDone: (sessionId: number, messageId: number) => void
  onError: (detail: string) => void
}

export async function streamChat(
  body: { session_id: number; message: string; model?: string | null },
  h: StreamHandlers,
): Promise<void> {
  const res = await fetch(`${apiBase}/api/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    h.onError((data as { detail?: string }).detail || `HTTP ${res.status}`)
    return
  }
  const reader = res.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const frames = buffer.split("\n\n")
    buffer = frames.pop() ?? ""
    for (const frame of frames) {
      const line = frame.trim()
      if (!line.startsWith("data: ")) continue
      const ev = JSON.parse(line.slice(6)) as Record<string, unknown>
      switch (ev.type) {
        case "token": h.onToken(ev.text as string); break
        case "tool_start": h.onToolStart(ev.label as string); break
        case "tool_end": h.onToolEnd(); break
        case "done": h.onDone(ev.session_id as number, ev.message_id as number); break
        case "error": h.onError(ev.detail as string); break
      }
    }
  }
}
```

Verify `getAuthHeader` is exported from `@/lib/auth` and `apiBase` from `@/lib/api` (both confirmed present at plan time) — adjust imports only if reality differs.

- [ ] **Step 2: `ChatCore.tsx`**

Extract from the current `AIChat.tsx` (read it first — reuse its message bubbles, quick prompts, scroll behavior, styling verbatim where possible). ChatCore owns: message list state (loaded from `GET /api/ai/sessions/{id}/messages` on mount/session change), the streaming send path (append user msg, run `streamChat`, append tokens to a growing assistant bubble, show tool-indicator rows with a spinner while between tool_start/tool_end), an inline error banner for `onError`, the model dropdown (options from the `models` prop; controlled state defaulting to `models.default_model`), and the QUICK_PROMPTS row (shown only when the thread is empty). Props: `sessionId: number`, `models: {providers: {provider,label,models:string[]}[], default_model: string|null}`, optional `className`. Dates need no formatting here (no timestamps rendered in the thread).

- [ ] **Step 3: Rework `AIChat.tsx`**

Keep: createPortal panel chrome, open/close, Sparkles header. Replace the inline thread/input with `<ChatCore/>`. On open: fetch `GET /api/ai/models` and `GET /api/ai/sessions`; use the most recent session or `POST /api/ai/sessions` if none; render ChatCore with that id. Add a "New chat" button (creates a session, swaps ChatCore's `sessionId`). History now survives close/reopen and page refresh — remove the old `setMessages([])` reset-on-close.

- [ ] **Step 4: Verify**

From worktree `frontend/`: `npx tsc --noEmit && npx eslint src/lib/aiStream.ts src/components/ai src/components/AIChat.tsx`
Expected: clean for these files.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/aiStream.ts frontend/src/components/ai frontend/src/components/AIChat.tsx
git commit -m "feat(ai-ui): SSE streaming ChatCore + persistent-session FAB panel (#117)"
```

---

### Task 6: Frontend — /agent full-screen page + nav

**Files:**
- Create: `frontend/src/app/(dashboard)/agent/page.tsx`
- Modify: `frontend/src/lib/nav.ts` (NAV System section + SUB_NAV system array + SECTION_PREFIXES.system gains `"/agent"`)
- Modify: `frontend/src/lib/navTitles.ts` (`"/agent": "AI Assistant"`)

**Interfaces:**
- Consumes: ChatCore + session/models endpoints (Tasks 2-3, 5).

- [ ] **Step 1: Page**

`app/(dashboard)/agent/page.tsx` ("use client"): two-column layout — left rail (~260px): session list from `GET /api/ai/sessions` (newest first; click selects; inline rename via pencil → `PATCH`; delete via trash → `DELETE` with `window.confirm`; "New chat" button at top → `POST`); right: `<ChatCore sessionId={selected} models={models}/>` full-height. Guard: if `GET /api/ai/models` 403s (module uninstalled), render a friendly "Install the AI Assistant from System → Apps" empty state instead of the layout. Print stylesheet: wrap the left rail and input areas in `print:hidden` so the browser's print-to-PDF captures just the conversation thread ("export conversation" per spec).

- [ ] **Step 2: Nav wiring**

nav.ts NAV (System section, after "User Guide"): `{ label: "AI Assistant", href: "/agent", icon: Sparkles, section: "System", forModule: "ai_assistant" }` (import `Sparkles` if missing). Mirror in `SUB_NAV.system`. Append `"/agent"` to `SECTION_PREFIXES.system`. navTitles.ts: add `"/agent": "AI Assistant"`.

- [ ] **Step 3: Verify**

`npx tsc --noEmit && npx eslint src/lib/nav.ts src/lib/navTitles.ts "src/app/(dashboard)/agent"` — clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/nav.ts frontend/src/lib/navTitles.ts "frontend/src/app/(dashboard)/agent"
git commit -m "feat(ai-ui): /agent full-screen page with session sidebar (#117)"
```

---

### Task 7: Frontend — Settings → AI card

**Files:**
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx`

**Interfaces:**
- Consumes: `GET /api/ai/key-status`, `PATCH /api/settings` (Task 3 keys), provider registry shape.

- [ ] **Step 1: Card**

New card on the **Advanced** tab (read the page's existing card pattern first), rendered only when `useModules().installedModules.has("ai_assistant")` and user role is admin/owner (match how existing admin-gated cards check role). Contents: three provider rows (Anthropic/OpenAI/Gemini) each with: masked status from `GET /api/ai/key-status` (`••••x4Kb` or "Not set"), a password-type input to paste a new key, and a Clear button (PATCHes empty string); a default-model `<select>` (options = the registry's 6 `provider/model` strings, but disable options whose provider shows "Not set"); a rate-limit number input (`ai_rate_limit_per_hour`, placeholder 20). Save button PATCHes only touched fields via `/api/settings`, then refetches key-status. Never render a full key.

- [ ] **Step 2: Verify**

`npx tsc --noEmit && npx eslint "src/app/(dashboard)/settings/page.tsx"` — clean.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(ai-ui): Settings AI card — provider keys, default model, rate limit (#117)"
```

---

### Task 8: Docs delta + full verification

**Files:**
- Modify: `CLAUDE.md` (routers table `ai_chat.py` row; Frontend AI Chat paragraph; env-vars section)
- Verify: full backend suite + frontend build + live e2e drive

- [ ] **Step 1: CLAUDE.md delta**
  1. Rewrite the `routers/ai_chat.py` row: multi-provider via LiteLLM (anthropic/openai/gemini, per-tenant keys in Settings KV with env fallback for Anthropic only), async SSE `POST /api/ai/chat` (`token/tool_start/tool_end/done/error` events), server-side sessions (`AiChatSession`/`AiChatMessage`, per-user private), sliding-hour rate limit (`ai_rate_limit_per_hour`, default 20), `GET /models` + `GET /key-status` (admin, masked).
  2. Update the Frontend AI Chat paragraph: ChatCore shared by FAB + `/agent` page (session sidebar), Settings → AI card, `aiStream.ts` raw-fetch SSE reader.
  3. Env vars: note `ANTHROPIC_API_KEY` is now the anthropic-provider fallback; per-tenant keys via Settings → AI.
  4. `services/` table: add `ai_providers.py` row.

- [ ] **Step 2: Full backend suite** — `PYTHONPATH=. uv run pytest -q` → only documented pre-existing failures.

- [ ] **Step 3: Frontend build** — `npm run build` → clean; `/agent` route present.

- [ ] **Step 4: e2e drive** (controller runs this per the verify skill): with NO keys configured → FAB hidden module-off tenant / 503 path on module-on tenant; configure a fake OpenAI key via settings API → dropdown appears with 2 OpenAI models, `/agent` renders session list; send a message → pre-stream 401-from-provider arrives as mid-stream error event rendered in the banner (fake key can't produce tokens — the graceful-failure path IS the test); refresh → session + user message persisted; rate-limit field saves; key-status shows masked tail; `GET /api/settings` response contains no `ai_api_key_` values (assert in the drive script).

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md delta for multi-provider AI chat (#117)"
```
