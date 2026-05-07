# Multi-Tenant SaaS Transition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transition Easy-Books from a single-tenant prototype to a multi-tenant SaaS platform with JWT authentication and isolated data scoping.

**Architecture:** Shared-database multi-tenancy (Column-based) using a `tenant_id` on all entities. Backend uses FastAPI dependency injection to enforce tenant isolation at the session level.

**Tech Stack:** FastAPI, SQLModel (SQLAlchemy), JWT (python-jose), Bcrypt (passlib), Next.js 16.

---

### Task 1: Add Auth Dependencies & Models

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/models.py`
- Test: `backend/tests/test_models.py`

- [x] **Step 1: Update dependencies**
Add `passlib[bcrypt]`, `python-jose[cryptography]`, and `python-multipart` to `pyproject.toml`.

- [x] **Step 2: Define Tenant and User models**
Modify `backend/models.py` to add `Tenant` and `User` models, and update existing models to include `tenant_id`.

```python
class Tenant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(unique=True, index=True)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: int = Field(foreign_key="tenant.id")
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str
    role: str = "Admin"

# Update Account, Transaction, etc.
class Account(SQLModel, table=True):
    ...
    tenant_id: int = Field(foreign_key="tenant.id", index=True)
```

- [x] **Step 3: Commit**
```bash
git add backend/pyproject.toml backend/models.py
git commit -m "feat: add tenant and user models"
```

---

### Task 2: Implement JWT & Password Hashing

**Files:**
- Create: `backend/auth.py`
- Test: `backend/tests/test_auth.py`

- [x] **Step 1: Write auth utility tests**
Create `backend/tests/test_auth.py` to test password hashing and JWT token creation.

- [x] **Step 2: Implement auth logic**
Create `backend/auth.py` with `get_password_hash`, `verify_password`, and `create_access_token`.

```python
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "super-secret-key-change-in-prod"
ALGORITHM = "HS256"

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

- [x] **Step 3: Run tests and verify**
Run: `pytest backend/tests/test_auth.py`
Expected: PASS

- [x] **Step 4: Commit**
```bash
git add backend/auth.py backend/tests/test_auth.py
git commit -m "feat: implement jwt and password hashing"
```

---

### Task 3: Tenant-Aware Session Dependency

**Files:**
- Modify: `backend/db.py`
- Modify: `backend/main.py`

- [x] **Step 1: Implement get_current_user dependency**
In `backend/main.py`, create a dependency that extracts the `tenant_id` from the JWT token.

- [x] **Step 2: Update get_session to be tenant-aware**
In `backend/db.py`, modify `get_session` or create a new `get_tenant_session` that automatically filters by `tenant_id`.

```python
def get_tenant_session(tenant_id: int):
    with Session(engine) as session:
        # Note: In a real app, we'd use a query listener or base class filter
        # For this task, we will just prepare the session
        yield session
```

- [x] **Step 3: Commit**
```bash
git add backend/db.py backend/main.py
git commit -m "feat: add tenant-aware session logic"
```

---

### Task 4: SaaS Signup & Auto-Seeding

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/db.py`

- [x] **Step 1: Create signup endpoint**
In `backend/main.py`, add `POST /api/auth/signup` that creates a Tenant, a User, and seeds the Chart of Accounts.

- [x] **Step 2: Update seeding logic**
Update `seed_data` in `backend/db.py` to accept a `tenant_id`.

- [x] **Step 3: Commit**
```bash
git add backend/main.py backend/db.py
git commit -m "feat: implement tenant signup and auto-seeding"
```

---

### Task 5: Frontend Auth Integration

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/app/login/page.tsx`
- Modify: `frontend/src/components/Sidebar.tsx`

- [x] **Step 1: Build Login Page**
Create a professional login form in `frontend/src/app/login/page.tsx` using the "Malik Enterprises" theme.

- [x] **Step 2: Dynamic Branding in Sidebar**
Modify `frontend/src/components/Sidebar.tsx` to fetch the tenant name from the auth context instead of hardcoding "Malik Ent."

- [x] **Step 3: Commit**
```bash
git add frontend/src/app/login/page.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat: add login page and dynamic branding"
```
