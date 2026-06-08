> ⏳ **Historical working notes** (pre-v2.5.0 analysis). Many recommendations have since shipped. For current status see [`docs/ROADMAP.md`](./docs/ROADMAP.md).

# Copilot Improvement Plan

## Goal
Review the full codebase (backend + frontend + workflows) against prevailing accounting best practices and international standards, and benchmark feature parity against Odoo, QuickBooks, and Manager.io. Produce a prioritized remediation roadmap without implementing changes yet.

## Scope of Review
1. **Backend architecture & APIs**: FastAPI routers, services, GL posting rules, period close, reports, multi-tenancy, security controls.
2. **Data model**: financial entities, audit trail, accounting periods, tax, multi-currency, inventory, manufacturing, telecom.
3. **Frontend features**: accounting workflows, reports, settings, role-based gating, onboarding flows.
4. **Standards alignment**: IAS/IFRS coverage (IAS 1, IAS 2, IAS 8, IAS 16, IAS 21, IFRS 15, IFRS 9), auditability, data integrity.
5. **Product parity**: Odoo Accounting, QuickBooks Online, Manager.io.

## Plan of Work (No Implementation)
1. **Baseline inventory**
   - Compile API endpoint catalog and workflow map from backend routers and documentation.
   - Inventory frontend screens and features in App Router.
   - Build a feature matrix categorized by AR/AP, GL, Banking, Inventory, Reporting, Tax, Assets, Multi-currency, and Compliance.
2. **Standards mapping**
   - Map existing controls and workflows to IAS/IFRS and general bookkeeping best practices.
   - Capture evidence references (file/module/function or UI page).
3. **Gap analysis**
   - Identify missing or partial capabilities vs standards and reference products.
   - Rank gaps by compliance risk and operational impact (High/Medium/Low).
4. **Remediation roadmap**
   - Define epics per gap with required backend changes, frontend UX changes, and data impacts.
   - Document dependencies and suggested sequencing.
5. **Validation criteria**
   - Define acceptance checks and accounting scenarios for each remediation epic.
   - Outline reporting and audit-trail verification steps.

## Deliverables
1. **Compliance matrix**: IAS/IFRS requirement → current implementation → evidence → gap.
2. **Product parity matrix**: Odoo/QuickBooks/Manager.io feature → current coverage → gap.
3. **Prioritized backlog**: epics with scope, dependencies, and risk classification.
4. **Non‑implementation action list**: required design decisions and policy inputs.

## Open Inputs Needed
1. Target jurisdictions and tax regimes.
2. Required statutory reports beyond standard TB/PL/BS/CF.
3. Target parity level (basic, pro, enterprise).
4. Any mandated internal controls (approval chains, segregation of duties, audit standards).
