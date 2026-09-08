# How the catalog explorer HTML is shipped for advertisement

The artifact is `catalog-advertisement.html`: a **public, no-login explorer** of every demo tenant, form, Studio tab, report, and screen. Catalog JSON is embedded in the file. Snapshots are JPEGs in a `catalog/` folder (~20 MB).

There is **one canonical public URL**. Ads, email, and social all point at that URL. They never attach the HTML or the JPEG folder.

---

## Canonical URL (primary ship)

On any Easy-Books frontend (dev, desktop, Docker, Vercel):

```
https://<FRONTEND_ORIGIN>/catalog-advertisement.html
```

Examples:

| Environment | URL |
|-------------|-----|
| Local dev | `http://localhost:3000/catalog-advertisement.html` |
| Vercel frontend | `https://<your-frontend>.vercel.app/catalog-advertisement.html` |
| Custom domain | `https://app.example.com/catalog-advertisement.html` |

**Why this is the ad landing page**

- No login, no JWT, no cookies required.
- Next.js already serves `frontend/public/catalog-advertisement.html` and `frontend/public/catalog/*.jpg` as static files.
- Search / kind / tenant / tag filters run entirely in the browser (JSON is inlined).
- In-app Catalog (`Settings → Catalog`) already links here as “public explorer”.

**Ad / social / email CTA** (use this, not a file attachment):

> Browse every mill, hospital, and books screen — snapshots and GL notes, no login.  
> `https://<FRONTEND_ORIGIN>/catalog-advertisement.html`  
> Try a live company: `demo.manufacturing@easy-books.app` / `demo1234`

Do **not** iframe this page in Meta/Google display ads. The app sends `X-Frame-Options: DENY`. Ads must **click out** to the URL.

---

## What not to ship

| Channel | Do not |
|---------|--------|
| Email | Attach the HTML or the 20 MB `catalog/` folder. Most clients cap attachments well below that, and a lone HTML file shows “Snapshot pending” without the JPEGs. |
| Chat (WhatsApp / Slack / LinkedIn DM) | Send the raw `.html` file. Send the **URL**. |
| Display ads | Embed `/catalog-advertisement.html` in an iframe. |
| App stores | Treat this page as a store listing. Store copy lives in `mobile/store/STORE_LISTING.md`. |
| GitHub “raw” links | `raw.githubusercontent.com/.../catalog-advertisement.html` will not resolve `/catalog/*.jpg` on the same origin. |

A single self-contained HTML with every JPEG inlined would be ~25 MB of base64. That is too large for email, GitHub review, and most CDNs as a first paint. We keep JSON in the HTML and pictures as sibling static files.

---

## Offline / sales pack (secondary ship)

For a trade-show laptop, USB stick, or a prospect who cannot reach the cloud:

```bash
python3 docs/marketing/pack_catalog_ad.py
```

Writes `docs/marketing/dist/easy-books-catalog-explorer.zip` (gitignored). Unzip:

```
easy-books-catalog-explorer/
  catalog-advertisement.html   ← double-click
  catalog/*.jpg                ← snapshots (same origin as the HTML)
  README.txt
```

Open `catalog-advertisement.html` in a browser (`file://` is fine). Pictures load from the sibling `catalog/` folder. Google Fonts still need network; without network the page uses system fonts and still works.

Do not commit the zip. Rebuild it when snapshots change:

```bash
cd frontend && npm test -- src/lib/__tests__/workflowCatalog.test.ts
python3 docs/marketing/build_catalog_ad.py
python3 docs/marketing/pack_catalog_ad.py
```

---

## Channel map

| Channel | Ship | Asset |
|---------|------|--------|
| Google / Meta / LinkedIn ads | Click-out URL | Canonical `/catalog-advertisement.html` |
| Email (nurture / one-to-one) | Link in the body | Same URL + demo logins |
| LinkedIn / X / WhatsApp | Paste the URL | Optional: slide `12-cta.png` as the preview image |
| Sales deck / USB / booth | Zip pack | `pack_catalog_ad.py` output |
| Product itself | Static public file | `frontend/public/` on every deploy |
| In-app | Link from Catalog | Settings → Catalog → “public explorer” |

Social copy that can carry the link: [`social/SOCIAL_MEDIA_PACK.md`](./social/SOCIAL_MEDIA_PACK.md) § “Catalog explorer”.

---

## Deploy checklist

1. Snapshots exist in `frontend/public/catalog/` (321 JPEGs; recapture with `CAPTURE_CATALOG=1` if the product UI changed).
2. `python3 docs/marketing/build_catalog_ad.py` copies the explorer HTML into `frontend/public/`.
3. Frontend deploy (Vercel / Docker / `install-and-run`) publishes both the HTML and `/catalog/*.jpg`.
4. Smoke: open `/catalog-advertisement.html` in a logged-out browser, search “studio”, open a card, confirm the snapshot loads.
5. Point ads at that origin. After a custom-domain cutover, update the ad destination URL once.

Desktop and script installs get the same files: they serve `frontend/public/` next to the SPA, so `/catalog-advertisement.html` works on the LAN URL as well.

---

## Ad destination variants (query string)

One hosted file, many campaigns. Filters are read from the URL and written back as the viewer clicks (UTM params are preserved).

| Campaign | Destination |
|----------|-------------|
| Generic catalog | `/catalog-advertisement.html` |
| Spinning mill | `/catalog-advertisement.html?tenant=spinning` |
| Hospital HIS | `/catalog-advertisement.html?tenant=hospital` |
| Textile processing | `/catalog-advertisement.html?tenant=processing` |
| Studio / print | `/catalog-advertisement.html?q=studio` |
| Reports only | `/catalog-advertisement.html?kind=report` |
| One card | `/catalog-advertisement.html?id=<catalog-id>` |

Tracked ads (append, do not replace filters):

```
/catalog-advertisement.html?tenant=spinning&utm_source=linkedin&utm_medium=cpc&utm_campaign=catalog-mill
```

Tenant keys: `simple` `services` `trader` `manufacturing` `telecom` `pra` `hospital` `spinning` `processing`.  
Kind keys: `tenant` `segment` `workflow` `form` `subform` `report` `screen`.

---

## Creative pairing

The HTML is the **landing page**, not the ad creative. Pair:

| Slot | File |
|------|------|
| LinkedIn / Meta image | `docs/marketing/slides/12-cta.png` |
| Carousel | `docs/marketing/slides/01-title.png` … `06-spinning.png` |
| Video | `docs/marketing/video/easy-books-overview.mp4` |
| Click-out | Canonical `/catalog-advertisement.html` (+ query above) |

Open Graph tags on the HTML use `/catalog/services--dashboard.jpg` so a pasted URL can preview when the crawler hits the same origin. Crawlers that require an absolute `og:image` should use the slide PNG as the paid creative instead.

Copy that already carries this CTA: [`social/SOCIAL_MEDIA_PACK.md`](./social/SOCIAL_MEDIA_PACK.md) § “Catalog explorer”.
