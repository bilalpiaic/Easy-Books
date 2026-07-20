# Weaving Calculators Implementation Plan (#196)

> Spec: `docs/superpowers/specs/2026-07-20-weaving-calculators-design.md`

**Goal:** Ship Weaving + Sizing planning calculators with contract assign, mismatch override, and history.

**Branch:** `feat/weaving-calculators-196`

## Task 1: Pure engine (TDD)

- Create `backend/tests/test_weaving_yarn_calc.py` (failing)
- Create `backend/services/weaving_yarn_calc.py` (green)

## Task 2: Schema + API (TDD)

- Extend models + `0037_weaving_calculators.py`
- Register `weaving.calculators` permission
- Create `backend/tests/test_weaving_calculators.py` (failing)
- Create `backend/routers/weaving_calculators.py`, mount in `main.py`

## Task 3: Frontend mirror (TDD)

- `frontend/src/lib/weavingYarnCalc.ts` + vitest

## Task 4: UI

- Calculator pages, nav, setup `count_ne`, contract planned + history

## Task 5: ADD

- pytest + vitest green; PR `Closes #196`
