# AI Chat Level 1 Completion — Multi-Provider, Streaming, Sessions (#117)

**Date:** 2026-07-11
**Status:** Approved design
**Prior art:** Level 1 core merged 2026-07-03 (PR #135 + hardening `eca27cf`): sync `POST /api/ai/chat`, Anthropic-SDK agent loop (`MAX_STEPS=6`, pinned `claude-sonnet-4-6`), 7 read-only tools calling existing report functions, module gate (`ai_assistant`), 4000-char/20-turn cost caps, typed error mapping. Docs PR #136.

## Scope (user-selected, 2026-07-11)

Closes the remaining #117 acceptance criteria plus one new requirement:

1. **SSE streaming** — token-by-token responses, per-tool progress indicators.
2. **Persisted history** — server-side chat sessions surviving refresh.
3. **Rate limiting** — 20 agent calls/hour per user, tenant-overridable.
4. **`/agent` full-screen page** — session list + chat.
5. **NEW: multi-provider model selection** — Anthropic / OpenAI / Gemini,
   admin-configured, per-conversation dropdown.

## Key decisions (locked)

1. **Provider abstraction = LiteLLM** (`litellm` PyPI package). The agent
   loop is rewritten once around `litellm.acompletion(model=...,
   tools=[...], stream=True)` using the OpenAI message/tool format LiteLLM
   normalizes everything to. The 7 existing tool definitions convert from
   Anthropic format to OpenAI function format once, at module import.
   Rejected alternatives: hand-rolled per-SDK adapters (3× maintenance,
   normalization is exactly the hard part), OpenAI-compat endpoints
   (Anthropic's is beta with tool-use gaps — fragile for an agent loop).

2. **Model choice = tenant setting + chat dropdown.** Admin configures
   provider keys in Settings → AI; the chat UI's model dropdown lists only
   models whose provider has a key configured. `ai_default_model` setting
   picks the preselected one.

3. **Keys = per-tenant in the existing Settings KV**, one key per
   provider: `ai_api_key_anthropic`, `ai_api_key_openai`,
   `ai_api_key_gemini`. The settings API returns only a masked tail
   (last 4 chars, e.g. `••••x4Kb`) — the full key is never returned by
   any GET. Writing a new value replaces; writing empty string clears.
   The existing `ANTHROPIC_API_KEY` env var remains as a fallback for the
   Anthropic provider only (dev/demo works out of the box); no other env
   keys are consulted.

4. **The endpoint goes `async def`** — SSE + LiteLLM's async streaming
   force this, resolving the deferred sync-endpoint follow-up from the
   original L1 review (recorded in BLUEPRINT.md's Sprint 22 table).

5. **Default model stays `claude-sonnet-4-6`-class.** Upgrading the
   default to `claude-sonnet-5` remains out of scope (adaptive-thinking
   defaults eat into max_tokens — needs its own deliberate pass).

## Provider registry

`services/ai_providers.py`:

```python
PROVIDERS = {
    "anthropic": {
        "label": "Anthropic (Claude)",
        "settings_key": "ai_api_key_anthropic",
        "env_fallback": "ANTHROPIC_API_KEY",
        "models": ["claude-sonnet-4-6", "claude-haiku-4-5"],   # litellm: "anthropic/<id>"
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "settings_key": "ai_api_key_openai",
        "env_fallback": None,
        "models": ["gpt-4o-mini", "gpt-4o"],                    # litellm: "openai/<id>"
    },
    "gemini": {
        "label": "Google (Gemini)",
        "settings_key": "ai_api_key_gemini",
        "env_fallback": None,
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],       # litellm: "gemini/<id>"
    },
}
```

Exact model ids are pinned at plan time against LiteLLM's current
provider docs; the registry is the single source both for the settings
card and the chat dropdown (`GET /api/ai/models` returns only providers
with a resolvable key, each with its models + which one is the tenant
default).

`resolve_api_key(session, tenant_id, provider) -> Optional[str]`:
settings value wins; env fallback only for anthropic; None → provider
absent from `/api/ai/models` and 400 if explicitly requested.

## Sessions (persisted history)

New tables (migration 0033, `has_table` guard):

### `AiChatSession`
| Field | Notes |
|---|---|
| `id`, `tenant_id` (FK, indexed), `user_id` (FK, indexed) | sessions are per-user private — every query filters BOTH tenant_id and user_id |
| `title` | auto-set from the first user message (truncated ~60 chars), renameable |
| `created_at`, `updated_at` | updated_at bumps on every message |

### `AiChatMessage`
| Field | Notes |
|---|---|
| `id`, `session_id` (FK, CASCADE, indexed) | |
| `role` | `user` \| `assistant` |
| `content` | full text |
| `model` | litellm model string used (assistant rows) |
| `created_at` | |

Endpoints (`routers/ai_chat.py`, all module-gated + `CurrentUserDep`,
all filtered tenant_id AND user_id):
- `GET /api/ai/sessions` — list (id, title, updated_at), newest first
- `POST /api/ai/sessions` — create empty session
- `PATCH /api/ai/sessions/{id}` — rename
- `DELETE /api/ai/sessions/{id}` — delete (cascades messages)
- `GET /api/ai/sessions/{id}/messages` — full transcript
- `GET /api/ai/models` — provider/model dropdown data (per decision 2)

`POST /api/ai/chat` body becomes `{session_id, message, model?}` — the
server loads the last `MAX_HISTORY` (20) turns from the session itself
(client no longer sends history), appends the user message and, at
stream end, the assistant message.

## SSE streaming

`POST /api/ai/chat` → `StreamingResponse`, `media_type="text/event-stream"`.
Event protocol (each `data:` line is JSON with a `type` field):
- `{"type":"token","text":...}` — assistant text delta
- `{"type":"tool_start","label":...}` — friendly label per tool (e.g.
  `get_profit_and_loss` → "Checking your P&L…"; label map lives beside
  the tool definitions)
- `{"type":"tool_end"}`
- `{"type":"done","session_id":...,"message_id":...}`
- `{"type":"error","detail":...}` — terminal; also used for mid-stream
  provider failures after headers are sent (HTTP status can no longer
  change, so errors after start are events)

Pre-stream failures (module gate, no key, rate limit, message too long,
foreign session_id) remain plain HTTP errors (403/400/429/404) since
headers aren't sent yet.

Agent loop: unchanged semantics (MAX_STEPS=6, tools executed
server-side, `is_error` tool results) — re-expressed over LiteLLM's
OpenAI-format streaming chunks (`delta.content`, `delta.tool_calls`,
`finish_reason`).

## Rate limiting

In-memory sliding-hour deque per `(tenant_id, user_id)` in
`routers/ai_chat.py` (module-level dict; per-process, resets on restart
— acceptable at current scale, matches the app's single-process deploy).
Default 20/hour; Settings key `ai_rate_limit_per_hour` overrides
per-tenant. Exceeded → 429 `{"detail": "AI request limit reached
(N/hour). Try again in a few minutes."}` before any provider call.

## Frontend

**Shared core:** extract the message-thread + streaming logic from
`AIChat.tsx` into `components/ai/ChatCore.tsx` (message list, SSE
consumption via `fetch` + `ReadableStream` reader — `apiFetch` can't do
SSE — token append, tool-indicator rows, error banner). The FAB panel
and the `/agent` page both render it.

**FAB panel (`AIChat.tsx`):** on open, loads the most recent session
(creates one if none) — history survives refresh. Adds the model
dropdown (from `/api/ai/models`, default preselected) and a "new chat"
button. Quick prompts stay.

**`/agent` page (`app/(dashboard)/agent/page.tsx`):** session list left
(select/rename/delete, newest first), `ChatCore` right, model dropdown
in the header. Print stylesheet so the browser's print-to-PDF covers
the "export conversation" wish (no server-side PDF — YAGNI). Nav:
System section, `forModule: "ai_assistant"`, BOTH `NAV` and `SUB_NAV`
registries (standing requirement).

**Settings → AI card (settings page, admin/owner only, visible only
when `ai_assistant` installed):** three masked key inputs (show
`••••x4Kb` tail when set; typing replaces; clear button), default-model
select (options from the registry filtered to configured providers),
rate-limit number field. Saves through the existing `/api/settings`
PATCH; the masked display comes from a small
`GET /api/ai/key-status` endpoint returning `{provider: masked_tail
| null}` (the settings GET must NOT return the raw keys — add these
keys to a server-side redaction list in `routers/settings.py`).

## Testing

Backend (`tests/test_ai_chat_v2.py`, mocking `litellm.acompletion`):
- `/api/ai/models`: no keys → anthropic only when env fallback set,
  empty otherwise; tenant key present → provider listed; masked
  key-status endpoint never returns the full key (assert tail-only)
- Settings GET redaction: raw `ai_api_key_*` values absent from
  `/api/settings` responses
- Session CRUD: tenant AND user isolation (user B of same tenant cannot
  read user A's session — 404), cascade delete, title auto-set
- Chat flow with mocked stream: SSE event sequence
  token→tool_start→tool_end→token→done; both messages persisted with
  correct roles + model string
- Rate limit: 21st call within the hour → 429; settings override
  respected
- Pre-stream errors: unknown model → 400, foreign session → 404,
  module uninstalled → 403

Frontend: tsc/eslint on all new/changed files; e2e drive (login,
configure a fake key via settings API, open FAB — dropdown appears,
`/agent` page renders session list, refresh mid-conversation preserves
history; real streaming requires a live key, so e2e asserts the
graceful no-key/error paths).

## Out of scope

- Upgrading the default model to `claude-sonnet-5` (adaptive-thinking
  caveat — separate deliberate pass)
- Server-side PDF export (print stylesheet covers it)
- Haiku auto-fallback routing for simple queries (issue wished for it;
  cut per YAGNI — the model dropdown gives manual control)
- Write-capable tools / OCR (that's Level 2, #122)
- Cross-process rate limiting (Redis) — single-process deploy today
