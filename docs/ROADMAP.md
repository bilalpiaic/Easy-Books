# Easy-Books — Development Roadmap

_Last reviewed: 2026-10-06. No open GitHub issues. `main` is through PR #411._

## Status summary

**Code is caught up.** v5, v6 growth A/B, entitlements/Studio (#370–#376), the SOTA speed pack (PRs #395–#397), Weighbridge (#391), UK MTD + Malaysia MyInvois (#306, PR #405), the Capacitor shell (#307, PR #407), and the SOC 2 evidence catalogue (#309, PR #406) are on `main`. GitHub has nothing left open.

**Remaining launch work is host configuration, not a branch.** Stripe live keys, S3 uploads, Neon point-in-time recovery, and `REQUIRE_OWNER_TOTP=true` / `ALLOW_DEMO_LOGIN=false` / `SEED_DEMO=false` on the Vercel backend. Checklist: [production launch plan](superpowers/plans/2026-09-06-production-launch.md). Do not reopen #307, #308 (declarative marketplace only), or #309.

**v6 Growth Track [#298](https://github.com/bilalpiaic/Easy-Books/issues/298):** A + B largely **landed on `main`** (PRs #323–#351). Do not treat the table below as a build queue until Wave 0 closes shipped issues. C (platforms/GTM) is now #369, not more modules.

**Complete:** **v5 Competitive Track** — [#254](https://github.com/bilalpiaic/Easy-Books/issues/254) (IFRS + tax packs + SaaS harden). All children #255–#271 shipped.

---

### A — Practice & money UX ([#298](https://github.com/bilalpiaic/Easy-Books/issues/298))

| Issue | Title | Status |
|-------|-------|--------|
| **#299** | Accountant practice depth — firm dashboard, onboarding, cross-client permissions | **Shipped** PR #324 — close on GitHub |
| **#300** | Multi-currency document/payment UX polish | **Shipped** PR #323 — close on GitHub |
| **#301** | Bank feeds — Open Banking / statement sync depth | **Shipped** PR #344 — close on GitHub |

### B — Vertical operations

| Issue | Title | Status |
|-------|-------|--------|
| **#302** | Multi-warehouse WMS — transfers, pick/pack, reservation | **Shipped** PRs #346 / #351 — close on GitHub |
| **#303** | Payroll depth — leave, expenses, statutory packs | **Shipped** leave PR #347 — close v1; statutory packs later |
| **#304** | POS module — counter sales → invoice/stock/cash | **Shipped** PR #345 — close on GitHub |
| **#305** | eCommerce connectors — Shopify / WooCommerce / Daraz | **Shipped** PR #350 — close v1 |

### C — Platforms & GTM

| Issue | Title | Status |
|-------|-------|--------|
| **#306** | Additional country localization packs | **Shipped** PR #405 — UK MTD + Malaysia MyInvois |
| **#307** | Native mobile shell (iOS/Android) on the PWA | **Shipped** PR #407 — Capacitor shell + push hook |
| **#308** | Marketplace partner code execution / signed extensions | **Wontfix** — declarative manifests + #376 bundles |
| **#309** | SOC 2–oriented evidence pack | **Shipped** PR #406 — controls map + admin ZIP; not a certification |
| **#370–#376** | Entitlements, catalog audience, Studio-lite | **Shipped** PRs #377–#383 |
| **#118** remainder | Require TOTP for `owner` + hide/block demo logins | **Shipped in code** — set `REQUIRE_OWNER_TOTP=true` and `ALLOW_DEMO_LOGIN=false` on production |
| **#390** | Self-service forgot-password from login | **Shipped** PR #393 |
| **#391** | First-party mill Weighbridge workspace | **Shipped** PR #400 — hub, tickets, first/second weigh, register; memo/ops, no extra GL |
| **Weighbridge** | Private mill Marketplace listing + Studio bundle | **Shipped** #384 listing, #387 mill visibility / Add-ons discovery |

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
