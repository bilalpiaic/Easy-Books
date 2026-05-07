# GEMINI.md — Easy-Books Project Context

This file provides the foundational context, architectural overview, and development guidelines for the Easy-Books project.

## Project Overview
**Easy-Books** is a specialized Financial Management System (FMS) designed for small to medium enterprises (specifically modeled for "Malik Enterprises"). It enables professional double-entry bookkeeping, transaction tracking (Revenue/Expense), and real-time generation of financial reports like Trial Balances and Income Statements.

### Key Technologies
The project follows a modern monorepo-style architecture with two primary stacks:

1.  **Modern Stack (Primary):**
    *   **Frontend:** Next.js 16 (React 19), TypeScript, Tailwind CSS, Lucide Icons.
    *   **Backend:** FastAPI (Python), SQLModel (SQLAlchemy + Pydantic), SQLite.
2.  **Legacy/Reference Stack:**
    *   **Backend:** Node.js, Express.js, better-sqlite3.
    *   **Frontend:** Static HTML, Vanilla JavaScript, CSS.

---

## Architecture & Structure

```text
/
├── backend/            # FastAPI Application (Modern Backend)
│   ├── main.py         # API entry point and routes
│   ├── models.py       # SQLModel database schemas
│   ├── db.py           # Database engine and seeding logic
│   └── database.db     # SQLite data store
├── frontend/           # Next.js Application (Modern Frontend)
│   ├── src/app/        # App Router pages and layouts
│   ├── src/components/ # Shared UI components (Sidebar, Header)
│   └── src/lib/        # Utilities and formatting helpers
├── public/             # Static HTML/JS Frontend (Legacy)
├── server.js           # Express.js Backend (Legacy)
└── db.js               # SQLite setup for legacy stack
```

---

## Building and Running

### 1. Modern Backend (FastAPI)
*   **Dependencies:** Uses `sqlmodel`, `fastapi`, and `uvicorn`.
*   **Setup:**
    ```bash
    cd backend
    python -m venv venv
    source venv/bin/activate  # or venv\Scripts\activate on Windows
    pip install -r requirements.txt  # or use 'uv sync' if uv is installed
    ```
*   **Run:**
    ```bash
    python main.py
    ```

### 2. Modern Frontend (Next.js)
*   **Setup:**
    ```bash
    cd frontend
    npm install
    ```
*   **Run (Development):**
    ```bash
    npm run dev
    ```

### 3. Legacy Stack (Express)
*   **Run:**
    ```bash
    npm install
    node server.js
    ```

---

## Development Conventions

### UI & UX (Malik Enterprises Brand)
*   **Theme:** Elegant, professional palette:
    *   Background: `#f6f3ee` (Cream)
    *   Primary/Accent: `#b8943f` (Gold)
    *   Text/Sidebar: `#1a1814` (Deep Charcoal)
*   **Typography:** Uses **DM Sans** for main UI and **DM Serif Display** for headings.
*   **Icons:** Use `lucide-react` for all iconography.

### Data Modeling (SQLModel)
*   All database models must inherit from `SQLModel`.
*   Maintain a strict separation between database tables (`table=True`) and API schemas (Read/Create models).
*   Double-entry consistency: All transactions must ensure that the sum of Debits equals the sum of Credits.

### API Standards
*   Endpoints are prefixed with `/api`.
*   Use `CORS` middleware to allow frontend communication (currently configured for all origins in development).
*   Follow RESTful principles for account management and transaction posting.

---

## TODO / Roadmap
- [ ] Implement remaining report pages in Next.js (General Journal, General Ledger, COA).
- [ ] Finalize the "New Entry" transaction form in the modern frontend.
- [ ] Add Balance Sheet and Cash Flow statement APIs.
- [ ] Implement user role-based access control (Owner, Accountant, Manager).
