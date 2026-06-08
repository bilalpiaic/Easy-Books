# Documentation Regeneration — Design

_Date: 2026-06-08 · Branch: `feature/docs-regen` · Base: `main` @ v2.5.0_

## Problem

The project's markdown docs were last touched 2026-06-02/03, **before** the bulk of
recent shipping. They no longer describe current behavior: multi-level Chart of
Accounts + hierarchical reporting, deferred-revenue origination, voucher series,
posted-edit hardening, comparative statements, the hierarchical default CoA, and the
upgraded demo seed — all landed after the docs were last updated (v2.4.0→v2.5.0). A new
reader (human or agent) gets a stale picture.

This is the **docs-regen** sub-project (the seeding-layer sub-project is complete and on
`main`). It reconciles every markdown doc to the current codebase.

## Scope (decided)

- **In:** all markdown docs — human project docs (`README.md`, `BLUEPRINT.md`,
  `WORKFLOW.md`, `USER_GUIDE.md`, `DEPLOYMENT.md`, `DEPLOYMENT_LOCAL.md`,
  `backend/README.md`, `frontend/README.md`), AI-instruction files (`CLAUDE.md`,
  `GEMINI.md`, `frontend/CLAUDE.md`, `frontend/AGENTS.md`,
  `.github/copilot-instructions.md`), `docs/ROADMAP.md` (consistency sweep), the
  `*-improvement.md` scratch notes (review/refresh-or-mark-historical, lowest priority),
  **and the in-app documentation pages** `frontend/src/app/(dashboard)/guide/page.tsx`
  (in-app User Guide, ~2000 lines) and `frontend/src/app/(dashboard)/workflow/page.tsx`
  (in-app transaction-flow / workflow, ~1150 lines) — these are the in-app equivalents of
  `USER_GUIDE.md`/`WORKFLOW.md` (documentation prose embedded in JSX) and must stay in
  sync with the same feature set.
- **Approach:** **reconcile + fill feature gaps** — preserve each doc's structure and
  accurate content; fix stale/incorrect facts, add coverage for everything shipped since
  2026-06-03, fix contradictions. No full rewrite, no restructuring.
- **Out:** new doc types, screenshots/diagrams regeneration, translating docs. (The
  in-app guide/workflow React pages ARE in scope — see Group D — but only their embedded
  documentation *content* is edited; their component structure/behavior is left intact.)

## Decisions (locked during brainstorming)

1. **Inventory-first:** establish one canonical current-state reference (§1); reconcile
   every doc against it to prevent per-doc drift.
2. **Reconcile, don't rewrite** — surgical fixes + gap-fills only.
3. **Verification = cross-check against the codebase** (no automated tests for prose); a
   reviewer confirms each doc's claims are backed by actual code.
4. All markdown in scope, grouped: human docs → AI-instruction docs → scratch notes.

## §1 · Canonical current-state inventory (the shared reference)

Every doc edit reconciles against this authoritative list. **Version: v2.5.0.**

**Accounting / reporting:**
- **Multi-level Chart of Accounts** — `Account.parent_id`/`is_group`; posting restricted
  to active leaf accounts; the **default CoA every tenant gets is now hierarchical**
  (group skeleton `1`/`11`/`12`/`2`/`21`/`3`/`4`/`41`/`49`/`5`/`51`/`52`/`59` in `db.py`,
  leaves parented).
- **Hierarchical reporting** (`services/account_tree.py` roll-up engine): Trial Balance
  → `{tree, totals}`; Balance Sheet → `{assets, liabilities, equity, totals}` (single
  period; RE-CUR synthetic equity line); P&L → `{revenue, expenses, totals}` + net
  profit. Comparison mode stays flat. Frontend `<AccountTree>` with expand/collapse +
  leaf drill-to-ledger on all three pages.
- **Deferred-revenue origination** (`services/deferred.py`): `product.is_deferred` →
  invoice credits Deferred Revenue (2300) + originates `DeferredRevenueSchedule`;
  `update_invoice` blocks edits once recognised, else reverses+rebuilds; existing
  recognition engine reused.
- **Voucher series** (#44): typed vouchers (SL/PU/CR/CP/JV/CN/DN…), Cash/Bank Book,
  voucher-type filters.
- **Comparative statements** (#43); **sub-ledger / consolidated GL** (#45);
  **selling/cost price** (#50); **posted-document editing** (#51) + **negative-stock
  guard on edit** (#48).

**Seeding:** default CoA hierarchical for all tenants; demo seed exercises deferred
origination, voucher types, 2 fiscal years, and multiple users (owner/accountant/clerk)
with varied Audit-Log attribution. Regeneration = purge + fresh reseed.

**Stable baseline (already documented, verify still accurate):** modern stack
(Next.js 16 / FastAPI), multi-tenancy, double-entry invariant, the 5 business models
(simple/services/trader/manufacturing/telecom_franchise), inventory, report builder,
audit log, Alembic migrations, desktop/script installers + in-app update.

## §2 · Per-document reconciliation scope

**Group A — human docs:**
- `README.md` — feature list, version (v2.5.0), quickstart accuracy.
- `BLUEPRINT.md` — architecture / data model / accounting design: add CoA hierarchy,
  `account_tree` roll-up, deferred origination, voucher types.
- `WORKFLOW.md` — business workflows: hierarchical-statement navigation, deferred-revenue
  lifecycle, voucher-typed entries, posted-edit rules.
- `USER_GUIDE.md` — end-user how-to: expand/collapse/drill reports, deferred products,
  comparative view.
- `DEPLOYMENT.md`, `DEPLOYMENT_LOCAL.md` — verify migrations/seed/version steps current.
- `backend/README.md`, `frontend/README.md` — verify dev commands/structure current.

**Group B — AI-instruction docs:**
- `CLAUDE.md` — add new modules (`services/account_tree.py`, `services/deferred.py`),
  hierarchical-CoA note in the architecture/migrations sections, seed changes.
- `GEMINI.md`, `frontend/CLAUDE.md`, `frontend/AGENTS.md`,
  `.github/copilot-instructions.md` — keep consistent with `CLAUDE.md` (these are largely
  mirrors / short pointers; verify they don't contradict current state).

**Group C — consistency + scratch:**
- `docs/ROADMAP.md` — final sweep (already updated this session).
- `claude-improvement.md`, `copilot-imrovement.md`, `gemini-improvement.md` — review;
  refresh if still relevant, else prepend a short "historical working notes" header.

**Group D — in-app documentation pages (React/TSX prose):**
- `frontend/src/app/(dashboard)/guide/page.tsx` — in-app **User Guide**: reconcile its
  embedded how-to content to current features (hierarchical reports expand/collapse +
  drill, deferred-revenue products, voucher types, comparative statements, posted-edit).
- `frontend/src/app/(dashboard)/workflow/page.tsx` — in-app **transaction-flow /
  workflow** guide: reconcile the documented flows (sales/purchase/payment cycles,
  voucher-typed entries, deferred-revenue lifecycle, hierarchical-statement navigation).
- **Edit only the documentation content** (JSX text/sections); do NOT change the page's
  component logic, routing, or layout primitives. The page must still compile.

## §3 · Execution & verification

Per-doc (or small-group) tasks, committed frequently, in order A → B → C → D. For each
doc: read it, diff its claims against the §1 inventory and the actual code, apply surgical
fixes + gap-fills. **Verification:** a reviewer cross-checks the edited doc's factual
claims against the codebase (file paths, endpoint shapes, feature behavior, version
numbers) and flags any claim not backed by code. No prose is invented that the code
doesn't support. **For Group D (TSX pages), additionally run `npm run lint`** and confirm
no new errors in the edited page — content edits must not break compilation.

## Success criteria

A reader of any doc sees current behavior: the docs describe the hierarchical CoA +
roll-up reports, deferred-revenue origination, voucher series, and the v2.5.0 feature
set; version references read v2.5.0; no claim contradicts the codebase; the AI-instruction
files point agents at the real current module map. Existing accurate content and
structure are preserved.
