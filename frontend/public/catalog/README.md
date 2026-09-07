# Catalog snapshots

JPEGs in this folder back **Settings → Catalog**.

Recapture (dev servers on :3000 / :8000):

```bash
cd frontend
CAPTURE_CATALOG=1 npx playwright test e2e/capture-catalog.spec.ts
```

Filenames are `{tenant}--{path-slug}.jpg` so several catalog cards can share one snap.
