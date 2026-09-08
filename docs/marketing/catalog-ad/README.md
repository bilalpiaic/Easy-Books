# Catalog advertisement source snaps

JPEGs captured from Settings → Catalog and live demo screens.

Rebuild the standalone HTML:

```bash
python3 docs/marketing/build_catalog_ad.py
```

Output: `docs/marketing/catalog-advertisement.html` (also copied to `frontend/public/catalog-advertisement.html`).

**Shipping for ads:** do not attach this HTML. Point campaigns at  
`https://<FRONTEND_ORIGIN>/catalog-advertisement.html`  
See [`../CATALOG_AD_SHIP.md`](../CATALOG_AD_SHIP.md). Offline zip: `python3 docs/marketing/pack_catalog_ad.py`.
