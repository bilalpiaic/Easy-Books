#!/usr/bin/env python3
"""Build a self-contained advertisement HTML for Settings → Catalog.

Reads JPEGs from docs/marketing/catalog-ad/ and writes:
  docs/marketing/catalog-advertisement.html
  frontend/public/catalog-advertisement.html
"""
from __future__ import annotations

import base64
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "catalog-ad"
OUT_DOCS = ROOT / "catalog-advertisement.html"
OUT_PUBLIC = ROOT.parent.parent / "frontend" / "public" / "catalog-advertisement.html"


def data_uri(name: str) -> str:
    path = ASSETS / name
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def img(name: str, alt: str, cls: str = "") -> str:
    cls_attr = f' class="{cls}"' if cls else ""
    return f'<img src="{data_uri(name)}" alt="{alt}"{cls_attr} />'


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Easy-Books · Workflow Catalog — advertisement</title>
<meta name="description" content="Every demo tenant, segment, workflow, report and screen — photographed, tagged, and explained. Settings → Catalog." />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Serif+Display:ital@0;1&display=swap" rel="stylesheet" />
<style>
  :root {
    --cream: #f6f3ee;
    --paper: #fffdf8;
    --gold: #b8943f;
    --gold-dark: #7a5c1e;
    --charcoal: #1a1814;
    --muted: rgba(26,24,20,.62);
    --line: rgba(26,24,20,.12);
    --ink: #1a1814;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body {
    font-family: "DM Sans", ui-sans-serif, system-ui, sans-serif;
    background: var(--cream);
    color: var(--ink);
    line-height: 1.55;
  }
  img { max-width: 100%; height: auto; display: block; }
  a { color: var(--gold-dark); }
  .wrap { max-width: 1120px; margin: 0 auto; padding: 0 24px; }
  header.top {
    display: flex; align-items: center; justify-content: space-between;
    padding: 18px 24px; max-width: 1120px; margin: 0 auto;
  }
  .brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: inherit; }
  .mark {
    width: 36px; height: 36px; border-radius: 10px; background: var(--gold);
    font-family: "DM Serif Display", Georgia, serif; font-size: 20px;
    display: grid; place-items: center; font-weight: 700;
  }
  .brand b { font-size: 15px; letter-spacing: .02em; }
  .chip {
    font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
    color: var(--gold-dark); background: rgba(184,148,63,.16);
    border: 1px solid rgba(184,148,63,.35); padding: 6px 10px; border-radius: 999px;
  }
  .hero { padding: 48px 0 28px; }
  .hero h1 {
    font-family: "DM Serif Display", Georgia, serif;
    font-size: clamp(36px, 6vw, 64px); font-weight: 400; line-height: 1.08;
    max-width: 16ch;
  }
  .hero h1 em { font-style: italic; color: var(--gold-dark); }
  .lede {
    margin-top: 18px; max-width: 52ch; font-size: 18px; color: var(--muted);
  }
  .cta-row { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px; }
  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    background: var(--gold); color: #1a1814; text-decoration: none;
    font-weight: 700; font-size: 14px; padding: 12px 18px; border-radius: 10px;
  }
  .btn.ghost {
    background: transparent; border: 1px solid var(--line);
  }
  .stats {
    display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px;
    margin: 40px 0 8px;
  }
  .stat {
    background: var(--paper); border: 1px solid var(--line); border-radius: 16px;
    padding: 18px 16px;
  }
  .stat strong { display: block; font-size: 28px; font-family: "DM Serif Display", Georgia, serif; }
  .stat span { font-size: 12px; color: var(--muted); font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
  .shot {
    margin: 36px 0; border-radius: 18px; overflow: hidden;
    border: 1px solid var(--line); box-shadow: 0 18px 50px rgba(26,24,20,.08);
    background: #fff;
  }
  .shot figcaption {
    padding: 12px 16px; font-size: 13px; color: var(--muted); background: var(--paper);
    border-top: 1px solid var(--line);
  }
  section.block { padding: 56px 0 8px; }
  section.block h2 {
    font-family: "DM Serif Display", Georgia, serif;
    font-size: clamp(26px, 4vw, 40px); font-weight: 400; margin-bottom: 10px;
  }
  section.block p.sub { color: var(--muted); max-width: 58ch; margin-bottom: 28px; }
  .pillars { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  .pillar {
    background: var(--paper); border: 1px solid var(--line); border-radius: 16px; padding: 22px;
  }
  .pillar .n {
    font-size: 11px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase;
    color: var(--gold-dark); margin-bottom: 8px;
  }
  .pillar h3 { font-size: 18px; margin-bottom: 8px; }
  .pillar p { font-size: 14px; color: var(--muted); }
  .gallery {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
  }
  .gallery .shot { margin: 0; }
  .tenants {
    display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 24px;
  }
  .tenants span {
    font-size: 13px; padding: 7px 12px; border-radius: 999px;
    border: 1px solid var(--line); background: #fff;
  }
  .how {
    display: grid; grid-template-columns: 1fr 1fr; gap: 28px; align-items: start;
    margin-top: 12px;
  }
  ol.steps { padding-left: 22px; color: var(--muted); font-size: 15px; }
  ol.steps li { margin: 8px 0; }
  .gl {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13px; background: #1a1814; color: #ffd966;
    padding: 16px 18px; border-radius: 12px; margin-top: 16px;
  }
  .cta-band {
    margin: 64px 0 24px; background: #1a1814; color: #fffdf8;
    border-radius: 24px; padding: 40px 36px;
  }
  .cta-band h2 { font-family: "DM Serif Display", Georgia, serif; font-size: 32px; font-weight: 400; }
  .cta-band p { color: rgba(255,253,248,.72); margin: 10px 0 22px; max-width: 52ch; }
  .cta-band .btn { color: #1a1814; }
  .logins { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 18px; }
  .logins code {
    display: block; background: rgba(255,253,248,.08); border: 1px solid rgba(255,253,248,.12);
    border-radius: 10px; padding: 10px 12px; font-size: 12px; color: #ffd966;
  }
  .logins small { display: block; color: rgba(255,253,248,.55); margin-bottom: 4px; }
  footer {
    padding: 28px 0 48px; color: var(--muted); font-size: 13px;
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px;
  }
  @media (max-width: 800px) {
    .stats, .pillars, .gallery, .how, .logins { grid-template-columns: 1fr; }
    header.top { padding: 14px 16px; }
  }
  @media print {
    .btn, header.top .chip { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .cta-band { break-inside: avoid; }
    .shot { box-shadow: none; }
  }
</style>
</head>
<body>
  <header class="top">
    <a class="brand" href="#top">
      <span class="mark">E</span>
      <b>Easy-Books</b>
    </a>
    <span class="chip">Settings → Catalog</span>
  </header>

  <main class="wrap" id="top">
    <section class="hero">
      <h1>Every workflow,<br>photographed.<br><em>Every posting, explained.</em></h1>
      <p class="lede">
        The in-app <strong>Workflow Catalog</strong> sits in Settings — a tagged gallery of
        every demo company, nav segment, end-to-end workflow, report, and screen.
        Open a card for the snapshot, the steps, and the Dr/Cr lines.
      </p>
      <div class="cta-row">
        <a class="btn" href="#catalog">See the catalog</a>
        <a class="btn ghost" href="#try">Try a demo company</a>
      </div>
    </section>

    <div class="stats">
      <div class="stat"><strong>9</strong><span>Demo tenants</span></div>
      <div class="stat"><strong>26</strong><span>Nav segments</span></div>
      <div class="stat"><strong>23</strong><span>Workflows</span></div>
      <div class="stat"><strong>55+</strong><span>Reports &amp; screens</span></div>
    </div>

    <figure class="shot" id="catalog">
      __SHOT_SETTINGS__
      <figcaption>Settings → <strong>Catalog</strong> tab, next to Company, Accounting, Studio, and Updates.</figcaption>
    </figure>

    <section class="block">
      <h2>One gallery for the whole product</h2>
      <p class="sub">
        Filter by kind (tenants, segments, workflows, reports, screens), by demo company,
        or by tag — <em>sales, gl, spinning, healthcare, compliance</em>. Search “trial balance”
        or “ZATCA” and jump to the live screen.
      </p>
      <figure class="shot">
        __SHOT_ALL__
        <figcaption>259 catalog entries with tenant cards, tag cloud, and live snapshots.</figcaption>
      </figure>
    </section>

    <section class="block">
      <h2>Built for demos, onboarding, and sales</h2>
      <div class="pillars">
        <article class="pillar">
          <div class="n">01 · Tags</div>
          <h3>Find the right story in seconds</h3>
          <p>Mill, hospital, franchise, IFRS, localization — tags and tenant pills replace a 40-page slide deck.</p>
        </article>
        <article class="pillar">
          <div class="n">02 · Snapshots</div>
          <h3>Show the real UI, not mockups</h3>
          <p>Each card carries a JPEG captured from the seeded demo companies. Click to lightbox or open the live route.</p>
        </article>
        <article class="pillar">
          <div class="n">03 · GL notes</div>
          <h3>Smart explanations, not slogans</h3>
          <p>Workflows include numbered steps and the actual Dr/Cr (1100 AR / 4100 Sales, 1200 RM → 1204 FG, and so on).</p>
        </article>
      </div>
    </section>

    <section class="block">
      <h2>Workflows with the posting map</h2>
      <p class="sub">
        Twenty-three end-to-end loops — sales, demand→PO→gate, store issue, payroll,
        OPD/IPD/lab, spinning, weaving, processing, weighbridge, telecom, POS, IFRS 15/16,
        period close, and e-invoice packs.
      </p>
      <div class="how">
        <figure class="shot" style="margin:0">
          __SHOT_WORKFLOWS__
          <figcaption>Workflows filter — sales cycle, AP bills, purchase-store chain.</figcaption>
        </figure>
        <div>
          <h3 style="margin-bottom:8px">Sales cycle, as the catalog tells it</h3>
          <ol class="steps">
            <li>Create the customer (prints on the invoice).</li>
            <li>New Invoice — lines, tax, due date from payment terms.</li>
            <li>Post: Dr 1100 AR / Cr 4100 (or 2300 if deferred).</li>
            <li>Collect via Payments Received.</li>
            <li>Credit note for returns — history stays intact.</li>
          </ol>
          <div class="gl">Invoice Dr 1100 / Cr 4100 (+ tax)<br/>Receipt Dr 1010 Bank / Cr 1100<br/>Credit note Dr 4100 / Cr 1100</div>
        </div>
      </div>
      <figure class="shot">
        __SHOT_DRAWER__
        <figcaption>Open a card: snapshot, how-it-works, GL posting, tags, and “Open live screen”.</figcaption>
      </figure>
    </section>

    <section class="block">
      <h2>Nine companies. One catalog.</h2>
      <p class="sub">Each demo tenant is a first-class catalog entry — so a mill walkthrough and a hospital walkthrough start from the same Settings page.</p>
      <div class="tenants">
        <span>Simple</span><span>Services</span><span>Trader</span>
        <span>Manufacturing</span><span>Telecom franchise</span><span>PRA e-Invoice</span>
        <span>Hospital</span><span>Yarn spinning</span><span>Textile processing</span>
      </div>
      <figure class="shot">
        __SHOT_TENANTS__
        <figcaption>Tenant cards explain the model, modules, and the first three things to click.</figcaption>
      </figure>
    </section>

    <section class="block">
      <h2>The same books, industry-deep</h2>
      <p class="sub">Catalog screens are captured from live seeded data — invoices, trial balance, mill operations, OPD, spin lots.</p>
      <div class="gallery">
        <figure class="shot">
          __SHOT_TB__
          <figcaption>Trial Balance — hierarchical tree, live GL.</figcaption>
        </figure>
        <figure class="shot">
          __SHOT_INV__
          <figcaption>Sales invoices — the AR loop the sales-cycle card explains.</figcaption>
        </figure>
        <figure class="shot">
          __SHOT_OPS__
          <figcaption>Manufacturing operations home — weaving + production KPIs.</figcaption>
        </figure>
        <figure class="shot">
          __SHOT_DEMAND__
          <figcaption>Purchase demands — quantity-only requisitions in the store chain.</figcaption>
        </figure>
        <figure class="shot">
          __SHOT_OPD__
          <figcaption>Hospital OPD — visits that post Dr 1100 / Cr 4100.</figcaption>
        </figure>
        <figure class="shot">
          __SHOT_SPIN__
          <figcaption>Yarn spinning lots — bale → WIP → cone, full GL.</figcaption>
        </figure>
      </div>
    </section>

    <section class="block">
      <h2>Reports and screens, not a buried wiki</h2>
      <p class="sub">Fifty-five reports and 146 screens share the same tag language as the workflows. A prospect can scan IFRS, tax, or spinning without leaving Settings.</p>
      <div class="gallery">
        <figure class="shot">
          __SHOT_REPORTS__
          <figcaption>Reports kind — trial balance, P&amp;L, aging, CIT, ZATCA logs.</figcaption>
        </figure>
        <figure class="shot">
          __SHOT_SCREENS__
          <figcaption>Screens kind — every unique sidebar route as a catalog card.</figcaption>
        </figure>
      </div>
    </section>

    <div class="cta-band" id="try">
      <h2>Open it in the product</h2>
      <p>Sign in to any demo company (password <strong>demo1234</strong>), then go to <strong>Settings → Catalog</strong>. Search a workflow, click a tag, open the live screen.</p>
      <a class="btn" href="/settings/catalog">Launch Catalog in Easy-Books</a>
      <p style="margin-top:14px;font-size:13px;color:rgba(255,253,248,.55)">If you opened this file on disk, sign in to the app first, then visit Settings → Catalog.</p>
      <div class="logins">
        <code><small>Simple books</small>demo.simple@easy-books.app</code>
        <code><small>Services / IFRS 15</small>demo.services@easy-books.app</code>
        <code><small>Trader + POS + GST</small>demo.trader@easy-books.app</code>
        <code><small>Mill + weaving</small>demo.manufacturing@easy-books.app</code>
        <code><small>Hospital</small>demo.hospital@easy-books.app</code>
        <code><small>Yarn spinning</small>demo.spinning@easy-books.app</code>
      </div>
    </div>

    <footer>
      <span>Easy-Books · Workflow Catalog advertisement · Settings → Catalog</span>
      <span>Double-entry for SMEs · cream / gold · one GL writer</span>
    </footer>
  </main>
</body>
</html>
"""


def main() -> None:
    html = HTML
    replacements = {
        "__SHOT_SETTINGS__": img("01-settings-catalog-tab.jpg", "Settings page with Catalog tab", "full"),
        "__SHOT_ALL__": img("02-catalog-all.jpg", "Workflow catalog grid of tenant cards", "full"),
        "__SHOT_WORKFLOWS__": img("04-catalog-workflows.jpg", "Workflows filter with sales and AP cards", "full"),
        "__SHOT_DRAWER__": img("05-catalog-sales-drawer.jpg", "Sales cycle drawer with snapshot and GL posting", "full"),
        "__SHOT_TENANTS__": img("03-catalog-tenants.jpg", "Nine demo tenant catalog cards", "full"),
        "__SHOT_TB__": img("07-trial-balance.jpg", "Trial Balance report", "full"),
        "__SHOT_INV__": img("08-invoices.jpg", "Invoices list", "full"),
        "__SHOT_OPS__": img("09-ops-home.jpg", "Manufacturing operations dashboard", "full"),
        "__SHOT_DEMAND__": img("10-demands.jpg", "Purchase demands", "full"),
        "__SHOT_OPD__": img("11-opd.jpg", "Hospital OPD", "full"),
        "__SHOT_SPIN__": img("12-spinning-lots.jpg", "Yarn spinning lots", "full"),
        "__SHOT_REPORTS__": img("06-catalog-reports.jpg", "Catalog reports filter", "full"),
        "__SHOT_SCREENS__": img("06b-catalog-screens.jpg", "Catalog screens filter", "full"),
    }
    for key, val in replacements.items():
        html = html.replace(key, val)
    OUT_DOCS.write_text(html, encoding="utf-8")
    OUT_PUBLIC.parent.mkdir(parents=True, exist_ok=True)
    OUT_PUBLIC.write_text(html, encoding="utf-8")
    kb = OUT_DOCS.stat().st_size / 1024
    print(f"wrote {OUT_DOCS} ({kb:.0f} KB)")
    print(f"wrote {OUT_PUBLIC} ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
