# Easy-Books: Copilot Development Guidelines

This document provides essential context for AI-assisted development in the Easy-Books Financial Management System (FMS).

## Project Overview

**Easy-Books** is a dual-stack financial application implementing professional double-entry bookkeeping for small-to-medium enterprises. It enforces strict debit/credit balance validation and generates financial reports (Trial Balance, Income Statements, Balance Sheets).

The project uses a **monorepo structure with two parallel implementations**:
- **Modern Stack (Primary):** Next.js 16 (React 19) + FastAPI (Python)
- **Legacy Stack (Reference):** Express.js + Vanilla JavaScript

See [GEMINI.md](../GEMINI.md) for detailed architecture and conventions.

---

## Build, Run, and Test Commands

### Modern Backend (FastAPI, Python 3.11+)

**Setup:**
```bash
cd backend
uv sync  # or: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

**Run:**
```bash
cd backend
python main.py  # Starts on http://localhost:8000
```

**Tests:**
```bash
cd backend
uv run pytest              # Run all tests
uv run pytest -v          # Verbose output
uv run pytest tests/test_auth.py  # Single test file
uv run pytest -k test_name         # Run specific test
```

**Debugging:** Backend uses `httpx` and `playwright` (see `pyproject.toml` dev dependencies).

### Modern Frontend (Next.js 16, TypeScript)

**Setup:**
```bash
cd frontend
npm install
```

**Run:**
```bash
cd frontend
npm run dev  # Starts on http://localhost:3000
```

**Build:**
```bash
cd frontend
npm run build
npm start    # Production mode
```

**Lint:**
```bash
cd frontend
npm run lint  # ESLint (Next.js config)
```

**Important:** The frontend uses **Next.js 16 with breaking changes**—see `frontend/AGENTS.md` before writing code. Review `node_modules/next/dist/docs/` for API changes.

### Legacy Stack (Express + Node.js)

**Setup & Run:**
```bash
npm install
node server.js  # Runs backend and legacy frontend
```

---

## Architecture & Design Patterns

### Data Layer (SQLModel + SQLAlchemy)

**Model Structure:**
- **Database Models** inherit from `SQLModel` with `table=True`
- **API Models** separate Create/Read schemas from table definitions
- All multi-tenant models include `tenant_id` field with foreign key to `Tenant`

**Key Constraint:** Double-entry bookkeeping requires **debit sum = credit sum** for every transaction. Validation happens:
1. At model definition level (separate debit/credit fields)
2. In transaction posting endpoints (sum validation before commit)

**Example Pattern:**
```python
class JournalEntry(JournalEntryBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    debit: float = Field(default=0.0)
    credit: float = Field(default=0.0)
    # Always post both, but exactly one must be > 0
```

### Backend API Standards

- **All endpoints** prefixed with `/api`
- **Authentication:** JWT tokens via `OAuth2PasswordBearer` (see `backend/auth.py`)
- **CORS:** Configured for all origins in development
- **Session Dependency:** Use `SessionDep = Annotated[Session, Depends(get_session)]` for database access
- **Current User:** Use `CurrentUserDep = Annotated[User, Depends(get_current_user)]` to enforce authentication

### Frontend Conventions

**Theme (Malik Enterprises Brand):**
- Background: `#f6f3ee` (Cream)
- Primary/Accent: `#b8943f` (Gold)
- Text/Sidebar: `#1a1814` (Deep Charcoal)

**UI Elements:**
- Icons: **lucide-react** only (consistent iconography)
- Typography: **DM Sans** for UI, **DM Serif Display** for headings (defined in Tailwind CSS)
- Styling: **Tailwind CSS** with `tailwind-merge` for conditional class merging
- Layout: Next.js App Router with `(dashboard)` route group for authenticated pages

**Components Location:**
- Shared UI: `src/components/` (Sidebar, Header)
- Pages: `src/app/` (route-based organization)
- Utilities: `src/lib/` (formatting, auth helpers)

### Multi-Tenancy

- Every data model (Account, Transaction, JournalEntry, Settings) includes `tenant_id` field
- Unique constraints are typically tenant-scoped (e.g., `UniqueConstraint("tenant_id", "code")`)
- JWT payload includes both `sub` (email) and `tenant_id` for tenant isolation

---

## Key Development Notes

### Database Initialization

- `backend/db.py` creates engine and seeding logic
- Default tenant "Malik Enterprises" is created if missing during startup
- Database file: `backend/database.db` (SQLite)
- Use `uv run pytest` to test against fresh database state (if tests don't mutate production DB)

### Common Task Patterns

**Adding a New Account Type:**
1. Add account type string to `Account.type` field documentation or enum if introduced
2. Update seeding in `db.py` if providing defaults for new type
3. Add corresponding report calculations in backend endpoints

**Creating a New Report:**
1. Add FastAPI endpoint in `backend/main.py` (or new router file when directory exists)
2. Query using SQLModel `select()` with appropriate filters and joins
3. Create Next.js page in `frontend/src/app/(dashboard)/[report-name]/page.tsx`
4. Use chart libraries (`react-chartjs-2`) for visualizations

**Posting a Transaction:**
1. Validate debit sum = credit sum in request payload
2. Create `Transaction` record with unique `jv_number` per tenant
3. Create linked `JournalEntry` records (one per account line)
4. Both table constraints and API logic enforce this invariant

### Testing

- Backend tests use **pytest** with `httpx` for API testing
- Tests are located in `backend/tests/`
- Always create separate Create and Read Pydantic models to avoid over-exposing internal fields
- Test file naming: `test_*.py` (pytest convention)

---

## Important Constraints & Gotchas

1. **Tenant Isolation:** Never query accounts/transactions without filtering by `tenant_id`
2. **Debit/Credit Balance:** Always validate that total debits = total credits before posting
3. **JWT Token Payload:** Must include both `email` (sub) and `tenant_id` for authentication to work
4. **CORS Policy:** Currently permissive in development; tighten before production
5. **Next.js 16 Breaking Changes:** Frontend documentation notes API changes from standard React—check `node_modules/next/dist/docs/` before assuming standard behavior
6. **Unique Constraints:** Account codes and JV numbers are unique per tenant, not globally

---

## File Organization

```
backend/
  main.py              ← API endpoints and dependency injection
  models.py            ← SQLModel definitions
  db.py                ← Database engine and seeding
  auth.py              ← JWT and password utilities
  tests/               ← pytest files
  database.db          ← SQLite data

frontend/
  src/app/             ← Next.js App Router pages
  src/components/      ← Reusable UI components
  src/lib/             ← Utilities and helpers
  package.json         ← Scripts: dev, build, lint, start
  eslint.config.mjs    ← ESLint (Next.js preset)
  tsconfig.json        ← TypeScript strict mode

public/               ← Legacy static frontend
server.js             ← Legacy Express backend
db.js                 ← Legacy database setup
```

---

## Useful Development Tips

- **Backend API Docs:** Visit `http://localhost:8000/docs` (Swagger UI) when running FastAPI
- **Hot Reload:** Both `npm run dev` and `python main.py` support hot reloading
- **Database Reset:** Delete `backend/database.db` and restart to reset to seeded state
- **Tenant Context:** When working with APIs, always include tenant in JWT claims and filter queries accordingly
- **Type Safety:** Frontend uses TypeScript; backend uses Pydantic for runtime validation

---

## References

- **Architecture & Conventions:** [GEMINI.md](../GEMINI.md)
- **Project README:** [README.md](../README.md)
- **Frontend-Specific Notes:** [frontend/AGENTS.md](../frontend/AGENTS.md)
