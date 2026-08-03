# Spec: Yarn Spinning Module (#319)

**Pull request:** https://github.com/bilalpiaic/Easy-Books/pull/319  
**Module id:** `spinning` · **Category:** Industry · **Deps:** `base`, `inventory`, `purchase_store`  
**Business model:** `yarn_spinning` · **GL:** Full from day 1 via `services/spinning_posting.py`

## Green tabs (input)

| Screen | Key data |
|--------|----------|
| Setup / Master Data | Yarn specs (Ne/Nm, blend %), fiber grades, machines, shifts, operators, waste types (GL 5901–5904), blend recipes |
| Production Plans | PP-YYYY-seq; monthly targets by yarn spec; approve to lock |
| Spin Lots | SL-YYYY-seq; draft→started→completed→closed; live cost-per-kg |
| Bale Receipt | BR-YYYY-seq; gross/tare/net kg; optional PO/gate-inward/bill link; approve posts Dr 1200 / Cr AP or Cash |
| Stage Entries | opening→carding→drawing→roving→spinning→winding; WIP transfers 1201/1202/1203; labour→5100, overhead→5200 |
| Cone Output | CO-YYYY-seq; approve transfers WIP→FG (1204) |
| Waste Log | posts to 5901–5904 and relieves WIP |
| Yarn Dispatch | YD-YYYY-seq; approve posts COGS (Dr 5010 / Cr 1204) |

## Yellow tabs (reports)

Spinning Dashboard · Daily Register · Lot Control · Waste Summary · Cost-per-kg · Dispatch Register · Yield/Blend/Spindle Calculators

## Conversion (single utility)

```
Lbs  = Kg × 2.2046226218
Bags = Lbs ÷ 100
Ne ↔ Nm yarn count conversion
```

## GL accounts (yarn_spinning CoA extras)

| Code | Name |
|------|------|
| 1200 | Raw Cotton / Fiber Inventory |
| 1201 | WIP — Opening & Carding |
| 1202 | WIP — Drawing & Roving |
| 1203 | WIP — Ring Spinning |
| 1204 | Finished Yarn Inventory |
| 5100 | Direct Labour |
| 5200 | Manufacturing Overhead |
| 5010 | Cost of Goods Sold |
| 5901–5904 | Waste expense accounts |

## Stock locations

`RAW`, `WIP-CARD`, `WIP-DRAW`, `WIP-SPIN`, `FG-YARN` — auto-created by `ensure_spinning_locations()`.

## Demo tenant

`demo.spinning@easy-books.app` / `demo1234` — pre-loaded masters, lots, bale receipts, stages, cones, waste, dispatches.

## Acceptance

- Full GL on bale receipt approve, stage post, cone approve, waste post, dispatch approve
- Lot cost-per-kg accumulates material + labour + overhead + waste
- Standalone from Weaving module (no dependency)
- AI spinning agent with dashboard/daily/lot-control tools
- 15 frontend pages under `/spinning/`

