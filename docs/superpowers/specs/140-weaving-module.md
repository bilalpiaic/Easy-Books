# Spec: Weaving Module (#140)

**Issue:** https://github.com/bilalpiaic/Easy-Books/issues/140  
**Module id:** `weaving` · **Category:** Industry · **Deps:** `base`, `inventory`  
**v1:** Operational / memo unit control only — **no GL posting**.

## Green tabs (input)

| Screen | Key data |
|--------|----------|
| Setup / Master Data | Fabric qualities, looms, yarn types, shifts, operators; customers via existing Customer; sizing vendors via Vendor |
| Contracts + Rate/Costing | Contract meters, pick/inch, yarn rate/kg, fabric return price/m, weaving rate, expected shrinkage %, payment terms, status |
| Yarn Inward | Gross/tare/net kg (+ Lbs/Bags), yarn value, rate/kg |
| Sizing | Input/output kg (+ Lbs/Bags), gain/shrink %, sizing cost |
| Production | Warp/weft/total yarn used kg (+ Lbs/Bags), grey fabric m, efficiency %, weaving charges |
| Dispatch | Meters, dispatch value, weaving charges billed, net receivable |

## Yellow tabs (reports)

Daily Operations Dashboard · Contract Control Panel · Customer & Contract KPI · Weaving Dashboard (monthly trend)

## Conversion (single utility)

```
Lbs  = Kg × 2.2046226218
Bags = Lbs ÷ 100
Rate/Lb = Rate/Kg ÷ 2.2046226218
```

## Calc formulas (v1)

- **Net kg** = gross − tare  
- **Gain/shrink %** = `(output_kg − input_kg) / input_kg × 100` (positive = gain)  
- **Efficiency %** = `(grey_meters / contract_meters) × 100` when contract meters > 0, else 0 (per-entry override allowed)  
- **Dispatch value** = meters × fabric_return_price_per_meter (from contract) when not supplied  
- **Weaving charges billed** = meters × weaving_rate (from contract) when not supplied  
- **Net receivable** = dispatch_value − weaving_charges_billed (or explicit override)

## Acceptance

See issue #140 checklist — all items required for close.
