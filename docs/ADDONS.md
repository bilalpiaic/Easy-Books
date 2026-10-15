# Easy-Books Add-ons — grouped by category of use

System → **Add-ons** (`/apps`) is the module store (admin/owner). Public signup starts with **Base Accounting** only. Everything else is installed here.

Recommended packs, Optional modules, and Marketplace listings are grouped by **how you use them**, not by when they shipped.

| Band | What it is | Module IDs |
|------|------------|------------|
| **Core** | Always-on ledger | `base` |
| **Operations** | Horizontal capabilities used across industries | `inventory`, `production`, `purchase_store`, `pos`, `ecommerce`, `weighbridge`, `shop_floor` |
| **HR & Payroll** | People and pay | `hrm` |
| **Business nature** (Industry) | Full verticals | `telecom`, `healthcare`, `weaving`, `spinning`, `textile_processing` |
| **Country & statutory** (Localization) | Tax / e-invoice by jurisdiction | `pra`, `uae_vat`, `sa_zatca`, `in_gst`, `eu_peppol`, `uk_mtd`, `my_invois` |
| **Intelligence** | Ask the books | `ai_assistant` |

A mill, hospital, or trader pack does **not** include a tax jurisdiction. Install a country pack beside any business nature. Pakistan **FBR Digital Invoicing** (historic key `pra`) lives with the other country packs — not under Industry.

Source of truth: `MODULE_REGISTRY` in `backend/db.py` (`category` field) and `ADDON_PACKS` / `MODULE_CATEGORY_ORDER` in `frontend/src/lib/addonPacks.ts`.

---

## Tabs

| Tab | Shows |
|-----|--------|
| **Default** | Base Accounting (cannot uninstall) |
| **Recommended** | One-click packs in three bands: Business nature · Country & statutory · Intelligence |
| **Optional** | Individual modules, same bands (plus Operations and HR) |
| **Marketplace** | Curated products (declarative manifests; no partner code), grouped by category |

`CATEGORY_ORDER` is an **allowlist**. A module whose `MODULE_REGISTRY.category` is missing from that list never gets a card (it still counts in “N of M installed”).

---

## Business nature packs (Recommended)

| Pack | Modules | Demo |
|------|---------|------|
| Trader | `inventory`, `pos` | `demo.trader@easy-books.app` |
| Manufacturing | `inventory`, `production`, `purchase_store`, `weaving`, `weighbridge`, `shop_floor` | `demo.manufacturing@easy-books.app` |
| Yarn Spinning | `inventory`, `purchase_store`, `spinning`, `weighbridge`, `shop_floor` | `demo.spinning@easy-books.app` |
| Textile Processing | `inventory`, `purchase_store`, `textile_processing`, `weighbridge`, `shop_floor` | `demo.processing@easy-books.app` |
| Healthcare | `hrm`, `inventory`, `healthcare` | `demo.hospital@easy-books.app` |
| Telecom Franchise | `inventory`, `telecom` | `demo.telecom@easy-books.app` |

Password for every demo: `demo1234`.

---

## Country & statutory packs (Recommended)

| Pack | Module | Jurisdiction | Typical demo seed |
|------|--------|--------------|-------------------|
| FBR Digital Invoicing | `pra` (+ `inventory`, `pos` in the pack) | Pakistan | `demo.pra@easy-books.app` |
| UAE VAT e-Invoice | `uae_vat` | UAE | simple tenant |
| Saudi ZATCA e-Invoice | `sa_zatca` | KSA | manufacturing |
| India GST | `in_gst` | India | trader |
| Peppol / EU VAT | `eu_peppol` | EU | services |
| UK MTD VAT | `uk_mtd` | United Kingdom | hospital |
| Malaysia MyInvois | `my_invois` | Malaysia | processing |

Each pack adds a dashboard + submission log. They **never rewrite** a posted journal line. Failures retry; the voucher stays posted.

Withholding tax and the CIT worksheet are **core accounting** (vendor WHT flags + Reports → CIT), not a country pack.

---

## Operations modules (Optional)

| Module | What it enables |
|--------|-----------------|
| Inventory | Products, categories, stock card, product ledger, performance |
| Manufacturing (`production`) | BoM, production orders, GRN, job-costing |
| Purchases & Store | Demand → quotation → comparative → PO → gate inward / outward → store issue |
| Point of Sale | Shift, register, cash-up; same GL as invoices |
| eCommerce Connectors | Shopify / WooCommerce → draft invoices |
| Weighbridge | Ticket desk (memo/ops, no GL). Pre-installed on mill models; also a dep of Weaving / Spinning / Textile Processing. Public Marketplace overlay (Gate pass + Lot ref on invoices) |
| PLC Shop Floor (`shop_floor`) | Mill gateway POSTs loom/frame/scale readings to `/api/plc/ingest`. Install from Add-ons (Optional, or mill Recommended packs). UI `/shop-floor`. Easy-Books never opens Modbus/OPC-UA. |

---

## Intelligence

**AI Financial Assistant** (`ai_assistant`, Pro): chat FAB + `/agent` + forecasts. Multi-provider (Anthropic / OpenAI / Gemini / Ollama). Read-only tools against live reports.

---

## How this maps to `business_model`

`Tenant.business_model` seeds the Chart of Accounts once (structural). `MODULES_BY_MODEL` only **pre-selects** modules at signup:

```
simple / services     → base
trader                → base, inventory, pos
manufacturing         → base, inventory, production, purchase_store, weaving, weighbridge, shop_floor
telecom_franchise     → base, inventory, telecom
pra_einvoice          → base, pra
hospital              → base, hrm, inventory, healthcare
yarn_spinning         → base, inventory, purchase_store, spinning, weighbridge, shop_floor
textile_processing    → base, inventory, purchase_store, textile_processing, weighbridge, shop_floor
```

After signup the user manages modules independently. Localization demos may also enable a country pack on selected tenants.

---

## Related

- User Guide §29 — how to install
- User Guide §28–28g — country pack how-tos
- [`MARKETPLACE.md`](./MARKETPLACE.md) — sandbox rules
- In-app Catalog (`/settings/catalog`) and `/apps`
