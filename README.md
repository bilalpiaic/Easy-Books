# Easy-Books (EBFMS)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Easy-Books** is a specialized Financial Management System (FMS) designed for small to medium enterprises. It enables professional double-entry bookkeeping, transaction tracking, and real-time generation of financial reports.

## ✨ Features

- **Double-Entry Bookkeeping**: Ensures financial integrity with strict debit/credit balance validation.
- **Modern Dashboard**: Real-time overview of financial health with elegant data visualization.
- **Comprehensive Reporting**: Generate Trial Balances, Income Statements, and Balance Sheets.
- **SaaS Ready**: Currently transitioning to a multi-tenant architecture for scalable business management.
- **Dual Stack Architecture**: Modern (FastAPI/Next.js) and Legacy (Node.js/Static HTML) implementations.

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **npm** or **yarn**

### 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bilalpiaic/ebfms.git
   cd ebfms
   ```

2. **Setup Modern Backend (FastAPI):**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python main.py
   ```

3. **Setup Modern Frontend (Next.js):**
   ```bash
   cd ../frontend
   npm install
   npm run dev
   ```

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

> [!NOTE]
> This project is currently in active transition to a SaaS foundation. Some reporting modules are still under development in the modern stack.
