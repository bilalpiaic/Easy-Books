# Easy-Books — Development Roadmap

_Last reviewed: 2026-08-03 (against `main` @ merge of PR #280 / epic #254 Track A progress)._

## Status summary

**v5 Competitive Track** is tracked under umbrella issue [#254](https://github.com/bilalpiaic/Easy-Books/issues/254):
IFRS-ready books (A) + country tax packs (B) + SaaS harden (C).

### A — IFRS accounting ([#254](https://github.com/bilalpiaic/Easy-Books/issues/254))

| Issue | Title | Status |
|-------|-------|--------|
| **#255** | Multi-entity consolidation (IFRS 10 / IAS 27) | Shipped (PR #279) |
| **#256** | IFRS 16 leases (RoU + liability) | Shipped (PR #280) |
| **#257** | Inventory depth — landed cost, lot/serial, NRV | Shipped |
| **#258** | Fixed assets depth — IAS 16/36 | Shipped |
| **#259** | IFRS 15 remaining — multi-element + contract assets | Shipped |
| **#260** | Analytic dimensions on all JE lines + dimensional P&L | Open |
| **#261** | Intercompany + IC reconciliation | Open |
| **#262** | Month-end close checklist + auditor export pack | Shipped |

### B — Country tax packs

| Issue | Title | Status |
|-------|-------|--------|
| **#263** | Core multi-jurisdiction tax engine | Shipped |
| **#264** | Country pack: Saudi ZATCA e-invoice | Open |
| **#265** | Country pack: India GST | Open |
| **#266** | Country pack: Peppol / EU VAT e-invoice | Open |
| **#267** | Withholding tax + corporate tax summary reports | Open |

### C — SaaS hardening

| Issue | Title | Status |
|-------|-------|--------|
| **#268** | Bank feeds hardening | Shipped |
| **#269** | Approvals SoD + thresholds + substitutes | Shipped |
| **#270** | Portal hardening (pay, disputes, branded domain) | Shipped |
| **#271** | Integration ops — webhooks, queue DLQ, plan quotas | Shipped |

### Earlier v4 backlog (mostly superseded / partially shipped)

Many items from the old v4 Cloud Launch list (#114–#125, #140) have landed under Track C or as modules (webhooks, queue, portal, approvals, bank feeds, weaving). Prefer epic **#254** as the live tracker; close or retarget leftover v4 issues when overlapping work ships.

---

## Shipped history (recent)

### v5.x — IFRS Track A + SaaS harden (2026-08)

| Feature | Detail |
|---------|--------|
| **Consolidation (#255)** | Holding entity graph, worksheet propose/post, IC/NCI elims, `/consolidation` |
| **IFRS 16 leases (#256)** | RoU + liability schedule, period post, maturity disclosure, `/leases` |
| **Inventory depth (#257)** | Landed cost, lot/serial, NRV valuation UI |
| **Close / audit pack (#262)** | Period checklist + auditor ZIP |
| **Tax engine (#263)** | Effective-dated `TaxRateHistory` |
| **SaaS harden (#268–#271)** | Bank feeds, approvals, portal, webhooks/DLQ/quotas |

### Older releases

See git history and prior sections in `BLUEPRINT.md` / `README.md` for v3.x–v4.x feature catalogs (search, auto-update, PRA, HRM, purchase/store, AI assistant, etc.).
