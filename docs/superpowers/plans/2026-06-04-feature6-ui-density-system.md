# Feature 6: UI Density System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One density source of truth (CSS tokens + semantic classes) controlling spacing across tables, forms, cards, and print, with a Comfortable/Compact toggle in Settings (per-tenant).

**Architecture:** Add `--ui-*` density variables + `.ui-table/.ui-th/.ui-td/.ui-card/.ui-field/.ui-section` classes to `globals.css`; refactor the existing `@media print` cell padding to read the same tokens. A `ui_density` setting drives `document.documentElement.dataset.density`. Then sweep the ~20 hand-rolled table pages and form modals to use the semantic classes and drop inline `px-6 py-4` / `px-4 py-3`.

**Tech Stack:** Tailwind CSS v4 (CSS `@theme`/vars, no `tailwind.config`), Next.js 16 / React 19 / TypeScript, FastAPI settings, pytest.

**Build position:** FIRST — before Features 1–5, so their UI inherits the classes.

---

### Task 1: Density tokens + semantic classes + print refactor

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Add tokens and screen classes**

After the `:root { ... }` brand block (line ~11) add:

```css
/* ── Density tokens ── */
:root {
  --ui-cell-px: 1rem;      --ui-cell-py: 0.55rem;
  --ui-head-py: 0.55rem;   --ui-section-gap: 1.25rem;
  --ui-card-pad: 1.25rem;  --ui-control-py: 0.55rem;  --ui-control-px: 0.9rem;
}
html[data-density="compact"] {
  --ui-cell-px: 0.7rem;    --ui-cell-py: 0.32rem;
  --ui-head-py: 0.38rem;   --ui-section-gap: 0.85rem;
  --ui-card-pad: 0.9rem;   --ui-control-py: 0.4rem;   --ui-control-px: 0.7rem;
}

/* ── Density semantic classes (screen) ── */
.ui-th { padding: var(--ui-head-py) var(--ui-cell-px); }
.ui-td { padding: var(--ui-cell-py) var(--ui-cell-px); }
.ui-card { padding: var(--ui-card-pad); }
.ui-field { padding: var(--ui-control-py) var(--ui-control-px); }
```

- [ ] **Step 2: Make print read the same density (with print-pt scale)**

Inside `@media print`, replace the fixed paddings at lines ~173 and ~176:

```css
  th { ... padding: 5pt 6pt !important; ... }
  td { padding: 4pt 6pt !important; }
```
with rules that also cover the semantic classes (print stays in pt for fidelity):

```css
  th, .ui-th { padding: 5pt 6pt !important; }
  td, .ui-td { padding: 4pt 6pt !important; }
```

- [ ] **Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: compiles; no CSS errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/globals.css
git commit -m "feat(ui): density tokens + semantic classes; print reads same scale"
```

---

### Task 2: `ui_density` setting + Comfortable/Compact toggle

**Files:**
- Modify: `backend/routers/settings.py:24-55` (`SettingsUpdate`)
- Modify: `frontend/src/context/SettingsContext.tsx` (interface + defaults + apply effect)
- Modify: `frontend/src/app/(dashboard)/settings/page.tsx` (toggle UI)
- Test: `backend/tests/test_settings_density.py`

- [ ] **Step 1: Write the failing backend test**

```python
# backend/tests/test_settings_density.py
"""ui_density setting round-trips through the settings PATCH."""


def test_ui_density_persists(client, admin_headers):
    h = admin_headers
    r = client.patch("/api/settings", headers=h, json={"ui_density": "compact"})
    assert r.status_code == 200
    got = client.get("/api/settings", headers=h).json()
    assert got["ui_density"] == "compact"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && uv run pytest tests/test_settings_density.py -v`
Expected: FAIL — key not in `SettingsUpdate`, dropped on PATCH.

- [ ] **Step 3: Add the key to `SettingsUpdate`**

In `backend/routers/settings.py`, add to `SettingsUpdate`:

```python
    ui_density: Optional[str] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && uv run pytest tests/test_settings_density.py -v`
Expected: PASS.

- [ ] **Step 5: Add to frontend settings context**

In `frontend/src/context/SettingsContext.tsx`: add `ui_density: string` to
`AppSettings` (interface, line ~6) and `ui_density: "comfortable"` to `defaults`
(line ~39). In `SettingsProvider`, add an effect that applies it:

```tsx
useEffect(() => {
  document.documentElement.dataset.density =
    settings.ui_density === "compact" ? "compact" : "comfortable"
}, [settings.ui_density])
```

- [ ] **Step 6: Add the toggle to the Settings page**

In `frontend/src/app/(dashboard)/settings/page.tsx`, near the existing
`block_negative_stock` control (line ~610), add a density `<select>`:

```tsx
<div>
  <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/60 mb-1">Display Density</label>
  <select
    value={form.ui_density}
    onChange={e => handleChange('ui_density', e.target.value)}
    className="ui-field w-full bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
  >
    <option value="comfortable">Comfortable</option>
    <option value="compact">Compact</option>
  </select>
</div>
```

(Confirm `form` initial state includes `ui_density`; add it mirroring how
`block_negative_stock` is seeded into `form`.)

- [ ] **Step 7: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 8: Manual check**

Toggle Comfortable↔Compact in Settings → tables/forms tighten/loosen live;
reload preserves the choice.

- [ ] **Step 9: Commit**

```bash
git add backend/routers/settings.py backend/tests/test_settings_density.py frontend/src/context/SettingsContext.tsx "frontend/src/app/(dashboard)/settings/page.tsx"
git commit -m "feat(settings): per-tenant display density toggle (Comfortable/Compact)"
```

---

### Task 3: Sweep table pages onto `.ui-th` / `.ui-td`

**Files (find the full list first):**
- Discover: `grep -rln "px-6 py-4" frontend/src` (≈20 files: products, invoices, bills, customers, vendors, journal, trial-balance, balance, reconciliations, purchase-orders, payments-received, bill-payments, reports pages, etc.)

- [ ] **Step 1: List the files**

Run: `grep -rln "px-6 py-4" frontend/src`
Process them in small batches (3–5 files per commit) so each diff is reviewable.

- [ ] **Step 2: Apply the canonical transform per `<table>`**

For every table cell, replace the inline padding utilities with the semantic
class, keeping all non-padding utilities (alignment, font, color, width).

Header cells — before/after:
```tsx
<th className="px-6 py-4 text-left text-xs font-bold uppercase tracking-widest text-black/60">Name</th>
```
```tsx
<th className="ui-th text-left text-xs font-bold uppercase tracking-widest text-black/60">Name</th>
```

Body cells — before/after:
```tsx
<td className="px-6 py-4 text-right font-mono">{fmt(x)}</td>
```
```tsx
<td className="ui-td text-right font-mono">{fmt(x)}</td>
```

Rules:
- Only strip the `px-* py-*` (and `px-4 py-4`, `px-3 py-2` variants used as cell
  padding) — leave `text-*`, `font-*`, `w-*`, `truncate`, color utilities intact.
- Do not touch non-cell paddings (buttons, badges, page chrome).
- Keep `min-w-[...]` wrappers and `overflow-x-auto` (responsive scroll).

- [ ] **Step 3: After each batch — lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 4: Visual check a representative page per batch**

Open one page from the batch (e.g. `/products`, `/journal`, `/trial-balance`):
rows are tighter and uniform; columns not crushed; horizontal scroll still works
on a narrow window.

- [ ] **Step 5: Commit each batch**

```bash
git add frontend/src/app/...
git commit -m "refactor(ui): tables use density classes (batch N)"
```

---

### Task 4: Sweep form modals / controls onto `.ui-field`

**Files:**
- Discover: `grep -rln "px-4 py-3" frontend/src` (form inputs/selects in modals)

- [ ] **Step 1: List the files**

Run: `grep -rln "px-4 py-3" frontend/src`

- [ ] **Step 2: Apply the transform to inputs/selects**

Replace control padding with `ui-field`, keeping the rest:
```tsx
<input className="w-full px-4 py-3 bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
```
```tsx
<input className="ui-field w-full bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]" />
```

- [ ] **Step 3: Lint + build**

Run: `cd frontend && npm run lint && npm run build`
Expected: no errors.

- [ ] **Step 4: Manual check**

Open Add Product / Record Payment / New Invoice modals: fields are consistent
and right-sized at both densities.

- [ ] **Step 5: Commit (batched)**

```bash
git add frontend/src
git commit -m "refactor(ui): form controls use density field class"
```

---

### Task 5: Cross-cutting verification (screen + print, both densities)

- [ ] **Step 1: Full frontend build + lint**

Run: `cd frontend && npm run lint && npm run build`
Expected: clean.

- [ ] **Step 2: Backend suite**

Run: `cd backend && uv run pytest -q`
Expected: all pass (density setting test included).

- [ ] **Step 3: Print check**

Print-preview a wide report (Trial Balance or General Ledger) and an invoice in
both Comfortable and Compact: print padding stays at the tuned pt scale (screen
density does not distort print), headers repeat, nothing clipped.

- [ ] **Step 4: Narrow-viewport check**

At ~600px width a wide table scrolls horizontally rather than crushing columns.

- [ ] **Step 5: Commit any final tweaks**

```bash
git add -A
git commit -m "chore(ui): density verification tweaks"
```

---

## Self-Review Notes
- Spec Feature 6 fully covered: tokens + semantic classes (Task 1), print parity (Task 1 Step 2), toggle plumbing screen+settings+backend (Task 2), table sweep (Task 3), form sweep (Task 4), screen/print/responsive verification (Task 5).
- "Neither squeezed nor expanded": tuned default tighter than today's `px-6 py-4`; `min-w` + horizontal scroll retained so columns never crush (Task 3 rules).
- Mechanical sweep risk (accidentally stripping non-padding utilities) is mitigated by the explicit keep/strip rules and per-batch build+visual checks.
