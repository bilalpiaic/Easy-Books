# Easy-Books User Handbook

Short operator handbook for the dual-home dashboard and tenant segments.
For the full product guide see [USER_GUIDE.md](./USER_GUIDE.md) (§9.1 Dual Home Dashboards).

---

## Two homes: Financial and Operations

| Home | Route | Who it serves | What you see |
|------|-------|---------------|--------------|
| **Financial** | `/dashboard` | Financial manager / management P&amp;L | Revenue, expenses, cash, AR/AP, aging, trends |
| **Operations** | `/dashboard/operations` | Operations / production / clinic / franchise | Module KPIs (lots, WIP, beds, tracker floats, purchase pipeline…) |

Open **Dashboard → Operations** in the top-nav menu (or Ctrl+K `operations dashboard`). The **Financial | Operations** toggle under the page title also switches homes. Pure Base/Services tenants do not see Operations until an industry pack is installed (System → Add-ons).

### Default home by tenant segment

| Segment (`business_model`) | Default home |
|----------------------------|--------------|
| `simple`, `services`, `trader` | Financial |
| `manufacturing`, `yarn_spinning`, `textile_processing`, `hospital`, `telecom_franchise` | Operations |
| PRA portal preference | `/pra-dashboard` |

Change login home anytime: **Settings → Advanced → Home dashboard** (stored as `eb.home_dashboard`).

---

## Customize each home separately

1. Switch to Financial or Operations.
2. Click **Customize** → drag / resize / add / remove widgets.
3. **Done** saves only that home (layout schema v4).

Reset restores defaults for the **active** home only.

---

## Staff permissions

When **User Rights** is enabled (Settings → Advanced), the matrix includes:

| Resource | Category | Meaning |
|----------|----------|---------|
| Financial Dashboard | Dashboard | View Financial home KPI APIs |
| Operations Dashboard | Dashboard | View Operations summary API + toggle data |

Layout save remains a personal preference for any authenticated user.

---

## Demo tenants (password `demo1234`)

| Email | Segment | Expect |
|-------|---------|--------|
| `demo.simple@easy-books.app` | simple | Financial only |
| `demo.manufacturing@easy-books.app` | manufacturing | Toggle; Operations default. Marketplace **Weighbridge** (For you) |
| `demo.spinning@easy-books.app` | yarn_spinning | Spinning Operations. Marketplace **Weighbridge** (For you) |
| `demo.hospital@easy-books.app` | hospital | Healthcare Operations |
| `demo.telecom@easy-books.app` | telecom_franchise | Telecom Operations |
| `demo.pra@easy-books.app` | trader + PRA | PRA portal or Financial |
| `demo.processing@easy-books.app` | textile_processing | Processing Operations |

Mills use **Weighbridge** in the top nav (`/weighbridge`) to record tickets and print slips (no GL). The optional Marketplace overlay still puts **Gate pass** / **Lot ref** on **Sales → New Invoice**. Full steps: [USER_GUIDE.md §41](./USER_GUIDE.md#41-weighbridge-mill-workspace).

Demo seed writes v4 dual-home layouts for owner/accountant users so Operations widgets appear on first login.

Operations home includes process-visibility charts and tables (funnel / WIP / status board / mix) that adapt to installed purpose modules — not only KPI tiles.
