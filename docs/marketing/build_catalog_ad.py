#!/usr/bin/env python3
"""Build a standalone Workflow Catalog explorer HTML.

Embeds catalog JSON (search / filters / drawers). Snapshots load from a sibling
`catalog/` folder or `/catalog/` when the file is served by Easy-Books.

Writes:
  docs/marketing/catalog-advertisement.html
  frontend/public/catalog-advertisement.html
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
INDEX_CANDIDATES = [
    ROOT / "catalog-index.json",
    REPO / "frontend" / "public" / "catalog" / "index.json",
]
OUT_DOCS = ROOT / "catalog-advertisement.html"
OUT_PUBLIC = REPO / "frontend" / "public" / "catalog-advertisement.html"


def load_index() -> dict:
    for path in INDEX_CANDIDATES:
        if path.exists():
            return json.loads(path.read_text())
    raise SystemExit("catalog-index.json missing — run frontend vitest workflowCatalog.test.ts first")


DATA = load_index()
ENTRIES_JSON = json.dumps(DATA["entries"], ensure_ascii=False)
KIND_COUNTS = {}
for e in DATA["entries"]:
    KIND_COUNTS[e["kind"]] = KIND_COUNTS.get(e["kind"], 0) + 1
KIND_COUNTS["all"] = len(DATA["entries"])

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Easy-Books · Workflow Catalog explorer</title>
<meta name="description" content="Explore every Easy-Books demo tenant, segment, workflow, form, subform, report and screen — with snapshots and GL notes. Standalone HTML." />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Serif+Display:ital@0;1&display=swap" rel="stylesheet" />
<style>
  :root {
    --cream: #f6f3ee; --paper: #fffdf8; --gold: #b8943f; --gold-dark: #7a5c1e;
    --charcoal: #1a1814; --muted: rgba(26,24,20,.62); --line: rgba(26,24,20,.12); --ink: #1a1814;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html { scroll-behavior: smooth; }
  body { font-family: "DM Sans", ui-sans-serif, system-ui, sans-serif; background: var(--cream); color: var(--ink); line-height: 1.55; }
  img { max-width: 100%; height: auto; display: block; }
  a { color: var(--gold-dark); }
  .wrap { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
  header.top { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 24px; max-width: 1200px; margin: 0 auto; flex-wrap: wrap; }
  .brand { display: flex; align-items: center; gap: 10px; text-decoration: none; color: inherit; }
  .mark { width: 36px; height: 36px; border-radius: 10px; background: var(--gold); font-family: "DM Serif Display", Georgia, serif; font-size: 20px; display: grid; place-items: center; font-weight: 700; }
  .chip { font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; color: var(--gold-dark); background: rgba(184,148,63,.16); border: 1px solid rgba(184,148,63,.35); padding: 6px 10px; border-radius: 999px; }
  .hero { padding: 36px 0 12px; }
  .hero h1 { font-family: "DM Serif Display", Georgia, serif; font-size: clamp(32px, 5vw, 56px); font-weight: 400; line-height: 1.08; max-width: 18ch; }
  .hero h1 em { font-style: italic; color: var(--gold-dark); }
  .lede { margin-top: 16px; max-width: 62ch; font-size: 17px; color: var(--muted); }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; margin: 28px 0 18px; }
  .stat { background: var(--paper); border: 1px solid var(--line); border-radius: 14px; padding: 14px 12px; }
  .stat strong { display: block; font-size: 24px; font-family: "DM Serif Display", Georgia, serif; }
  .stat span { font-size: 11px; color: var(--muted); font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
  .note { font-size: 13px; color: var(--muted); margin-bottom: 18px; }
  .filters { position: sticky; top: 0; z-index: 20; background: rgba(246,243,238,.94); backdrop-filter: blur(8px); padding: 12px 0 10px; border-bottom: 1px solid var(--line); }
  .search { width: 100%; padding: 12px 14px; border-radius: 12px; border: 1px solid var(--line); background: #fff; font: inherit; font-size: 15px; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
  .pill { border: 1px solid var(--line); background: #fff; border-radius: 999px; padding: 6px 12px; font-size: 12px; font-weight: 600; cursor: pointer; color: var(--ink); }
  .pill.on { background: var(--charcoal); color: #fff; border-color: var(--charcoal); }
  .pill.gold.on { background: var(--gold); color: var(--charcoal); border-color: var(--gold); }
  .muted { font-size: 12px; color: var(--muted); margin: 14px 0; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; padding-bottom: 80px; }
  .card { background: #fff; border: 1px solid var(--line); border-radius: 16px; overflow: hidden; cursor: pointer; text-align: left; font: inherit; color: inherit; display: flex; flex-direction: column; }
  .card:hover { border-color: var(--gold); box-shadow: 0 10px 28px rgba(26,24,20,.08); }
  .thumb { aspect-ratio: 16/9; background: #efeae0; overflow: hidden; }
  .thumb img { width: 100%; height: 100%; object-fit: cover; object-position: top; }
  .ph { width: 100%; height: 100%; display: grid; place-items: center; font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: rgba(26,24,20,.35); font-weight: 700; }
  .card body, .body { padding: 12px 14px 14px; }
  .kicker { display: flex; justify-content: space-between; gap: 8px; align-items: start; }
  .title { font-size: 14px; font-weight: 700; }
  .kind { font-size: 9px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; padding: 3px 6px; border-radius: 6px; background: #efeae0; }
  .kind.tenant { background: #1a1814; color: #fff; }
  .kind.segment { background: #e0e7ff; color: #3730a3; }
  .kind.workflow { background: rgba(184,148,63,.2); color: #7a5c1e; }
  .kind.form { background: #fef3c7; color: #92400e; }
  .kind.subform { background: #ede9fe; color: #5b21b6; }
  .kind.report { background: #d1fae5; color: #065f46; }
  .kind.screen { background: #e0f2fe; color: #075985; }
  .blurb { font-size: 12px; color: var(--muted); margin-top: 6px; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
  .tag { font-size: 10px; background: var(--cream); padding: 2px 6px; border-radius: 999px; color: var(--muted); }
  .drawer-bg { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 80; display: none; }
  .drawer-bg.on { display: block; }
  aside.drawer { position: fixed; top: 0; right: 0; height: 100%; width: min(560px, 100%); background: #fff; z-index: 90; overflow: auto; box-shadow: -16px 0 40px rgba(26,24,20,.12); transform: translateX(100%); transition: transform .2s ease; }
  aside.drawer.on { transform: none; }
  .dhead { position: sticky; top: 0; background: #fff; border-bottom: 1px solid var(--line); padding: 14px 18px; display: flex; justify-content: space-between; gap: 12px; }
  .shotfull { width: 100%; background: #efeae0; cursor: zoom-in; }
  .shotfull img { width: 100%; }
  .dpad { padding: 18px; }
  .steps { margin: 14px 0; padding-left: 18px; }
  .steps li { margin: 6px 0; font-size: 14px; }
  .gl { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; background: var(--cream); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
  .x { border: 0; background: var(--cream); width: 32px; height: 32px; border-radius: 8px; cursor: pointer; font-size: 18px; }
  .lightbox { position: fixed; inset: 0; background: rgba(0,0,0,.85); z-index: 100; display: none; align-items: center; justify-content: center; padding: 16px; }
  .lightbox.on { display: flex; }
  .lightbox img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 8px; }
  footer { border-top: 1px solid var(--line); padding: 28px 0 48px; color: var(--muted); font-size: 13px; }
  .demo { margin: 8px 0 0; font-size: 13px; }
  .demo code { background: #fff; padding: 1px 6px; border-radius: 4px; border: 1px solid var(--line); }
</style>
</head>
<body>
<header class="top">
  <a class="brand" href="#explore"><span class="mark">E</span><b>Easy-Books</b></a>
  <span class="chip">Standalone catalog explorer</span>
</header>
<main>
  <section class="wrap hero">
    <h1>Every tenant, form, and report — <em>photographed and explained.</em></h1>
    <p class="lede">
      This page is a full product explorer for Easy-Books: nine demo companies, every nav segment,
      end-to-end workflows, create/edit/print forms, Studio subforms, and statutory plus industry reports.
      Open a card for the snapshot, the posting story, and how a clerk actually runs the screen.
    </p>
    <p class="demo">Demo password for every seeded company: <code>demo1234</code>
      · e.g. <code>demo.services@easy-books.app</code>, <code>demo.manufacturing@easy-books.app</code>,
      <code>demo.hospital@easy-books.app</code>, <code>demo.spinning@easy-books.app</code>.</p>
    <div class="stats" id="stats"></div>
    <p class="note">Snapshots live in a <code>catalog/</code> folder next to this HTML (or at <code>/catalog/</code> on a running Easy-Books server). The catalog JSON is embedded — search and filters work even if pictures are still pending.</p>
  </section>

  <div class="filters" id="explore">
    <div class="wrap">
      <input class="search" id="q" type="search" placeholder="Search invoices, Studio, spinning lots, ZATCA, trial balance…" />
      <div class="row" id="kinds"></div>
      <div class="row" id="tenants"></div>
      <div class="row" id="tags"></div>
    </div>
  </div>

  <div class="wrap">
    <p class="muted" id="count"></p>
    <div class="grid" id="grid"></div>
  </div>
</main>
<div class="drawer-bg" id="backdrop"></div>
<aside class="drawer" id="drawer"></aside>
<div class="lightbox" id="lightbox"></div>
<footer>
  <div class="wrap">
    Easy-Books · double-entry bookkeeping for SMEs. Settings → Catalog is the in-app twin of this page.
    Studio (Settings → Studio) customises invoice/bill/customer/product/vendor fields, form layout, and print HTML — those tabs are catalogued here as subforms.
  </div>
</footer>
<script id="catalog-data" type="application/json">__ENTRIES_JSON__</script>
<script>
const ENTRIES = JSON.parse(document.getElementById("catalog-data").textContent);
const TENANT_LABEL = {
  simple: "Simple", services: "Services", trader: "Trader", manufacturing: "Manufacturing",
  telecom: "Telecom", pra: "PRA", hospital: "Hospital", spinning: "Spinning", processing: "Processing"
};
const KIND_LABEL = { all: "All", tenant: "Tenants", segment: "Segments", workflow: "Workflows", form: "Forms", subform: "Subforms", report: "Reports", screen: "Screens" };
const KINDS = ["all","tenant","segment","workflow","form","subform","report","screen"];

function shotBases() {
  const path = (location.pathname || "").replace(/\\/g, "/");
  const bases = ["catalog/", "/catalog/"];
  if (path.includes("/docs/marketing/") || path.includes("/marketing/")) {
    bases.unshift("../../frontend/public/catalog/");
  }
  return bases;
}
const SHOT_BASES = shotBases();

function shotUrl(shot) {
  return SHOT_BASES[0] + shot + ".jpg";
}

const state = { kind: "all", tenant: "all", tag: null, q: "", active: null, light: false };

function counts(list) {
  const c = { all: list.length };
  for (const k of KINDS) if (k !== "all") c[k] = list.filter(e => e.kind === k).length;
  return c;
}

function filtered() {
  const q = state.q.trim().toLowerCase();
  return ENTRIES.filter(e => {
    if (state.kind !== "all" && e.kind !== state.kind) return false;
    if (state.tenant !== "all" && !(e.tenants || []).includes(state.tenant)) return false;
    if (state.tag && !(e.tags || []).includes(state.tag)) return false;
    if (!q) return true;
    const blob = [e.title, e.explanation, (e.tags||[]).join(" "), e.segment, e.href, e.gl || ""].join(" ").toLowerCase();
    return q.split(/\s+/).filter(Boolean).every(t => blob.includes(t));
  });
}

function allTags() {
  const map = new Map();
  for (const e of ENTRIES) for (const t of (e.tags || [])) map.set(t, (map.get(t) || 0) + 1);
  return [...map.entries()].sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]));
}

function thumb(e) {
  const src = shotUrl(e.shot);
  return `<div class="thumb"><img alt="" src="${src}" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'ph',textContent:'Snapshot pending'}))" /></div>`;
}

function renderFilters() {
  const base = ENTRIES.filter(e => {
    if (state.tenant !== "all" && !(e.tenants||[]).includes(state.tenant)) return false;
    if (state.tag && !(e.tags||[]).includes(state.tag)) return false;
    return true;
  });
  const c = counts(base);
  document.getElementById("kinds").innerHTML = KINDS.map(k =>
    `<button class="pill ${state.kind===k?"on":""}" data-kind="${k}">${KIND_LABEL[k]} <span style="opacity:.6">${c[k]||0}</span></button>`
  ).join("");
  document.getElementById("tenants").innerHTML =
    `<button class="pill gold ${state.tenant==="all"?"on":""}" data-tenant="all">All companies</button>` +
    Object.keys(TENANT_LABEL).map(t =>
      `<button class="pill gold ${state.tenant===t?"on":""}" data-tenant="${t}">${TENANT_LABEL[t]}</button>`
    ).join("");
  document.getElementById("tags").innerHTML = allTags().map(([t,n]) =>
    `<button class="pill ${state.tag===t?"on":""}" data-tag="${t}">${t} ${n}</button>`
  ).join("");
}

function renderGrid() {
  const items = filtered();
  document.getElementById("count").textContent = items.length + " " + (items.length===1?"entry":"entries")
    + (state.tag ? ` tagged “${state.tag}”` : "")
    + (state.tenant !== "all" ? " · " + TENANT_LABEL[state.tenant] : "");
  document.getElementById("grid").innerHTML = items.map(e => `
    <button class="card" data-id="${e.id}">
      ${thumb(e)}
      <div class="body">
        <div class="kicker">
          <div class="title">${escapeHtml(e.title)}</div>
          <span class="kind ${e.kind}">${e.kind}</span>
        </div>
        <p class="blurb">${escapeHtml(e.explanation)}</p>
        <div class="tags">${(e.tags||[]).slice(0,4).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
      </div>
    </button>
  `).join("");
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
}

function openDrawer(id) {
  const e = ENTRIES.find(x => x.id === id);
  if (!e) return;
  state.active = e;
  const steps = (e.steps && e.steps.length)
    ? `<ol class="steps">${e.steps.map(s => `<li>${escapeHtml(s)}</li>`).join("")}</ol>` : "";
  const gl = e.gl ? `<p class="gl">${escapeHtml(e.gl)}</p>` : "";
  document.getElementById("drawer").innerHTML = `
    <div class="dhead">
      <div>
        <div class="kind ${e.kind}">${e.kind} · ${escapeHtml(e.segment)}</div>
        <strong>${escapeHtml(e.title)}</strong>
      </div>
      <button class="x" id="close" aria-label="Close">×</button>
    </div>
    <div class="shotfull" id="zoom">${thumb(e)}</div>
    <div class="dpad">
      <p>${escapeHtml(e.explanation)}</p>
      ${steps}
      ${gl}
      <div class="tags" style="margin:12px 0">${(e.tags||[]).map(t => `<span class="tag">${escapeHtml(t)}</span>`).join("")}</div>
      <p class="muted">Shown on: ${(e.tenants||[]).map(t => TENANT_LABEL[t] || t).join(", ")} · Modules: ${(e.modules||[]).join(", ")}</p>
      <p class="muted">Live path: <code>${escapeHtml(e.href)}</code></p>
    </div>`;
  document.getElementById("drawer").classList.add("on");
  document.getElementById("backdrop").classList.add("on");
  document.getElementById("close").onclick = closeDrawer;
  document.getElementById("zoom").onclick = () => {
    const src = shotUrl(e.shot);
    document.getElementById("lightbox").innerHTML = `<img alt="${escapeHtml(e.title)}" src="${src}" />`;
    document.getElementById("lightbox").classList.add("on");
  };
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("on");
  document.getElementById("backdrop").classList.remove("on");
  state.active = null;
}

function renderStats() {
  const c = counts(ENTRIES);
  document.getElementById("stats").innerHTML = [
    ["all","Entries"],["tenant","Tenants"],["segment","Segments"],["workflow","Workflows"],
    ["form","Forms"],["subform","Subforms"],["report","Reports"],["screen","Screens"]
  ].map(([k,l]) => `<div class="stat"><strong>${c[k]||0}</strong><span>${l}</span></div>`).join("");
}

document.getElementById("q").addEventListener("input", ev => { state.q = ev.target.value; renderGrid(); });
document.getElementById("kinds").addEventListener("click", ev => {
  const b = ev.target.closest("[data-kind]"); if (!b) return;
  state.kind = b.getAttribute("data-kind"); renderFilters(); renderGrid();
});
document.getElementById("tenants").addEventListener("click", ev => {
  const b = ev.target.closest("[data-tenant]"); if (!b) return;
  const t = b.getAttribute("data-tenant");
  state.tenant = state.tenant === t ? "all" : t;
  renderFilters(); renderGrid();
});
document.getElementById("tags").addEventListener("click", ev => {
  const b = ev.target.closest("[data-tag]"); if (!b) return;
  const t = b.getAttribute("data-tag");
  state.tag = state.tag === t ? null : t;
  renderFilters(); renderGrid();
});
document.getElementById("backdrop").onclick = closeDrawer;
document.getElementById("lightbox").onclick = () => document.getElementById("lightbox").classList.remove("on");
document.getElementById("grid").addEventListener("click", ev => {
  const b = ev.target.closest("[data-id]"); if (!b) return;
  openDrawer(b.getAttribute("data-id"));
});
document.addEventListener("keydown", ev => {
  if (ev.key === "Escape") { closeDrawer(); document.getElementById("lightbox").classList.remove("on"); }
});

renderStats();
renderFilters();
renderGrid();
</script>
</body>
</html>
"""

html = HTML.replace("__ENTRIES_JSON__", ENTRIES_JSON)
OUT_DOCS.write_text(html)
OUT_PUBLIC.write_text(html)
print(f"wrote {OUT_DOCS} ({OUT_DOCS.stat().st_size // 1024} KB)")
print(f"wrote {OUT_PUBLIC} ({OUT_PUBLIC.stat().st_size // 1024} KB)")
print(f"entries {KIND_COUNTS['all']} kinds {KIND_COUNTS}")
