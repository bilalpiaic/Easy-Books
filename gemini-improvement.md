# Easy-Books Improvement Roadmap (Phase 2)

This document outlines the strategic plan to elevate Easy-Books from a robust multi-tenant accounting system to a feature-complete ERP competitor (Odoo, QuickBooks, Manager.io) while ensuring full compliance with International Accounting Standards (IFRS/IAS).

---

## Phase 1: Accounting Precision & Compliance

### 1.1 Multi-Currency Frontend Integration (IAS 21)
*   **Gap:** Backend supports multi-currency, but the Frontend is locked to a single currency (PKR) in UI helpers and forms.
*   **Action:**
    *   Add `currency` and `exchange_rate` fields to Invoice/Bill forms.
    *   Implement an "FX Lookup" component that fetches the latest rate from `/api/exchange-rates` on date change.
    *   Update `fmtPKR` to a dynamic `fmtAmount(amt, currency)` helper.

### 1.2 Fixed Assets & Depreciation (IAS 16)
*   **Gap:** No automated handling of long-term assets.
*   **Action:**
    *   **New Models:** `AssetAccount`, `AssetDepreciationSchedule`.
    *   **Feature:** Automated monthly depreciation posting (Straight-line / Reducing Balance).
    *   **Feature:** Asset registry with acquisition cost, salvage value, and accumulated depreciation tracking.

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

### 2.2 Advanced Reporting
*   **Gap:** Reports are single-period only.
*   **Action:**
    *   **Comparative Reports:** 2-column P&L/Balance Sheet (Current vs. Prior Period).
    *   **Budgeting:** Allow tenants to set monthly budgets per Expense account and report on "Budget vs. Actual".

---

## Phase 3: Operational & UI Polishing

### 3.1 Document Lifecycle & Locking
*   **Gap:** Invoices can be edited after being "Sent" or "Partially Paid".
*   **Action:**
    *   Implement a "Locked" state for documents that have GL impact.
    *   Use a "Credit Note" / "Debit Note" workflow for adjustments to posted documents instead of direct editing.

### 3.2 Enhanced Inventory (IAS 2)
*   **Gap:** Weighted-average is the only cost flow.
*   **Action:**
    *   Implement optional **FIFO (First-In-First-Out)** cost flow toggle.
    *   Add "Stock Adjustments" with reason codes (Damage, Shrinkage, Initial Upload).

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
