# Easy-Books — Development Roadmap

_Last reviewed: 2026-08-04 (v6 epic opened; v5 #254 closed complete)._

## Status summary

**Active:** **v6 Growth Track** — umbrella [#298](https://github.com/bilalpiaic/Easy-Books/issues/298):
practice/money UX (A) + vertical ops (B) + platforms/GTM (C).

**Complete:** **v5 Competitive Track** — [#254](https://github.com/bilalpiaic/Easy-Books/issues/254) (IFRS + tax packs + SaaS harden). All children #255–#271 shipped.

---

### A — Practice & money UX ([#298](https://github.com/bilalpiaic/Easy-Books/issues/298))

| Issue | Title | Status |
|-------|-------|--------|
| **#299** | Accountant practice depth — firm dashboard, onboarding, cross-client permissions | Open |
| **#300** | Multi-currency document/payment UX polish | Open |
| **#301** | Bank feeds — Open Banking / statement sync depth | Open |

### B — Vertical operations

| Issue | Title | Status |
|-------|-------|--------|
| **#302** | Multi-warehouse WMS — transfers, pick/pack, reservation | Open |
| **#303** | Payroll depth — leave, expenses, statutory packs | Open |
| **#304** | POS module — counter sales → invoice/stock/cash | Open |
| **#305** | eCommerce connectors — Shopify / WooCommerce / Daraz | Open |

### C — Platforms & GTM

| Issue | Title | Status |
|-------|-------|--------|
| **#306** | Additional country localization packs | Open |
| **#307** | Native mobile shell (iOS/Android) on the PWA | Open |
| **#308** | Marketplace partner code execution / signed extensions | Open |
| **#309** | SOC 2–oriented evidence pack | Open |

### Shipped foundations (not v6 — do not reopen)

Practice switcher v1 (#220), MRP depth (#221–#224), PWA (#226), marketplace manifests (#227), Playwright (#228), Storybook (#229), country packs (#264–#266) + WHT/CIT (#267), IFRS suite (#255–#262), SaaS harden (#268–#271).

---

## Shipped history (recent)

### v5.x — IFRS Track A + country packs + SaaS harden (2026-08)

| Feature | Detail |
|---------|--------|
| **Consolidation (#255)** | Holding entity graph, worksheet propose/post, IC/NCI elims, `/consolidation` |
| **Intercompany (#261)** | IC flag on invoice/bill, auto mirror draft, recon report `/intercompany/recon` |
| **IFRS 16 leases (#256)** | RoU + liability schedule, period post, maturity disclosure, `/leases` |
| **IFRS 15 remainder (#259)** | Relative-SSP multi-element allocation, contract assets (1140), `/contract-balances` |
| **Assets depth (#258)** | Componentization, impairment/reversal, disposal, rollforward `/assets/rollforward` |
| **Dimensions (#260)** | Up to 3 `AnalyticDimension`s, mandatory dims, dimensional P&L |
| **Inventory depth (#257)** | Landed cost, lot/serial, NRV valuation UI |
| **Close / audit pack (#262)** | Period checklist + auditor ZIP |
| **Tax engine (#263)** | Effective-dated `TaxRateHistory` |
| **Saudi ZATCA (#264)** | `sa_zatca` module — sandbox clear/report, TLV QR, submission logs |
| **India GST (#265)** | `in_gst` module — place of supply, CGST/SGST/IGST, GSTR-1/3B |
| **Peppol / EU VAT (#266)** | `eu_peppol` module — BIS Billing 3.0 UBL, AP submit, submission logs |
| **WHT + CIT (#267)** | Vendor withholding on bill payments (Cr 2265), CIT worksheet + adjustments |
| **SaaS harden (#268–#271)** | Bank feeds, approvals, portal, webhooks/DLQ/quotas |
| **Party closing + settings (#297)** | Customer/vendor list closing balances; decimal 0/2/4; more currencies |

### Older releases

See git history and prior sections in `BLUEPRINT.md` / `README.md` for v3.x–v4.x feature catalogs (search, auto-update, PRA, HRM, purchase/store, AI assistant, etc.).
