# Easy-Books — Development Roadmap

_Last reviewed: 2026-09-06 (forgot-password #390 on `main`; next: [SOTA implementation plan](superpowers/plans/2026-09-06-sota-implementation.md))._

## Status summary

**Active — production launch:** [Production plan](superpowers/plans/2026-09-06-production-launch.md) — Wave 1 **product** is on `main`. Remaining launch work is **ops secrets** (Stripe/S3/Neon PITR) and production env flags. **Engineering next:** [SOTA plan](superpowers/plans/2026-09-06-sota-implementation.md) — SQL hot paths, session bootstrap, then optional #391 Weighbridge workspace. Epic **[#369](https://github.com/bilalpiaic/Easy-Books/issues/369)** leftover is GTM/ops (children shipped).

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
| **#306** | Additional country localization packs | After entitlements (#370); not a launch blocker |
| **#307** | Native mobile shell (iOS/Android) on the PWA | **Defer** — PWA is enough for go-live |
| **#308** | Marketplace partner code execution / signed extensions | **Wontfix for production** — keep #227 declarative + #376 bundles |
| **#309** | SOC 2–oriented evidence pack | **Defer** until an enterprise RFP |
| **#370–#376** | Entitlements, catalog audience, Studio-lite | **Shipped** PRs #377–#383 |
| **#118** remainder | Require TOTP for `owner` + hide/block demo logins | **Shipped in code** — set `REQUIRE_OWNER_TOTP=true` and `ALLOW_DEMO_LOGIN=false` on production |
| **#390** | Self-service forgot-password from login | **Shipped** PR #393 |
| **#391** | First-party mill Weighbridge workspace | **Open** — after ops + SQL hot paths; see [SOTA plan](superpowers/plans/2026-09-06-sota-implementation.md) |
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
