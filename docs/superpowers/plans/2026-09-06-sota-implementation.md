# Easy-Books — state-of-the-art implementation plan

**Date:** 2026-09-06  
**Status:** Plan only — execute as numbered PRs below. Do not start #122 / #307 / #309.  
**Locked:** one `main`, one Vercel app, one Neon DB. Client = `Tenant` row.  
**Companion:** [production launch](2026-09-06-production-launch.md) (ops secrets) · [#391](https://github.com/bilalpiaic/Easy-Books/issues/391) (weighbridge UI, not this plan’s first PR)

## Goal

Make the **existing** product feel fast and operable for a paying mill/trader:

1. Host can take money, store files, restore a tenant, and turn off demo logins.
2. GitHub matches `main` (no fake “unbuilt” modules).
3. Home + journal + invoice lists stay snappy on a dense GL (SQL pagination/aggregates, batched lines, one session bootstrap).
4. Weighbridge **workspace** (#391) only after (1)–(3), and only if the first mill contract needs a scale desk.

This is **not** more industry packs, React Query rewrite-the-app, or a second database.

---

## Do not build in this programme

- Per-client Vercel/Neon or `client-*` branches
- Partner in-process code (#308)
- Native iOS/Android (#307), SOC 2 pack (#309), extra country packs (#306)
- AI L2 OCR (#122) until Wave 1 ops is green
- Unlimited Studio fields in GL
- Full TanStack Query migration (too wide; bootstrap + timeouts is the first win)
- Cursor/keyset pagination in v1 of the speed pack (offset/`LIMIT` done in SQL is enough)

---

## Programme map (PRs)

| PR | Name | Blocks launch? | Repo work |
|----|------|----------------|-----------|
| **0** | Board hygiene + this plan | No | Docs + GitHub comments/closes |
| **1** | SQL hot paths | No (feel-slow) | Journal, dashboard totals, invoice lines, allocation, store issues |
| **2** | Session bootstrap + `apiFetch` | No (feel-slow) | One GET for me/settings/modules/permissions; timeout/abort |
| **3** | Tenant+date indexes | No (scale) | Alembic 0085 composites |
| **Ops** | Secrets / S3 / PITR / env flags | **Yes** | Vercel + Neon console — no git |
| **4** | Weighbridge workspace | No | Only if mill signed — [#391](https://github.com/bilalpiaic/Easy-Books/issues/391) |

Ship **0 → 1 → 2 → 3**. Run **Ops** in parallel with 1–2. Start **4** only after Ops + PR1.

---

## PR 0 — Board hygiene

**Branch prefix:** `cursor/board-hygiene-*`

### GitHub

| Issue | Action |
|-------|--------|
| #369 | Comment “children #370–#376 shipped”; close or retitle to launch-ops |
| #298 | Close or convert to tracking epic (A/B landed) |
| #303 | Close v1 (leave + expense claims + PK templates on `main`); optional follow-up “statutory rate engine” |
| #390 | Already closed (PR #393) |
| #391 | Keep open — real product gap |
| #306 #307 #309 | Leave open; add “defer until …” comment |

### Docs

- `docs/ROADMAP.md`: #390 **Shipped** PR #393; point “next engineering” at this file.
- This plan is the source of truth for speed work until those PRs merge.

**Done when:** someone opening GitHub does not think POS/practice/Studio/forgot-password are unbuilt.

---

## PR 1 — SQL hot paths (highest ROI)

**Branch:** `cursor/sql-hot-paths-d032`  
**Tests:** mill-shaped fixtures (many JEs / invoices) so “page 2 is O(page)” is actually asserted.

### 1.1 Journal — real SQL pagination

**Today:** `GET /api/reports/journal` does `session.exec(q).all()` then `rows[skip:skip+limit]` (`backend/routers/reports.py`). The UI already sends `skip`/`limit` (`frontend/src/app/(dashboard)/journal/page.tsx`, `PAGE_SIZE = 50`).

**Change:**

- `COUNT(*)` on the same filtered join (or `select(func.count()).select_from(q.subquery())`).
- `q.offset(skip).limit(limit)` **before** `exec`.
- Keep response `{total, items}` unchanged.

**Test:** seed ≥ 60 journal lines; `skip=0&limit=50` returns 50 items and `total >= 60`; second page `skip=50` does not require loading page 1 into the assertion set. Optionally `EXPLAIN` is out of scope for pytest.

### 1.2 Dashboard revenue/expense — SQL aggregate

**Today:** `GET /api/reports/dashboard` hydrates every in-range `(JournalEntry, Account)` and sums in Python (`reports.py` ~141–158).

**Change:** one grouped query, e.g. `SUM(credit-debit)` / `SUM(debit-credit)` filtered by `Account.type` in `('Revenue','Expense')` and the same date/tenant predicates. Keep `ar_outstanding` / `ap_outstanding` (already SQL).

**Contract:** JSON `summary` keys stay the same so `dashboard/page.tsx` does not change.

**Test:** two JEs (revenue credit, expense debit) → totals match the old Python identity; empty period → zeros.

### 1.3 Invoice list — batch lines

**Today:** after `offset/limit`, each invoice runs `select(InvoiceLine).where(invoice_id == inv.id)` (`invoices.py` ~247–254).

**Change:**

```python
ids = [inv.id for inv in items]
lines = session.exec(select(InvoiceLine).where(InvoiceLine.invoice_id.in_(ids))).all()
by_inv: dict[int, list] = defaultdict(list)
for ln in lines:
    by_inv[ln.invoice_id].append(ln.model_dump())
```

Response shape unchanged (`{total, items}` with `lines` on each item).

**Test:** two invoices × N lines; list returns both line sets; query count must not scale with invoice count (optional: SQLAlchemy `echo` / event counter in the test).

### 1.4 Open-for-allocation — one allocation SUM

**Today:** unbounded invoice list + per-invoice `SUM(PaymentAllocation)` (`invoices.py` ~174–213).

**Change:**

- Filter open statuses in SQL (keep).
- Left-join / grouped `SUM(PaymentAllocation.amount)` for those invoice ids in **one** query.
- `HAVING` / Python filter `balance_due > 0`.
- Add `skip`/`limit` (default 100, max 500) so the allocation panel cannot dump a year of AR. Frontend: pass `customer_id` (already) + `limit`.

**Test:** paid vs partial vs open; only positive `balance_due` rows; two invoices one query for allocations.

### 1.5 Store issues list — `{total, items}`

**Today:** `list_store_issues` `.all()` then serialize (`store_issues.py` ~78–95). `_serialize` may N+1 lines — batch the same way as invoices if it loads lines per row.

**Change:** `skip`/`limit` (default 50), `{total, items}`. Update `frontend` store-issues list to `Pagination` if it still client-filters a bare array.

**Test:** 55 issues → page 1 has 50, `total=55`.

### PR 1 out of scope

Ledger running-balance rewrite, trial-balance trees, `dashboard_ops` parallel fan-out, React Query.

**PR 1 done when:** journal page 2 on a 200-row tenant is a `LIMIT` query; dashboard KPI does not load every JE; invoice list is 1 + 1 queries for headers and lines.

---

## PR 2 — Session bootstrap + fetch hygiene

**Branch:** `cursor/session-bootstrap-d032`

### 2.1 `GET /api/auth/bootstrap` (or `/api/session`)

Single authenticated GET returning:

```json
{
  "me": { },
  "settings": { },
  "modules": { "installed": [] },
  "permissions": { }
}
```

Reuse the existing serializers from `GET /api/auth/me`, `GET /api/settings`, `GET /api/modules`, `GET /api/permissions/me`. Do **not** invent a new permission engine.

Mount on `auth.router` (already cookie/JWT). CSRF: GET only.

**Test:** signup → bootstrap keys present; 401 without token; `installed` matches `/api/modules`.

### 2.2 Frontend: one load, fill existing contexts

**Files:**

- `frontend/src/lib/api.ts` — `AbortSignal.timeout(30_000)` (or `AbortController` + 30s); document that SSE (`aiStream.ts`) stays on raw `fetch`.
- New `frontend/src/context/SessionBootstrap.tsx` **or** extend `SettingsProvider` to call bootstrap once and pass slices into `ModuleProvider` / `PermissionProvider` via props/context.
- `frontend/src/hooks/useHomeDashboard.ts` — read `me.tenant.business_model` from bootstrap context; **delete** the extra `GET /api/auth/me`.
- `useDashboardLayout` — same; do not fetch `me` again if bootstrap already has it.

Keep provider **APIs** (`useSettings()`, `useModules()`, `usePermissions()`) so pages do not churn.

**Test (Playwright):** login as `demo.simple` → dashboard; network: at most **one** `/api/auth/bootstrap` (or the four GETs replaced). Existing `e2e/auth.spec.ts` still passes.

### 2.3 Optional follow-up (same PR only if small)

Next.js rewrite `/api/:path*` → `NEXT_PUBLIC_API_URL` so the browser hits same origin and **drops OPTIONS**. If this fights Vercel split frontend/backend projects, **defer** — do not block PR 2. Document in the PR: two Vercel apps ⇒ keep CORS; installer/Electron can still use rewrite in `next.config.ts` when `VERCEL` is unset.

**PR 2 done when:** cold dashboard does not fire 4–6 duplicate `me`/settings/modules/permissions GETs; hung API fails in 30s not forever.

---

## PR 3 — Indexes (Alembic `0085_hot_path_indexes`)

SQLite cannot `ADD CONSTRAINT`; follow 0016/0017: create indexes if missing; no FK add.

| Index | Why |
|-------|-----|
| `(tenant_id, date)` on `transaction` | Journal / dashboard date window |
| `(tenant_id, transaction_id)` or `transaction_id` on `journalentry` | Join journal lines |
| `(tenant_id, issue_date)` on `invoice` | AR lists / allocation |
| `(invoice_id)` on `invoiceline` if not already PK-adjacent | Batch line fetch |
| `(invoice_id)` on `paymentallocation` | Allocation SUM |

Guard with `inspect.get_indexes`. Postgres CI job already exists — run it.

**Test:** migration upgrade on SQLite + Postgres job; existing invoice/journal tests still pass.

**PR 3 done when:** `alembic upgrade head` is idempotent on a DB that already `create_all()`’d.

---

## Ops (parallel, not a git PR)

Do this on **production Vercel + Neon** while PRs 1–2 merge. Code already reads these vars.

| # | Action | Verify |
|---|--------|--------|
| 1 | Stripe **live** `STRIPE_SECRET_KEY` + `STRIPE_PRICE_*` + `STRIPE_WEBHOOK_SECRET` | One test charge; one failed card → tenant suspend |
| 2 | Webhook URL `https://<api>/api/stripe/webhook` | Dashboard delivery 2xx |
| 3 | `STORAGE_BACKEND=s3` + bucket | Upload logo; survives deploy |
| 4 | Neon PITR **on** | Restore drill to a scratch branch **before** live invoices |
| 5 | `JWT_SECRET_KEY` unique; `FRONTEND_ORIGIN` exact |
| 6 | `REQUIRE_OWNER_TOTP=true` `ALLOW_DEMO_LOGIN=false` `SEED_DEMO=false` | Demo login 403; owner write 403 until 2FA |
| 7 | `OPS_ADMIN_EMAILS` includes you | Entitle spinning for mill A only |
| 8 | Uptime on `GET /api/health` |
| 9 | `SMTP_HOST` if forgot-password must deliver | Else request still 200, no mail |

**Ops done when:** tenant A (free) cannot install spinning; you entitle A; B cannot see A’s private catalog; backup restore drill is written down.

---

## PR 4 — Weighbridge workspace (#391) — shipped with this work

Module id `weighbridge` in `MODULE_REGISTRY`; mill models pre-install like spinning.
Tables `wb_ticket`; router `routers/weighbridge.py`; nav section next to Store/Spinning.
Optional write-through to Marketplace `x.gate_pass_no` on linked invoice.
v1 **no** live scale/ANPR and **no** extra GL.

Keep Marketplace listing `partner.easybooks.weighbridge` as the Studio overlay; the module is the workspace users expected.

---

## Later (not this programme)

| Item | When |
|------|------|
| Redis-backed HTTP + AI rate limits | Multi-instance pain is measured |
| `dashboard_ops` parallel `asyncio` | Ops home > 500ms with all mill modules |
| ETag / `Cache-Control` on bootstrap | After PR 2 |
| Ledger running balances in SQL | After journal LIMIT is proven |
| Materialized period balances | Reports.py already notes “P4” |
| TanStack Query | Only if bootstrap is not enough |
| #122 OCR | Bookkeepers photograph bills |

---

## Execution order for the next agent

1. Land **this plan** on `main` (docs PR).  
2. Open **PR 1** immediately (SQL hot paths) — no product debate.  
3. **PR 2** once PR 1 is green (bootstrap is independent but rebase on 1 to avoid `reports.py` conflicts).  
4. **PR 3** indexes after 1 (queries must exist so indexes match).  
5. Operator runs **Ops** checklist; do not wait for PR 3.  
6. File or pick up **#391** only with a named mill.

## Acceptance for the whole programme

A mill demo tenant with a full seed year:

- `/journal` page 2 returns in well under the Playwright 20s expect budget (target: SQL `LIMIT`, not full scan).
- `/dashboard` financial KPIs do not load every JE into Python.
- Invoice list does not issue one SQL per row for lines.
- Login → dashboard: one bootstrap GET (plus dashboard/charts), not a preflight storm of settings/modules/permissions/me.
- Production: demo login off, TOTP required for owners, S3 + PITR + Stripe live documented.
