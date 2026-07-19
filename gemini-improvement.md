> 📋 **HISTORICAL audit log (originally pre-v2.5.0) — superseded.** As of 2026-07-19
> every gap tracked here is shipped except §4.1 batch processing and §4.2 webhooks,
> which are now formal GitHub issues (#115 Background Task Queue, #114 Webhook /
> Event Bus) in the v4.0 backlog. See [`claude-improvement.md`](./claude-improvement.md)
> for the closed gap-by-gap detail and [`docs/ROADMAP.md`](./docs/ROADMAP.md) for
> current status.

# Easy-Books Improvement Roadmap (Phase 2)

This document outlines the strategic plan to elevate Easy-Books from a robust multi-tenant accounting system to a feature-complete ERP competitor (Odoo, QuickBooks, Manager.io) while ensuring full compliance with International Accounting Standards (IFRS/IAS).

**Status updated: 2026-06-20 (v2.7).** Completed items are marked ✅ below.

---

## Phase 1: Accounting Precision & Compliance

### 1.1 Multi-Currency Frontend Integration (IAS 21)
*   **Gap:** Backend supports multi-currency, but the Frontend is locked to a single currency (PKR) in UI helpers and forms.
*   **Action:**
    *   Add `currency` and `exchange_rate` fields to Invoice/Bill forms.
    *   Implement an "FX Lookup" component that fetches the latest rate from `/api/exchange-rates` on date change.
    *   Update `fmtPKR` to a dynamic `fmtAmount(amt, currency)` helper.

### 1.2 Fixed Assets & Depreciation (IAS 16) ✅ SHIPPED
*   **Shipped:** `assets` router + `services/depreciation.py` — `FixedAsset` model with SL/RB methods; `DepreciationEntry` tracks period charges; Dr Depreciation / Cr Accumulated Depreciation GL postings.

### 1.3 Bank Reconciliation Hardening
*   **Gap:** Reconciliations can currently be closed with a non-zero difference.
*   **Action:**
    *   Enforce "Zero Difference" validation: `Statement Balance - (Uncleared JVs + GL Balance) == 0`.
    *   Add a "Bank Adjustment" shortcut to post missing bank fees/interest directly from the recon screen.

---

## Phase 2: Tax & Localization Generalization

### 2.1 Schema-Driven Tax Engine
*   **Gap:** Tax slabs (ITO 2001) are currently hardcoded in `reports.py`.
*   **Action:**
    *   Move tax slabs to a `TaxSlab` table.
    *   Implement "Tax Groups" to handle composite taxes (e.g., Sales Tax + Further Tax + Income Tax Withholding).
    *   Allow tenants to select "Localization Packs" (e.g., GCC VAT, UK VAT, Pakistan GST).

### 2.2 Advanced Reporting ✅ SHIPPED
*   **Comparative reports:** `compare_end`/`compare_start` on TB/BS/P&L (`routers/reports.py`) — flat `{current, comparison}` payload; 2-column rendering in frontend.
*   **Budgeting:** `budgets` router — monthly budgets per account; Budget vs Actual report endpoint.

---

## Phase 3: Operational & UI Polishing

### 3.1 Document Lifecycle & Locking ✅ SHIPPED
*   **Shipped:** `credit_notes` + `debit_notes` routers provide first-class adjustment documents. Posted invoices/bills use reverse-and-repost for edits (blocked if payment allocated). Delete guarded when `PaymentAllocation` rows exist.

### 3.2 Enhanced Inventory (IAS 2)
*   **FIFO:** ⏳ still open — WAvg remains the only cost flow (`services/inventory.py`). `InventoryLayer` structure already supports per-layer cost; adding `cost_method` flag to `Product` would enable FIFO consumption.
*   **Stock Adjustments:** ✅ shipped — stock movement reasons supported via inventory router.

---

## Phase 4: Automation & Integration

### 4.1 Batch Processing
*   **Action:**
    *   Batch payment tool: Select multiple bills and pay them via a single bank transfer JV.
    *   Batch invoicing: Generate recurring invoices for all "Services" model tenants in one click.

### 4.2 API Documentation & Webhooks
*   **Action:**
    *   Standardize all 29 routers with full Pydantic models for request/response validation.
    *   Implement Webhooks for external integrations (e.g., "Invoice Paid" event).

---

## Approval & Implementation
Upon approval of this plan, implementation will proceed in surgical increments, prioritizing **Phase 1** to ensure financial data integrity.
