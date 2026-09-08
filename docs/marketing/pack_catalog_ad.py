#!/usr/bin/env python3
"""Pack the catalog explorer for offline advertisement (USB / booth / email-of-last-resort).

Layout inside the zip (unzip and double-click the HTML):

  easy-books-catalog-explorer/
    catalog-advertisement.html
    catalog/*.jpg
    README.txt

Does not commit the zip. Output: docs/marketing/dist/easy-books-catalog-explorer.zip
"""
from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
HTML = ROOT / "catalog-advertisement.html"
SHOTS = REPO / "frontend" / "public" / "catalog"
DIST = ROOT / "dist"
ZIP_PATH = DIST / "easy-books-catalog-explorer.zip"
PREFIX = "easy-books-catalog-explorer"

README = """Easy-Books · Workflow Catalog explorer (offline pack)
=====================================================

Double-click catalog-advertisement.html — no install, no login.

Pictures live in the catalog/ folder next to the HTML. Keep that
folder beside the file or snapshots show as “pending”.

This pack is for booths, USB sticks, and airplanes. For ads, email,
and chat, send the hosted URL instead (one link, pictures on the
same origin):

  https://<your-frontend>/catalog-advertisement.html

Live demo companies (password demo1234):
  demo.simple@easy-books.app
  demo.services@easy-books.app
  demo.manufacturing@easy-books.app
  demo.hospital@easy-books.app
  demo.spinning@easy-books.app
  demo.processing@easy-books.app

Rebuild: python3 docs/marketing/pack_catalog_ad.py
Shipping rules: docs/marketing/CATALOG_AD_SHIP.md
"""


def main() -> None:
    if not HTML.is_file():
        raise SystemExit(f"missing {HTML} — run python3 docs/marketing/build_catalog_ad.py first")
    jpgs = sorted(SHOTS.glob("*.jpg"))
    if len(jpgs) < 50:
        raise SystemExit(f"expected catalog JPEGs in {SHOTS}, found {len(jpgs)}")

    DIST.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr(f"{PREFIX}/README.txt", README)
        zf.write(HTML, f"{PREFIX}/catalog-advertisement.html")
        for jpg in jpgs:
            zf.write(jpg, f"{PREFIX}/catalog/{jpg.name}")

    size_mb = ZIP_PATH.stat().st_size / (1024 * 1024)
    print(f"wrote {ZIP_PATH} ({size_mb:.1f} MB, {len(jpgs)} snapshots)")


if __name__ == "__main__":
    main()
