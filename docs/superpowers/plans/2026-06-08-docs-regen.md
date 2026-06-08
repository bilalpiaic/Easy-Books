# Documentation Regeneration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reconcile every project document (markdown + the two in-app React doc pages) to the current v2.5.0 codebase — fix stale facts, add coverage for features shipped since 2026-06-03, fix contradictions — preserving accurate content and structure.

**Architecture:** Inventory-first. The spec's §1 "canonical current-state inventory" is the single source of truth; every doc is reconciled against it. Surgical edits only (no rewrites/restructure). Verification per doc = cross-check claims against the codebase; for the TSX pages, also `npm run lint`.

**Tech Stack:** Markdown; React/TSX (Next.js 16) for the two in-app pages.

**Spec:** `docs/superpowers/specs/2026-06-08-docs-regen-design.md` — **read §1 (inventory) and §2 (per-doc scope) before each task.** This plan does not re-transcribe the final prose (that IS the work); it specifies, per doc, the exact features/facts to add and the staleness to correct, plus how to verify.

**Base:** `main` @ v2.5.0. Branch: `feature/docs-regen`.

**The §1 inventory (must be reflected in every applicable doc):** version **v2.5.0**; multi-level hierarchical CoA (every tenant; group skeleton in `db.py`; posting to leaves only); hierarchical reporting (`services/account_tree.py`; TB `{tree,totals}`, BS `{assets,liabilities,equity,totals}`, P&L `{revenue,expenses,totals}`+net_profit; comparison stays flat; `<AccountTree>` expand/collapse + leaf drill); deferred-revenue origination (`services/deferred.py`; `product.is_deferred`→2300 + schedules + recognition; edit blocks-if-recognized else rebuild); voucher series (#44, SL/PU/CR/CP/JV/CN/DN, Cash/Bank Book); comparative statements (#43); sub-ledger/consolidated GL (#45); selling/cost price (#50); posted-edit (#51) + negative-stock-on-edit guard (#48); seeding: hierarchical default CoA + demo exercises deferred/vouchers/2-FY/multi-user.

**Verification (every task):** for each edited doc, the reviewer cross-checks factual claims against the codebase (file paths exist, endpoint shapes match `routers/reports.py`/`invoices.py`, version reads v2.5.0, no claim contradicts code). Invent no behavior the code doesn't support.

---

### Task 1: README.md + version references

**Files:** Modify `README.md` (300 lines)

- [ ] **Step 1: Reconcile.** Read `README.md`. Apply:
  - Update the version/release reference to **v2.5.0** (search the file for any `2.x` version string).
  - In the feature list / overview, add (one line each): multi-level Chart of Accounts + hierarchical financial statements (roll-up & drill-down); deferred-revenue recognition; voucher series + Cash/Bank Book; comparative statements. Remove/repair any feature description that contradicts current behavior.
  - Verify the quickstart commands match `CLAUDE.md` (backend `uv sync` / `python main.py`; frontend `npm install` / `npm run dev`).
- [ ] **Step 2: Verify.** Re-read the edited sections; confirm each added claim is backed by code (the features exist per §1). Confirm no command is wrong.
- [ ] **Step 3: Commit.**
```bash
git add README.md
git commit -m "docs(readme): reconcile to v2.5.0 feature set"
```

---

### Task 2: BLUEPRINT.md (architecture / data model / accounting design)

**Files:** Modify `BLUEPRINT.md` (1059 lines)

- [ ] **Step 1: Reconcile.** Read `BLUEPRINT.md`. In the architecture / data-model / accounting sections, add or correct:
  - **Chart of Accounts:** now multi-level — `Account.parent_id`/`is_group`; default CoA hierarchical (group skeleton `1/11/12/2/21/3/4/41/49/5/51/52/59`); posting restricted to active leaf accounts.
  - **Reporting engine:** `services/account_tree.py` roll-up (parent = own + Σ descendants); TB/BS/P&L return nested trees (single period); comparison mode flat.
  - **Deferred revenue:** `services/deferred.py` origination (`product.is_deferred` → Deferred Revenue 2300 + `DeferredRevenueSchedule`); recognition engine; edit policy (block-if-recognized else reverse+rebuild).
  - **Voucher series** (typed transactions) if not already described accurately.
  - Fix any data-model/CoA description that predates the hierarchy.
- [ ] **Step 2: Verify** added claims against `models.py` (Account fields, DeferredRevenueSchedule), `services/account_tree.py`, `services/deferred.py`, `routers/reports.py`.
- [ ] **Step 3: Commit.**
```bash
git add BLUEPRINT.md
git commit -m "docs(blueprint): add multi-level CoA, hierarchical reporting, deferred revenue, voucher series"
```

---

### Task 3: WORKFLOW.md (business workflows)

**Files:** Modify `WORKFLOW.md` (1523 lines)

- [ ] **Step 1: Reconcile.** Read `WORKFLOW.md`. Add/correct workflow coverage for:
  - Navigating hierarchical statements (expand/collapse groups; drill leaf → ledger → voucher).
  - Deferred-revenue lifecycle (flag product deferred → invoice originates schedule → periodic recognition → edit rules).
  - Voucher-typed entries (which document → which voucher type; Cash/Bank Book).
  - Posted-document editing rules (incl. negative-stock guard on edit; block-if-paid / block-if-recognized).
  - Comparative-statement workflow.
  - Fix any workflow step that no longer matches the app.
- [ ] **Step 2: Verify** against `routers/invoices.py` (posted-edit/deferred), `routers/reports.py` (statements), `routers/deferred_revenue.py` (recognition), the frontend report pages.
- [ ] **Step 3: Commit.**
```bash
git add WORKFLOW.md
git commit -m "docs(workflow): add hierarchical statements, deferred revenue, voucher & posted-edit flows"
```

---

### Task 4: USER_GUIDE.md (end-user how-to)

**Files:** Modify `USER_GUIDE.md` (850 lines)

- [ ] **Step 1: Reconcile.** Read `USER_GUIDE.md`. Add end-user how-to for:
  - Reading hierarchical TB/Balance Sheet/P&L (expand/collapse, subtotals, drill into a line).
  - Setting up a deferred-revenue product and reading the deferred-revenue screen / running recognition.
  - Using voucher types / Cash & Bank Book.
  - Comparative (compare-period) view on BS/P&L.
  - Editing a posted invoice (what's allowed/blocked).
  - Correct any screen/menu reference that has changed.
- [ ] **Step 2: Verify** menu/feature references against the frontend route structure (`frontend/src/app/(dashboard)/...`).
- [ ] **Step 3: Commit.**
```bash
git add USER_GUIDE.md
git commit -m "docs(user-guide): add hierarchical reports, deferred revenue, vouchers, comparative, posted-edit"
```

---

### Task 5: Deployment + component READMEs (verification-led)

**Files:** Modify (as needed) `DEPLOYMENT.md`, `DEPLOYMENT_LOCAL.md`, `backend/README.md`, `frontend/README.md`

- [ ] **Step 1: Reconcile.** Read each. These are mostly setup/ops docs — verify and correct only what's stale:
  - Migrations: Alembic is the source of truth; `alembic upgrade head` runs on install. Confirm the documented steps match `CLAUDE.md`.
  - Seeding: demo auto-seed on first install (`SEED_DEMO`), purge/reseed via Settings; confirm wording matches current behavior.
  - Version references → v2.5.0 where present.
  - Dev commands (`uv sync`/`python main.py`, `npm run dev`/`build`) — confirm correct.
  - Add a one-line note that the default CoA is hierarchical (if these docs describe initial data).
- [ ] **Step 2: Verify** commands/paths against `CLAUDE.md`, `backend/` layout, installer scripts.
- [ ] **Step 3: Commit.**
```bash
git add DEPLOYMENT.md DEPLOYMENT_LOCAL.md backend/README.md frontend/README.md
git commit -m "docs(deploy/readme): verify + reconcile setup/ops docs to v2.5.0"
```

---

### Task 6: AI-instruction files

**Files:** Modify `CLAUDE.md` (primary); reconcile `GEMINI.md`, `frontend/CLAUDE.md`, `frontend/AGENTS.md`, `.github/copilot-instructions.md`

- [ ] **Step 1: Reconcile CLAUDE.md.** Read `CLAUDE.md`. In the backend architecture / services / "Adding common features" sections add:
  - `services/account_tree.py` (hierarchical roll-up engine) in the services list.
  - `services/deferred.py` (deferred-revenue origination) + note `create_invoice`/`update_invoice` split to 2300.
  - Note the **default CoA is now hierarchical** (group skeleton; posting to leaves) in the CoA / migrations notes.
  - Note the demo seed exercises deferred/vouchers/2-FY/multi-user.
  - Reports section: TB/BS/P&L now return nested trees (single period); `account_tree` is the roll-up.
- [ ] **Step 2: Reconcile mirrors.** Read `GEMINI.md`, `frontend/CLAUDE.md`, `frontend/AGENTS.md`, `.github/copilot-instructions.md`. These are short/pointer/mirror files — ensure none contradicts the current state; if one is a CLAUDE.md mirror, apply the same key additions; if it's a pointer (e.g. `frontend/CLAUDE.md` → `@AGENTS.md`), leave the pointer but fix any stale claim in the target.
- [ ] **Step 3: Verify** the module paths exist (`services/account_tree.py`, `services/deferred.py`) and the descriptions match the code.
- [ ] **Step 4: Commit.**
```bash
git add CLAUDE.md GEMINI.md frontend/CLAUDE.md frontend/AGENTS.md .github/copilot-instructions.md
git commit -m "docs(agents): update AI-instruction files with account_tree, deferred, hierarchical CoA"
```

---

### Task 7: ROADMAP sweep + scratch notes

**Files:** Modify `docs/ROADMAP.md` (sweep), `claude-improvement.md`, `copilot-imrovement.md`, `gemini-improvement.md`

- [ ] **Step 1: ROADMAP sweep.** Read `docs/ROADMAP.md`. It was updated this session; confirm it reflects: #47/#48/#53 done (v2.5.0), seeding-layer done, remaining = #40/#41/#42/#52§3/§4/§6. Fix any drift.
- [ ] **Step 2: Scratch notes.** Read each `*-improvement.md`. If its content is still actionable, refresh outdated references; otherwise prepend a one-line header: `> Historical working notes (as of <date>); see docs/ROADMAP.md for current status.` Do not delete.
- [ ] **Step 3: Commit.**
```bash
git add docs/ROADMAP.md claude-improvement.md copilot-imrovement.md gemini-improvement.md
git commit -m "docs(roadmap+notes): final consistency sweep; mark scratch notes historical"
```

---

### Task 8: In-app User Guide page (guide/page.tsx)

**Files:** Modify `frontend/src/app/(dashboard)/guide/page.tsx` (~2002 lines)

- [ ] **Step 1: Reconcile content only.** Read the page. It renders the in-app User Guide as JSX prose sections. Edit ONLY the documentation content (text/section JSX), NOT component logic/imports/layout. Add/correct guidance for: hierarchical reports (expand/collapse + drill), deferred-revenue products + recognition, voucher types / Cash & Bank Book, comparative view, posted-edit rules. Fix any described behavior that no longer matches.
- [ ] **Step 2: Verify compile.** Run `cd frontend && npm run lint`; confirm no new errors in `guide/page.tsx`. Confirm added claims match app behavior.
- [ ] **Step 3: Commit.**
```bash
git add "frontend/src/app/(dashboard)/guide/page.tsx"
git commit -m "docs(in-app guide): reconcile User Guide content to v2.5.0 features"
```

---

### Task 9: In-app workflow/transaction-flow page (workflow/page.tsx)

**Files:** Modify `frontend/src/app/(dashboard)/workflow/page.tsx` (~1150 lines)

- [ ] **Step 1: Reconcile content only.** Read the page. Edit ONLY the documentation content. Reconcile the documented transaction flows: sales (invoice→receipt) and purchase (bill→payment) cycles with their voucher types; deferred-revenue lifecycle; hierarchical-statement navigation; posted-edit. Fix stale flow descriptions.
- [ ] **Step 2: Verify compile.** `cd frontend && npm run lint`; no new errors in `workflow/page.tsx`. Claims match behavior.
- [ ] **Step 3: Commit.**
```bash
git add "frontend/src/app/(dashboard)/workflow/page.tsx"
git commit -m "docs(in-app workflow): reconcile transaction-flow content to v2.5.0 features"
```

---

### Task 10: Final consistency pass

- [ ] **Step 1: Cross-doc consistency.** Grep all edited docs for the version string and key feature names; confirm consistent terminology (e.g. "hierarchical reports", "deferred revenue", voucher-type names SL/PU/CR/CP/JV/CN/DN) across docs.
  Run: `grep -rInE "2\.[0-9]\.[0-9]" README.md BLUEPRINT.md WORKFLOW.md USER_GUIDE.md DEPLOYMENT*.md CLAUDE.md docs/ROADMAP.md` — confirm all version refs read 2.5.0.
- [ ] **Step 2: Frontend lint (whole).** `cd frontend && npm run lint` — no new errors from the two edited pages.
- [ ] **Step 3: Commit (if any consistency fixes).**
```bash
git add -A
git commit -m "docs: final cross-document consistency pass (v2.5.0)"
```

---

## Self-Review notes

- **Spec coverage:** §1 inventory → referenced by every task; §2 Group A → Tasks 1-5; Group B → Task 6; Group C → Task 7; Group D → Tasks 8-9; §3 verification → each task's verify step + Task 10.
- **Granularity note:** for prose, each task specifies the exact feature/fact set to add + the staleness to fix + the verification, rather than transcribing final wording (which would be the work itself). This is the appropriate altitude for docs reconciliation; the §1 inventory keeps wording consistent across docs.
- **Group D guardrail:** content-only edits; `npm run lint` gate ensures the React pages still compile.
- **Ordering:** A (human docs) → B (agent files) → C (roadmap/scratch) → D (in-app pages) → final consistency. Each commit is independent and low-risk (docs only; no code behavior changes).
