# Easy-Books (EBFMS)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a specialized Financial Management System (FMS) designed for small to medium enterprises. It enables professional double-entry bookkeeping, transaction tracking, and real-time generation of financial reports.

## ✨ Features

- **Double-Entry Bookkeeping**: Ensures financial integrity with strict debit/credit balance validation.
- **Modern Dashboard**: Real-time overview of financial health with elegant data visualization.
- **Comprehensive Reporting**: Generate Trial Balances, Income Statements, Balance Sheets, Cash Flow, and Tax Summaries.
- **Multi-Tenant SaaS**: Self-service signup creates an isolated tenant with auto-seeded Chart of Accounts.
- **JWT Auth**: Email/password login with tenant-scoped JWT bearer tokens.
- **CSV Bulk Import**: Onboard existing books for transactions, accounts, customers, vendors, and products.
- **Dual Stack Architecture**: Modern (FastAPI/Next.js) and Legacy (Node.js/Static HTML) implementations.

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **npm** or **yarn**

### 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bilalpiaic/Easy-Books.git
   cd Easy-Books
   ```

2. **Setup Modern Backend (FastAPI):**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env       # then edit secrets — see Authentication below
   python main.py             # runs uvicorn on :8000
   ```

3. **Setup Modern Frontend (Next.js):**
   ```bash
   cd ../frontend
   npm install
   npm run dev                # serves on :3000
   ```

### 🔐 Authentication

Two ways to get an account:

- **Self-service signup (recommended):** open `http://localhost:3000/signup`, fill in name, company, email, password — a new tenant is created with a default Chart of Accounts, then you're logged in automatically.
- **Seeded admin (optional):** set `SEED_ADMIN_EMAIL` and `SEED_ADMIN_PASSWORD` in `backend/.env` before first start; the admin user is created on the first tenant during `create_db_and_tables()`.

Tokens are JWT bearer tokens with `{sub, tenant_id, full_name}` and stored in `localStorage`. CORS is locked to `FRONTEND_ORIGIN` (default `http://localhost:3000`).

## 🏗️ Architecture

The project follows a monorepo structure with two primary stacks:

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | Next.js 16 (React 19), TypeScript, Tailwind CSS | Modern, responsive interface using App Router. |
| **Backend** | FastAPI, SQLModel (Pydantic + SQLAlchemy) | High-performance Python API with SQLite. |
| **Legacy** | Node.js, Express, Vanilla JS | Reference implementation for system validation. |

## 🎨 Design Philosophy

Easy-Books uses the **Malik Enterprises** brand palette:
- **Cream** (`#f6f3ee`) for background comfort.
- **Gold** (`#b8943f`) for professional accents.
- **Deep Charcoal** (`#1a1814`) for high-contrast typography.

## 🛠️ Tech Stack

- **Frameworks**: Next.js, FastAPI
- **Database**: SQLite (SQLModel)
- **Styling**: Tailwind CSS
- **Icons**: Lucide React

---

## 📚 Further Reading

- [`WORKFLOW.md`](./WORKFLOW.md) — full accounting workflow, GL posting rules, report-linking matrix, and API catalog.
- [`DEPLOYMENT.md`](./DEPLOYMENT.md) — Vercel deployment for backend + frontend, environment variables, seed admin setup.

> [!NOTE]
> Branch `saas-transition-foundation` carries the active SaaS work (multi-tenant auth, signup, dashboard charts, CSV import). Roadmap items (hierarchical CoA, multi-currency, recurring docs, PDF/email) are tracked in `WORKFLOW.md §13`.
