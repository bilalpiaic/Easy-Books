# Design Spec: Multi-Tenant SaaS Transition

**Date:** 2026-05-07  
**Status:** Draft  
**Topic:** Transitioning Easy-Books from a single-tenant prototype to a multi-tenant SaaS platform.

## 1. Overview
The goal is to transform the "Malik Enterprises" prototype into a production-ready SaaS (Software as a Service) platform where multiple organizations (tenants) can manage their finances independently on a shared infrastructure.

## 2. Architecture: Shared Database (Approach A)
We will use a shared SQLite database (transitioning to PostgreSQL for production) where every table is scoped by a `tenant_id`.

### 2.1 Data Model Changes
We will introduce new core models and update existing ones:

#### New Models:
*   **Tenant:** `id`, `name`, `slug`, `created_at`.
*   **User:** `id`, `tenant_id`, `email`, `hashed_password`, `full_name`, `role` (Admin, Accountant, Viewer).

#### Updated Models (Adding `tenant_id`):
*   **Account:** `id`, `tenant_id`, `code`, `name`, `type`.
*   **Transaction:** `id`, `tenant_id`, `jv_number`, `date`, `description`, etc.
*   **JournalEntry:** `id`, `tenant_id`, `transaction_id`, `account_id`, `debit`, `credit`.
*   **Settings:** `id`, `tenant_id`, `key`, `value`.

### 2.2 Tenant Isolation Logic
*   **Global Filter:** In the FastAPI backend, we will use a dependency-injected session that automatically adds `.where(Model.tenant_id == current_tenant_id)` to all queries.
*   **Consistency:** The `tenant_id` will be enforced at the API layer using JWT claims.

## 3. Security & Authentication
*   **Auth Provider:** Custom JWT implementation using `passlib` (bcrypt) and `python-jose`.
*   **Token Payload:** `{ "sub": user_id, "tenant_id": tenant_id, "role": role, "exp": ... }`.
*   **Frontend Storage:** Secure `localStorage` for the prototype, transitioning to `HttpOnly` cookies for production.

## 4. Multi-Tenant Workflows

### 4.1 Onboarding
1.  User submits sign-up form (Email, Company Name, Password).
2.  Backend creates a new `Tenant` record.
3.  Backend creates the `User` and links it to the `Tenant`.
4.  **Auto-Seeding:** The backend automatically inserts a default "Chart of Accounts" for the new `tenant_id`.

### 4.2 Dashboard & Reports
All existing reports (Trial Balance, P&L, etc.) will be updated to respect the `tenant_id` filter.

## 5. UI/UX Adjustments
*   **Branding:** Replace hardcoded "Malik Enterprises" with the `Tenant.name` from the logged-in user's context.
*   **Onboarding UI:** Add Login and Sign-up pages.
*   **Sidebar:** Update user profile section to show the logged-in user's name and company.

## 6. Implementation Phases
1.  **Phase 1 (Core):** Implement Tenant/User models and JWT Auth.
2.  **Phase 2 (Migration):** Add `tenant_id` to all existing tables and update backend dependencies.
3.  **Phase 3 (Frontend):** Build Login/Sign-up and update UI to be dynamic.
4.  **Phase 4 (Reporting):** Update all report queries to be tenant-aware.

## 7. Success Criteria
*   A user can sign up and get a fresh, empty FMS setup.
*   Data entered by User A (Tenant A) is never visible to User B (Tenant B).
*   The system handles multiple "Malik Enterprises"-like setups simultaneously.
