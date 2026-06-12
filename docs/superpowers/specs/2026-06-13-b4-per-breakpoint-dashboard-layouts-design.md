# B4: Per-Breakpoint Dashboard Layouts — Design

**Date:** 2026-06-13
**Status:** Approved
**Scope:** Frontend only — the backend layout store (`UserDashboardLayout` KV, GET/PUT `/api/dashboard/layout`) remains an opaque JSON blob and is NOT modified.

## Problem

The dashboard grid (shipped in #52 §3 Phase 2) stores a single v2 layout
`{version: 2, items: [{id, x, y, w, h}]}` and feeds the **same item array to all
three responsive breakpoints** (`lg` 4 cols / `sm` 2 cols / `xs` 1 col).
Two consequences:

1. **Lossy down-conversion.** react-grid-layout clamps 4-column coordinates
   into 2 and 1 columns with its own compaction algorithm; users cannot
   influence the tablet/phone arrangement.
2. **Overwrite bug.** `onLayoutChange` fires with the *active* breakpoint's
   layout. Editing while the window is narrow overwrites the saved desktop
   arrangement with clamped mobile coordinates.

## Decisions (locked with user)

- **Per-breakpoint layouts**: each of desktop/tablet/phone can remember its own
  positions and sizes.
- **Shared membership**: the same set of widgets appears at every width; only
  position/size differ. Add/remove anywhere affects all breakpoints.
- **Sparse overrides** (Approach A): `lg` is canonical; `sm`/`xs` layouts exist
  only after the user actually drags/resizes at that width. Untouched
  breakpoints keep auto-deriving from `lg`, so desktop edits continue to flow
  down to mobile until mobile is explicitly customized.
- **Reset** returns to factory default and clears all overrides (not
  per-breakpoint reset).

### Rejected alternatives

- **Eager v3 (store all three breakpoints on every save):** freezes the
  auto-derived mobile layout at save time — a desktop-only user gets a stale
  mobile arrangement that no longer follows their desktop changes.
- **Explicit breakpoint switcher in customize mode:** extra UI surface; window
  resizing already switches breakpoints via `WidthProvider`. Can be layered on
  later without schema changes.

## Schema v3

```ts
type Breakpoint = "lg" | "sm" | "xs"

interface GridLayoutV3 {
  version: 3
  layouts: {
    lg: GridItem[]      // required — canonical, defines membership
    sm?: GridItem[]     // present only once customized at tablet width
    xs?: GridItem[]     // present only once customized at phone width
  }
}
```

`GridItem` is unchanged: `{id, x, y, w, h}`.

### Migration chain (pure, in `resolveLayout`)

| Saved blob | Resolution |
|---|---|
| v3 | validate each breakpoint (below) |
| v2 `{version:2, items}` | `{lg: validateV2(items)}` — no overrides |
| v1 `{version:1, widgets}` | `{lg: migrateV1toV2(...)}` |
| null / garbage | `{lg: defaultGrid()}` |

### Validation per breakpoint

- `lg`: as today (dedupe, registry/shortcut existence, model+role filter for
  shortcuts, clamp to widget `minSize`).
- `sm` / `xs`: additionally **drop ids not present in the validated `lg`**
  (shared-membership invariant) and clamp width to the breakpoint's column
  count (sm=2, xs=1) using `min(minW, cols)` so widgets with `minSize.w = 2`
  still fit a 1-column phone.
- An `sm`/`xs` array that validates to empty is dropped (treated as absent).

## Hook changes — `useDashboardLayout.ts`

State: `layouts: ResolvedLayouts` (`{lg: GridItem[], sm?: GridItem[], xs?: GridItem[]}`)
replaces the flat `items` array.

| API | Behavior |
|---|---|
| `applyLayout(bp, allLayouts)` | For each breakpoint present in `allLayouts`: accept `lg` unconditionally; accept `sm`/`xs` **only if that override already exists**. Breakpoints absent from `allLayouts` are left untouched. |
| `markCustomized(bp)` | Create the `sm`/`xs` override from RGL's current derived layout. Called from drag/resize stop only. No-op for `lg`. |
| `addWidget(id)` | Append (packed at bottom) to `lg` and to every existing override, with per-breakpoint width clamping. |
| `removeWidget(id)` | Filter from `lg` and every existing override. |
| `reset()` | `{lg: defaultGrid()}` — clears all overrides. |
| `reload()` | Re-resolve from last-saved blob. |
| `save()` | PUT v3 `{version: 3, layouts}` (omit absent overrides). |
| `dirty` | Serialized comparison of the full layouts object vs. resolved baseline. |

## Grid component changes — `DashboardGrid.tsx`

- Track the active breakpoint via `onBreakpointChange` (initial value derived
  from window width with the same thresholds: 1024 / 640 / 0).
- `layouts` prop: pass only the keys we have — RGL auto-derives missing
  breakpoints from the closest defined one.
- `onDragStop` / `onResizeStop` → `markCustomized(activeBp)` then apply. These
  are the only signals that *create* an override (genuine user gestures).
- `onLayoutChange` → `applyLayout(activeBp, allLayouts)` while editing — keeps
  existing overrides in sync with add/remove compaction, but never creates one
  (breakpoint switches fire this event spuriously).
- Editing toolbar: small static label showing which layout is being edited
  ("Desktop layout" / "Tablet layout" / "Phone layout"). No new controls.

## Error handling

- Unknown future versions or malformed blobs fall back to `defaultGrid()`
  (existing behavior, preserved).
- Save failures keep the current inline error banner; no behavior change.

## Testing & verification

- **Backend:** zero changes — full suite (372) must stay green untouched.
- **Frontend gate:** `npm run build` + `npm run lint` at the existing baseline
  (2 errors / 14 warnings, all pre-existing).
- **Manual verification checklist:**
  1. Existing v2 blob loads and renders identically at desktop width.
  2. Editing at desktop width does not create `sm`/`xs` overrides (inspect PUT
     payload).
  3. Dragging at narrow width creates exactly one override for that breakpoint.
  4. Re-editing desktop afterward leaves the mobile override untouched.
  5. Add/remove widget propagates to all breakpoints.
  6. Reset clears overrides and restores the factory grid.
