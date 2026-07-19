# Weaving

**Labels:** `enhancement`, `new-module`, `weaving`
**Suggested assignee:** @BilalPiaic

## Summary
Add a new **Weaving** add-on module to Easy Books, modeled on the attached `Weaving_unit_control_template (version 1).xlsx`. Screens should mirror the template's tab structure:

- 🟩 **Green tabs → Input / data-entry screens**
- 🟨 **Yellow tabs → Report / dashboard screens (read-only, auto-computed)**

---

## Input Screens (from GREEN tabs)

| Screen | Source Sheet | Key Fields |
|---|---|---|
| Setup / Master Data | `Master_Data` | Customers, Fabric Qualities, Looms, Yarn Types, Sizing Vendors, Shifts, Operators |
| Contracts | `Contracts` | Contract ID, Customer, dates, fabric quality, yarn type, contract meters, pick/inch, assumed yarn rate/kg, fabric return price/meter, weaving rate, expected shrinkage %, payment terms, status |
| Rate & Costing | `Rate_Costing` | Contract pricing assumptions, expected weaving revenue |
| Yarn Inward | `Yarn_Inward` | Gross/Tare/Net Kg (+ auto Lbs & 100-lb Bags), yarn value |
| Sizing | `Sizing` | Input/Output Kg (+ auto Lbs & Bags), gain/shrink %, sizing cost |
| Production | `Production` | Warp/Weft/Total Yarn Used Kg (+ auto Lbs & Bags), grey fabric produced, efficiency %, weaving charges |
| Dispatch | `Dispatch` | Meters dispatched, dispatch value, weaving charges billed, net receivable |

## Report / Dashboard Screens (from YELLOW tabs)

| Screen | Source Sheet | Purpose |
|---|---|---|
| Daily Operations Dashboard | `Daily Operations Dashboard` | Date-range filterable activity feed + KPI tiles (yarn received/sized, fabric produced/delivered, efficiency, weaving charges, net receivable) + shift/operator/loom efficiency breakdowns |
| Contract Control Panel | `Contract Control Panel` | Single-contract drill-down: timeline/progress, yarn quantities (Kg/Lbs/Bags), finished/sizing stock, full date-wise activity history |
| Customer & Contract KPI | `Customer & Contract KPI` | Portfolio KPIs (total/in-process/completed/delayed contracts, value) + per-contract grid (received/used/balance yarn, value) |
| Weaving Dashboard | `Dashboard` | Top-level KPIs (yarn received/used/balance, sizing output, production, dispatch, weaving revenue, efficiency), monthly trend chart, contract/order status summary |

---

## Requirement: Kg → Lbs conversion everywhere yarn weight appears

The template's own `Read_me` tab states the intended design: every yarn quantity should be shown in **Kg, Lbs, and 100-lb Bags**, using:

```
Lbs  = Kg × 2.2046226218
Bags = Lbs ÷ 100
```

This is already implemented as a formula on most input tables (`Yarn_Inward`, `Sizing`, `Production`), but is **missing on some report-tab KPI tiles** and on the **yarn rate field**. The module should close both gaps:

1. **Derived field, not user input** — implement Kg→Lbs→Bags as a shared conversion utility applied wherever a yarn weight is entered or displayed (don't duplicate the formula per screen).
2. **Extend Lbs/Bags display to report tiles that currently show Kg only:**
   - Daily Operations Dashboard: "Yarn Received Kg" / "Yarn Sized Kg" KPI tiles + activity list columns
   - Contract Control Panel: "Yarn Received Kg" / "Yarn Sized Kg" activity columns
   - Customer & Contract KPI: "Yarn Received Kg", "Yarn Used Kg", "Yarn Balance Kg" tiles + per-contract grid columns
   - *(The `Dashboard` tab already does this correctly for Total Yarn Received/Used/Balance — use it as the reference pattern.)*
3. **Add "Assumed Yarn Rate / Lb"** alongside the existing "Assumed Yarn Rate/Kg" in `Contracts`, `Rate_Costing`, and `Yarn_Inward` — currently rate is Kg-only everywhere.
4. UI should present weight fields the same way the template does: **Kg | Lbs | Bags (100 lb)** shown together, not as a single unit.

---

## Acceptance Criteria
- [ ] New "Weaving" section added to Easy Books navigation
- [ ] Setup screen for Master Data (customers, fabric qualities, looms, yarn types, sizing vendors, shifts, operators)
- [ ] Contract entry screen linked to Rate/Costing fields
- [ ] Yarn Inward entry with auto Kg→Lbs→Bags conversion
- [ ] Sizing entry with auto Kg→Lbs→Bags conversion + gain/shrink %
- [ ] Production entry with auto Kg→Lbs→Bags conversion + efficiency % + weaving charges
- [ ] Dispatch entry with auto dispatch value / net receivable calc
- [ ] Daily Operations Dashboard report with Kg+Lbs KPI tiles
- [ ] Contract Control Panel report with Kg+Lbs+Bags quantities
- [ ] Customer & Contract KPI report with Kg+Lbs portfolio KPIs
- [ ] Weaving Dashboard with Kg+Lbs+Bags summary + monthly trend chart
- [ ] Kg→Lbs conversion (`× 2.2046226218`) implemented as one shared utility, not duplicated per screen
- [ ] "Assumed Yarn Rate/Lb" derived field added wherever Rate/Kg is shown

## Reference
- Source template: `Weaving_unit_control_template (version 1).xlsx` (attached to this issue)
- Sheet color legend: 🟩 Green = input/data entry · 🟨 Yellow = report/dashboard (read-only, auto-calculated)
