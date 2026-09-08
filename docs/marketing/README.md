# Easy-Books Marketing & Presentation Pack

Narrated pictograph presentation, voiceover script, and social copy for commercial outreach.

## Contents

| Path | Purpose |
|------|---------|
| [`slides/`](./slides/) | 12 pictograph slide PNGs (1920×1080) |
| [`audio/`](./audio/) | Per-slide voiceover WAV (espeak-ng) |
| [`video/easy-books-overview.mp4`](./video/easy-books-overview.mp4) | Full narrated presentation |
| [`VOICEOVER_SCRIPT.md`](./VOICEOVER_SCRIPT.md) | Editable narration + bullet source |
| [`catalog-advertisement.html`](./catalog-advertisement.html) | **Standalone catalog explorer** (no login). Hosted at `/catalog-advertisement.html`. |
| [`CATALOG_AD_SHIP.md`](./CATALOG_AD_SHIP.md) | **How to ship it for ads** — canonical URL, what not to attach, offline zip pack. |
| [`catalog-index.json`](./catalog-index.json) | Catalog metadata embedded into the explorer (from the frontend vitest). |
| [`catalog-ad/`](./catalog-ad/) | Optional hero JPEGs (legacy ad stills) |
| [`build_catalog_ad.py`](./build_catalog_ad.py) | Rebuilds the explorer HTML from `catalog-index.json` |
| [`pack_catalog_ad.py`](./pack_catalog_ad.py) | Builds `dist/easy-books-catalog-explorer.zip` (HTML + snapshots, gitignored) |
| [`../../ship-catalog-ad.sh`](../../ship-catalog-ad.sh) · [`.ps1`](../../ship-catalog-ad.ps1) · [`.bat`](../../ship-catalog-ad.bat) | One-click rebuild + zip from the project root (prints every required path) |
| [`build_presentation.py`](./build_presentation.py) | Regenerates slides, audio, and MP4 |

## Segments covered (voiceover)

1. Product thesis  
2. SME tooling gap  
3. Single GL architecture  
4. Industry packs overview  
5. **Textile Processing** use case  
6. **Yarn Spinning** use case  
7. Healthcare / Telecom / Purchases  
8. IFRS advancements  
9. Agentic AI assistant  
10. Deploy options (desktop · Docker · Vercel+Neon)  
11. Commercial advantages  
12. Demo CTAs (incl. processing tenant)

## Regenerate

```bash
# Requires: python3-pil, espeak-ng, ffmpeg
python3 docs/marketing/build_presentation.py

# Catalog explorer HTML (embeds catalog JSON; snapshots from frontend/public/catalog/)
cd frontend && npm test -- src/lib/__tests__/workflowCatalog.test.ts
python3 docs/marketing/build_catalog_ad.py

# Offline USB/booth zip (not committed)
python3 docs/marketing/pack_catalog_ad.py

# Same two steps, with paths printed (repo root):
./ship-catalog-ad.sh
# Windows: ship-catalog-ad.bat
```

How ads, email, and social should point at this file: [`CATALOG_AD_SHIP.md`](./CATALOG_AD_SHIP.md).  
Campaigns may deep-link (`?tenant=spinning`, `?kind=report`, `?q=studio`); UTM params are preserved.

## Related product docs

- Architecture & competitive frame: [`../PRESENTATION.md`](../PRESENTATION.md)
- Cloud deploy: [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md)
- Living system guide: [`../../CLAUDE.md`](../../CLAUDE.md)
