# Spec: Weaving + Sizing Calculators (#196)

**Issue:** https://github.com/bilalpiaic/Easy-Books/issues/196  
**Module:** `weaving` (already installed via #140 / PR #194)  
**v1:** Planning calculators only — assign planned yarn quantities onto contracts; **no GL**, no PDF/CSV export, Ne count system only.

## Goals

1. **Weaving Calculator** — EPI/PPI fabric yarn consumption (Ne) → warp/weft/total lbs + kg + 100-lb bags.
2. **Sizing Calculator** — unsized warp → sized yarn with pickup, stretch, wastes.
3. **Assign to Contract** — server recomputes, writes planned snapshot on `WvContract`, appends `WvCalcRun` history.
4. **Mismatch guard** — if calculated qty vs existing planned (or count) differs by >10%, require `override_reason`.

## Non-goals

- GL posting / Dispatch → Invoice
- PDF/CSV export
- Tex / denier count systems
- Standalone `/calculators` outside Weaving nav
- Changing ops docs (yarn inward / sizing entry) formulas

## Conversion

Reuse `#140` helpers (`services.weaving_calc.weight_triple`):

```
Lbs  = Kg × 2.2046226218
Bags = Lbs ÷ 100
kg   = lbs / 2.2046226218   (when formula yields lbs first)
```

## Formulas

### Weaving (Ne)

Waste factor is **additive** (matches issue sample): `waste = 1 + vis/100 + inv/100` (not compounded).

```
Warp_lbs = (EPI × Width_in × Length_yd × (1 + Crimp_w/100) × waste) / (840 × WarpNe)
Weft_lbs = (PPI × Width_in × Length_yd × (1 + Crimp_f/100) × waste) / (840 × WeftNe)
Total_lbs = Warp_lbs + Weft_lbs
*_kg = *_lbs / 2.2046226218
Net_lbs (before waste) = Total_lbs / waste   when waste > 0
```

Zero / missing Ne → that leg returns 0 (no division by zero).

**Worked example** (EPI=60, PPI=50, W=60 in, L=1000 yd, WarpNe=40, WeftNe=30, Crimp_w=10, Crimp_f=5, Vis=3, Inv=1):

| Leg | lbs | kg (approx) |
|-----|-----|-------------|
| Warp | 122.5714 | 55.598 |
| Weft | 130.0000 | 58.967 |
| Total | 252.5714 | 114.565 |

### Sizing

```
waste = 1 + vis/100 + inv/100
gross_kg = unsized_kg × (1 + pickup/100) × (1 + stretch/100) × waste
net_before_waste_kg = unsized_kg × (1 + pickup/100) × (1 + stretch/100)
```

Attach `weight_triple` to unsized, net, and gross.

**Worked example** (unsized=100 kg, pickup=12, stretch=1.5, vis=0.7, inv=1.0):

- net ≈ 100 × 1.12 × 1.015 = 113.68 kg  
- waste = 1.017  
- gross ≈ 115.61256 kg

## Assign + mismatch

Compare calculator outputs to the contract’s **existing planned snapshot** (if any):

- Qty mismatch when `|calc_total − planned_total| / max(planned_total, ε) > 0.10` and `planned_total > 0`
- Count mismatch when contract has `warp_count_ne` / `weft_count_ne` set and calc counts differ (tolerance 0 — exact Ne compare)
- First assign (no prior planned) → always OK
- On mismatch without `override_reason` → HTTP 400 with `warnings[]`
- On success → update contract planned fields + insert `WvCalcRun`

**Weaving assign writes:** `planned_warp_kg`, `planned_weft_kg`, `planned_total_yarn_kg`, `warp_count_ne`, `weft_count_ne`, `last_calc_at`  
**Sizing assign writes:** `planned_total_yarn_kg` (gross sized), `last_calc_at` (leaves warp/weft counts alone unless provided)

## Data model

- `WvYarnType.count_ne` — optional Decimal
- `WvContract`: `planned_warp_kg`, `planned_weft_kg`, `planned_total_yarn_kg`, `warp_count_ne`, `weft_count_ne`, `last_calc_at`
- `WvCalcRun`: tenant_id, contract_id, calc_type (`weaving`|`sizing`), inputs JSON, outputs JSON, override_reason, created_by_id, created_at

Migration `0037_weaving_calculators` revises `0036_weaving`.

## API

| Method | Path | Perm |
|--------|------|------|
| POST | `/api/weaving/calculators/weaving` | view |
| POST | `/api/weaving/calculators/sizing` | view |
| POST | `/api/weaving/calculators/weaving/assign` | edit |
| POST | `/api/weaving/calculators/sizing/assign` | edit |
| GET | `/api/weaving/calculators/history?contract_id=` | view |

Module gate `_require_weaving` on all. Resource: `weaving.calculators`.

## UI

- `/weaving/calculators/weaving`, `/weaving/calculators/sizing`
- Nav + SubNav under Weaving; hub tiles
- Setup: edit `count_ne` on yarn types
- Contract detail: planned yarn snapshot + history list + links to calculators

## Acceptance

- [ ] Calculators work independently with accurate formulas
- [ ] Unit conversions correct (Kg | Lbs | Bags via shared utility)
- [ ] Assign button updates contract (API)
- [ ] Popup / block triggers on mismatch; override with reason allowed
- [ ] Clean UI, mobile-friendly under Weaving
- [ ] Backend + frontend tests with shared numeric fixtures
