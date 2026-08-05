# Easy-Books Marketing & Presentation Pack

Narrated pictograph presentation, voiceover script, and social copy for commercial outreach.

## Contents

| Path | Purpose |
|------|---------|
| [`slides/`](./slides/) | 12 pictograph slide PNGs (1920×1080) |
| [`audio/`](./audio/) | Per-slide voiceover WAV (espeak-ng) |
| [`video/easy-books-overview.mp4`](./video/easy-books-overview.mp4) | Full narrated presentation |
| [`VOICEOVER_SCRIPT.md`](./VOICEOVER_SCRIPT.md) | Editable narration + bullet source |
| [`social/SOCIAL_MEDIA_PACK.md`](./social/SOCIAL_MEDIA_PACK.md) | LinkedIn, X, Instagram, email copy |
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
```

## Related product docs

- Architecture & competitive frame: [`../PRESENTATION.md`](../PRESENTATION.md)
- Cloud deploy: [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md)
- Living system guide: [`../../CLAUDE.md`](../../CLAUDE.md)
