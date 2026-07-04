---
name: verify
description: Build, launch, and drive Easy-Books to verify a change at the UI surface
---

# Verifying Easy-Books changes end-to-end

## Launch (dev, WSL2)

```bash
# Backend → :8000 (SQLite dev DB, seeds demo tenants on first run)
cd backend && nohup uv run python main.py > /tmp/backend.log 2>&1 &

# Frontend → :3000
cd frontend && nohup npm run dev > /tmp/frontend.log 2>&1 &

# Ready when both return 200:
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/login
```

## Drive with Playwright

Playwright is NOT in frontend/package.json. Browsers are cached in
`~/.cache/ms-playwright/` (chromium). Install the package into a scratch dir:

```bash
cd <scratch> && npm init -y && npm install playwright
node script.mjs   # must run from the dir that has node_modules/playwright
```

## App-driving gotchas

- **Login:** fill `input[type="email"]` / `input[type="password"]`, click
  `button[type="submit"]`, wait for `**/dashboard**`. All demo tenants use
  password `demo1234` (emails in CLAUDE.md, e.g. `demo.manufacturing@easy-books.app`).
- **Wait ~1.5 s after login** for ModuleContext to fetch `/api/modules` —
  module-gated nav appears only after that resolves.
- **TopNav dropdowns are click-toggled.** An open dropdown renders a
  `div.fixed.inset-0` backdrop (z-99) that intercepts all clicks — close it
  (click backdrop with `{ force: true }`) before opening another dropdown.
- **Nav links are duplicated** in hidden containers (MoreDrawer). Always use
  `:visible` filters: `page.locator('a[href="..."]:visible').first()`.
- **Active-section checks:** the app has no `aria-current`/`.active` marker on
  TopNav tabs — assert on which SubNav rail links are visible instead.
- **Which tenant has which module:** query the dev DB —
  `uv run python -c "import sqlite3; print(*sqlite3.connect('backend/database.db').execute('SELECT name, enabled_modules FROM tenant'), sep='\n')"`
