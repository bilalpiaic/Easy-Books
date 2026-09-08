# Easy-Books Marketing & Presentation Pack

Narrated pictograph presentation, voiceover script, and social copy for commercial outreach.

## Contents

| Path | Purpose |
|------|---------|
| [`slides/`](./slides/) | 12 pictograph slide PNGs (1920×1080) |
| [`audio/`](./audio/) | Per-slide voiceover WAV (espeak-ng) |
| [`video/easy-books-overview.mp4`](./video/easy-books-overview.mp4) | Full narrated presentation |
| [`VOICEOVER_SCRIPT.md`](./VOICEOVER_SCRIPT.md) | Editable narration + bullet source |
| [`catalog-advertisement.html`](./catalog-advertisement.html) | **Standalone ad page** for Settings → Catalog (self-contained HTML, double-click to open) |
| [`catalog-ad/`](./catalog-ad/) | Source JPEGs used by the catalog advertisement |
| [`build_catalog_ad.py`](./build_catalog_ad.py) | Rebuilds the advertisement HTML (embeds the JPEGs) |
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

# Catalog advertisement HTML (embeds JPEGs from catalog-ad/)
python3 docs/marketing/build_catalog_ad.py
```

## Related product docs

- Architecture & competitive frame: [`../PRESENTATION.md`](../PRESENTATION.md)
- Cloud deploy: [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md)
- Living system guide: [`../../CLAUDE.md`](../../CLAUDE.md)
