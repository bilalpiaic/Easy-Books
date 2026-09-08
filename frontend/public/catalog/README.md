# Catalog snapshots

JPEGs in this folder back **Settings → Catalog** and the public explorer at `/catalog-advertisement.html`.

Recapture missing shots (dev servers on :3000 / :8000). Existing files are skipped unless `CAPTURE_CATALOG_FORCE=1`:

```bash
cd frontend
npm test -- src/lib/__tests__/workflowCatalog.test.ts   # refreshes e2e/catalog-shots.json
CAPTURE_CATALOG=1 npx playwright test e2e/capture-catalog.spec.ts
```

Filenames are `{tenant}--{path-slug}.jpg` so several catalog cards can share one snap. `{id}` in a capture path becomes `id` in the filename.

**Ads / email:** do not attach these JPEGs or the HTML. Point campaigns at the hosted explorer (`/catalog-advertisement.html`). Shipping rules: `docs/marketing/CATALOG_AD_SHIP.md`. Offline zip: `python3 docs/marketing/pack_catalog_ad.py`.
