# Easy-Books Frontend

Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS v4.

The auth-gated app for the [Easy-Books](../README.md) multi-tenant accounting SaaS. Talks to the FastAPI backend at `NEXT_PUBLIC_API_URL`.

> **Heads up:** This project uses **Next.js 16**, which has breaking changes from earlier versions. Before making frontend changes, read the relevant guide in `node_modules/next/dist/docs/` — see [`AGENTS.md`](./AGENTS.md).

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start dev server on `http://localhost:3000` (binds `0.0.0.0`) |
| `npm run build` | Production build |
| `npm start` | Serve the production build |
| `npm run lint` | Run ESLint |

For one-shot dev (backend + frontend together), use `./dev.sh` at the repo root.

## Environment

Copy `.env.example` to `.env.local`:

| Variable | Required | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | FastAPI base URL (e.g. `http://localhost:8000` in dev) |

## Layout

```
src/
├── app/                # Next.js App Router
│   ├── login/  signup/ # public routes
│   └── (dashboard)/    # auth-gated route group (29 pages)
├── components/         # UI components (Sidebar, DocLink, PrintHeader, ...)
├── context/            # SettingsContext (currency/company)
└── lib/                # apiFetch, auth helpers
```

See the root [`README.md`](../README.md) for the full app overview and the
[`BLUEPRINT.md`](../BLUEPRINT.md) for the complete page/component inventory.

## Deployment

See [`DEPLOYMENT.md`](../DEPLOYMENT.md) — the frontend deploys as a separate
Vercel project (`easy-books-frontend`) and points at the backend via
`NEXT_PUBLIC_API_URL`.
