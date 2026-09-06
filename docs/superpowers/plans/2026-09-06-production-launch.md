# Easy-Books production launch plan

**Date:** 2026-09-06  
**Status:** Wave 1 product (#370–#376 + P7.3 Weighbridge) is on `main` / this PR. Remaining launch work is **ops secrets** (Stripe/S3/Neon PITR), **Wave 0 GitHub closes** (issues API 403), and **CI debt** (frontend lint, Alembic upgrade-over-create_all).  
**Audience:** ship paying tenants on the existing Vercel + Neon stack  
**Companion:** Studio/customization spec `docs/superpowers/specs/2026-09-06-tenant-customization-studio-design.md`

## How this board was read

GitHub Issues API is **403** for the default integration (`repository.issues`). This plan is reconstructed from:

- In-repo `docs/ROADMAP.md` (last reviewed **2026-08-04** — **stale** vs later merges)
- Merged PRs #319–#367 (spinning through demo-seed lite)
- Newly filed Studio epic **#369** and children **#370–#376**
- Indexed public issues: #112, #114–#125, #193, #227
- Code: `services/saas.py`, `routers/billing.py`, TOTP/OAuth, ARQ queue, S3 storage, portal, webhooks, `PLAN_LIMITS`

Treat GitHub “Open” as **untrusted** until a hygiene pass (Wave 0). Several v6 tickets are still Open on paper and **already merged**.

## Product decision (locked)

Launch as **one SaaS**: one `main`, one Vercel frontend, one Vercel FastAPI, one Neon database. Client = `Tenant` row. Industry differences = `enabled_modules` + entitlements + Settings. **Not** per-client git branches or extra Neon projects.

#308 (partner **code execution**) stays **wontfix for production**. Marketplace remains declarative (`#227` + #371 / #376).

---

## Issue inventory (production-relevant)

### A. Already in `main` — close or convert to “harden” tickets

| Issue (ROADMAP / GitHub) | Code / PR evidence | Action |
|--------------------------|--------------------|--------|
| #117 AI L1 | Agent pipeline in `routers/ai_chat.py` | Close if still open |
| #118 2FA + SSO | TOTP + Google/Microsoft OAuth, login UI, `test_wave_bcd.py` | Close **v1**; open “require TOTP for owner” as follow-up |
| #114 webhooks | `WebhookEndpoint`, outbox, Settings UI; branch deleted after merge | Close if still open |
| #115 task queue | `backend/tasks/` + ARQ; Redis optional | Close v1; harden Redis-on-Vercel as ops |
| #116 cloud stack | Vercel workflows + Neon `DATABASE_URL` + S3 helper | Close original VPS/Caddy AC; ops uses Vercel not Caddy |
| #119 / #271 plans + quotas | `PLAN_LIMITS`, 402 on quota, `/api/billing/*`, Settings → Billing | Close **metering v1**; keep Stripe **live keys** as Wave 1 ops |
| #120 portal + dunning | Dunning shipped; portal + Stripe pay (`portal_pay.py`, #270 tests) | Close or split: remaining = Collections UI polish only |
| #123 approvals | `approvals` routers + SoD tests | Close v1 |
| #220 / #299 practice | Memberships, switcher, practice page; PR #324 | Close #299 |
| #300 FX UX | PR #323 | Close |
| #301 / #268 bank feeds | Plaid-class adapters + sync status; PR #344 | Close v1; Plaid production credentials = Wave 1 ops |
| #302 WMS | Transfers + pick/pack; PRs #346, #351 | Close |
| #303 leave | PR #347 | Close v1 (statutory packs later) |
| #304 POS | PR #345 | Close |
| #305 eCommerce | PR #350 | Close v1 (Daraz if still thin) |
| #227 marketplace manifests | `services/marketplace/` | Keep open **only** as parent of #371/#376 |
| #255–#267 IFRS/tax | ROADMAP v5 complete | Already closed per ROADMAP |
| #264–#266 localization | Modules in `MODULE_REGISTRY` | Shipped |

### B. Still real work — production path

| Issue | Why it matters for launch | Wave |
|-------|---------------------------|------|
| **#370–#376** entitlements / audience / Studio | Shipped PRs #377–#383; P7.3 Weighbridge private listing | Close on GitHub |
| **#369** epic | Tick shipped children; remaining is GTM/ops | Hygiene + ops |
| **#119 remainder** | Stripe Checkout in **test** vs **live**; suspend on failed payment | **1** ops |
| **#116 remainder** | Postgres CI job added; S3 + Neon PITR still host secrets | **1** ops |
| **#121** Plaid-class feeds | Code exists; production bank connections | **2** if a client needs it |
| **#122** AI L2 OCR | Differentiator, not launch blocker | **4** |
| **#124 / #125** AI L3–5 | After L2 | **4+** |
| **#193** parity epic | Backlog spine; do not build all of it | Hygiene |
| **#306** more country packs | Entitle existing packs first (#370) | **4** |
| **#307** native mobile | PWA is enough | Defer |
| **#308** partner executable code | Conflicts with sandbox | **Wontfix** |
| **#309** SOC 2 | Deferred since 2026-07 | Defer |

### C. Do not build for first production

- Per-client Vercel/Neon
- Odoo xpath / partner Python in-process (#308)
- Unlimited Studio fields in GL
- Native iOS/Android (#307)
- SOC 2 evidence pack (#309) until a contract requires it

---

## What “production” means here

A stranger can:

1. Sign up → land on **Base** only (or a paid pack you entitled).
2. Pay (or start a trial) → quotas and module install match the plan.
3. Not see other tenants’ data, modules, or private Marketplace listings.
4. Get backups, TLS, secrets, and a way for **you** to entitle spinning/healthcare without a git branch.
5. Use TOTP; you can restore the tenant from backup.

Industry modules (spinning, hospital, weaving, POS, …) are **already in the binary**. Production is **control + ops**, not more modules.

---

## Wave 0 — Board hygiene (do first, no product code)

1. Close or comment “shipped in PR …” on: #299, #300, #301, #302, #303, #304, #305, and any still-open #114–#119 / #123 / #117 / #118 v1.
2. Update `docs/ROADMAP.md` “Open” rows to match `main` (this file is the source of truth until the board is clean).
3. Point #193 and #112 at **#369** for GTM/customization instead of implying more forks.
4. Label #308 `wontfix` with: use Track B/C (manifest + API/webhooks), not in-process code.
5. Keep **one** open epic for launch: **#369** (product) + this plan (ops).

**Done when:** someone opening GitHub does not think POS/eCommerce/practice are unbuilt.

---

## Wave 1 — Launch blockers (ship before first paid tenant)

Order inside the wave: **ops checklist in parallel with #370**, then #371.

### 1.1 Module entitlements — [#370](https://github.com/bilalpiaic/Easy-Books/issues/370)

**Blocker:** any owner can `POST /api/modules/spinning/install`.

Ship `PLAN_MODULES` + `OPS_ADMIN_EMAILS` + install 403 + Apps `installable`. Demo tenants `plan=enterprise`. Rollback: `ENFORCE_MODULE_PLANS=false`.

**Launch AC:** mill entitled to spinning; hospital 403; no new git branch.

### 1.2 Marketplace filter — [#371](https://github.com/bilalpiaic/Easy-Books/issues/371)

**Blocker:** catalog JSON is global.

Ship `audience` + server filter + **For you**. No tenant-name tags.

### 1.3 Billing live (code exists: `routers/billing.py`)

| Check | Action |
|-------|--------|
| Stripe **live** keys on Vercel backend | `STRIPE_*` in Vercel env, not git |
| Webhook endpoint | `https://<api>/api/stripe/webhook` + `invoice.payment_failed` → suspend |
| Settings → Billing | Real Checkout for starter/pro |
| Free default | New signup `plan=free`, document cap 50 |
| Trial | `trial_ends_at` if you sell “14 days Pro”; else skip |

Do **not** rebuild #119. Wire production secrets and one test charge + one failed-card suspend.

### 1.4 Data & runtime (Vercel + Neon)

| Check | Action |
|-------|--------|
| `JWT_SECRET_KEY` | Unique, not default; rotate if ever committed |
| `DATABASE_URL` | Neon **pooled** URL; `sslmode=require` (already in `db.py`) |
| `FRONTEND_ORIGIN` / CORS | Exact production origin |
| Uploads | `STORAGE_BACKEND=s3` + bucket (Vercel disk is ephemeral) |
| Backups | Neon PITR **on** + documented restore drill; tenant ZIP (`/api/backup`) is not a substitute for DB PITR |
| Redis / ARQ | Optional; if unset, in-process fallback — OK for v1 if webhooks volume is low |
| CI | Keep SQLite pytest; **add** one GitHub Actions job `pytest` against Postgres (issue #116 leftover) |
| `DEPLOY_VERCEL` | Confirm Actions variable is `true` and both Vercel projects deploy on `main` |
| Health | `GET /api/health` in uptime monitor |

### 1.5 Security baseline

| Check | Action |
|-------|--------|
| TOTP | Encourage in onboarding; **require for `owner`** before go-live (small follow-up on #118) |
| Demo passwords | Disable or isolate demo tenants on production (`SEED_DEMO=false`) |
| Rate limits | Confirm login lockout + `ai_rate_limit_per_hour` |
| Suspended tenants | 402 on accounting writes (`main.py` + `saas.py`) — verify with a live flag |

**Wave 1 done when:** you can create tenant A (free), entitle spinning via ops, take a Stripe test→live payment, restore from Neon PITR, and tenant B cannot install spinning or see A’s private catalog row.

---

## Wave 2 — First paying vertical (after Wave 1)

Pick **one** launch vertical (recommend: **yarn spinning** or **trader+POS**, whichever has a signed client). Do not entitle every industry pack.

| Work | Issue | Notes |
|------|--------|--------|
| Entitle that pack only | #370 | Ops PUT |
| Settings + CoA + tax pack | config | PKR + `in_gst` / `pra` / none as contracted |
| Custom fields the client actually asked for | **#372** | Cap 12; `x.*`; no GL |
| Bank connection if they pay for it | #121 | Production Plaid/GoCardless credentials |
| Portal pay if they invoice customers online | #120 remainder | Stripe live |

**Wave 2 done when:** that client’s users log in, post invoices/stock in **their** modules, and a second tenant does not see those modules or `x.*` fields.

Skip #373–#376 until a second client needs a different **core** field hidden, not just extra fields.

---

## Wave 3 — Studio-lite (second client / partners)

Only if Wave 2 clients need hide/show of core fields or a private Marketplace card.

| Issue | Ship |
|-------|------|
| #373 | Form schema + API enforce |
| #374 | Print clone + report-builder `x.*` |
| #375 | Field-level rights |
| #376 | Settings → Studio + declarative bundle |

**Wave 3 done when:** two tenants share `InvoiceForm.tsx` with different visible fields; a private listing installs a bundle for mill only.

---

## Wave 4 — After revenue (not launch)

| Item | When |
|------|------|
| AI L2 OCR (#122) | Bookkeepers ask to photograph bills |
| AI L3–5 (#124, #125) | After L2 is used in production |
| More countries (#306) | A signed contract in that country |
| Native mobile (#307) | PWA pain is measured |
| SOC 2 (#309) | Enterprise RFP |
| Partner in-process code (#308) | Never on this architecture |

---

## Launch playbook (people, not git)

1. Production Vercel + Neon + Stripe live (Wave 1.3–1.4).  
2. `SEED_DEMO=false` on production.  
3. Your user email in `OPS_ADMIN_EMAILS`.  
4. Create client tenant (signup or ops).  
5. `PUT /api/ops/tenants/{id}/modules` for the contract pack.  
6. They install (or you POST install).  
7. Settings: legal name, logo, currency, FY, tax module.  
8. Invite users; owner enables TOTP.  
9. One backup restore drill **before** they enter live invoices.

No `client-acme` branch. No second Neon “for that mill.”

---

## Suggested issue/PR sequence from here

| Order | PR / issue | Blocks launch? |
|-------|------------|----------------|
| 0 | Hygiene comments/closes on shipped #299–#305 / #370–#376 (needs issues write) | No, but unblocks thinking |
| 1 | Secrets + S3 + Neon PITR + Stripe live (no issue; ops) | **Yes** |
| 2 | Postgres CI job (this PR; schema wipe vs `drop_all`) | Strong yes |
| 3 | Require TOTP for owner | Strong yes |

Do not start #122 or #307 until Wave 1 is green.

---

## Risks if you skip Wave 1

| Skip | Failure |
|------|---------|
| Entitlements | Every signup is a full ERP; you cannot sell packs |
| Global catalog | Client-specific listing leaks |
| No S3 | Logos/attachments vanish on serverless |
| No PITR | One bad migration loses all tenants |
| Stripe test keys | You cannot get paid |
| Demo seed on prod | `demo1234` is a public backdoor |

---

## Success criteria (go-live)

- [ ] Production has **no** demo logins.  
- [ ] Free tenant cannot install `spinning` / `healthcare` (#370).  
- [ ] Ops can entitle a named tenant without a deploy.  
- [ ] Stripe live Checkout upgrades plan and raises quotas.  
- [ ] Neon PITR restore tested once.  
- [ ] Uploads survive a Vercel redeploy (S3).  
- [ ] Owner TOTP on.  
- [ ] Two tenants: data and catalog isolation proven with real accounts.  
- [ ] `docs/ROADMAP.md` matches GitHub (Wave 0).

When those boxes are ticked, **sell**. Studio (#373–#376) and AI L2+ are post-revenue.
