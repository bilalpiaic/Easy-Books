import { describe, expect, it } from "vitest"
import { mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs"
import { join, resolve } from "node:path"
import { NAV, TOP_NAV } from "../nav"
import {
  CATALOG,
  DEMO_TENANTS,
  catalogCaptureJobs,
  catalogScreenshot,
  filterCatalog,
  slugHref,
  shotKey,
} from "../workflowCatalog"
import { DEEP_ENTRIES } from "../workflowCatalogDeep"

describe("workflow catalog", () => {
  it("has unique ids", () => {
    const ids = CATALOG.map(e => e.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it("covers all nine demo tenants", () => {
    const tenantIds = CATALOG.filter(e => e.kind === "tenant").map(e => e.id)
    expect(tenantIds).toEqual(Object.keys(DEMO_TENANTS).map(k => `tenant-${k}`))
  })

  it("covers every top-nav segment", () => {
    const segs = new Set(CATALOG.filter(e => e.kind === "segment").map(e => e.id))
    for (const s of TOP_NAV) {
      expect(segs.has(`segment-${s.key}`)).toBe(true)
    }
  })

  it("covers every unique NAV href as a screen or report", () => {
    const hrefs = new Set(
      CATALOG.filter(e => e.kind === "screen" || e.kind === "report" || e.kind === "form" || e.kind === "subform")
        .map(e => (e.capturePath ?? e.href).split("?")[0].replace(/\{[^}]+\}/g, "")),
    )
    const missing: string[] = []
    const seen = new Set<string>()
    for (const item of NAV) {
      if (seen.has(item.href)) continue
      seen.add(item.href)
      const base = item.href.split("?")[0]
      if (![...hrefs].some(h => h === base || h.replace(/\/$/, "") === base)) missing.push(item.href)
    }
    expect(missing).toEqual([])
  })

  it("includes form, subform, and Studio entries", () => {
    expect(CATALOG.some(e => e.kind === "form")).toBe(true)
    expect(CATALOG.some(e => e.kind === "subform")).toBe(true)
    const studio = CATALOG.filter(e => e.href.includes("/settings/studio"))
    expect(studio.length).toBeGreaterThanOrEqual(12)
    expect(studio.some(e => e.href.includes("tab=fields") && e.href.includes("entity=invoice"))).toBe(true)
    expect(studio.some(e => e.href.includes("tab=forms"))).toBe(true)
    expect(studio.some(e => e.href.includes("tab=print"))).toBe(true)
    expect(DEEP_ENTRIES.length).toBeGreaterThan(80)
  })

  it("covers static dashboard routes and parameterized templates", () => {
    const skip = new Set(["/uae-logs"])
    const catalogRoutes = new Set(
      CATALOG.map(e => {
        const p = (e.capturePath ?? e.href).split("?")[0]
        return p.replace("{id}", "[id]").replace("{eid}", "[eid]")
      }),
    )
    const root = resolve(__dirname, "../../app/(dashboard)")
    const routes: string[] = []
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const full = join(dir, name)
        if (statSync(full).isDirectory()) walk(full)
        else if (name === "page.tsx") {
          const rel = full.slice(root.length).replace(/\\/g, "/").replace(/\/page\.tsx$/, "")
          routes.push(rel || "/dashboard")
        }
      }
    }
    walk(root)
    const missing = routes
      .map(r => (r.startsWith("/") ? r : `/${r}`.replace(/\/+/g, "/")))
      .filter(href => !skip.has(href) && !catalogRoutes.has(href))
    expect(missing).toEqual([])
  })

  it("gives every entry a title, explanation, tags, and capture tenant", () => {
    for (const e of CATALOG) {
      expect(e.title.length).toBeGreaterThan(2)
      expect(e.explanation.length).toBeGreaterThan(40)
      expect(e.tags.length).toBeGreaterThan(0)
      expect(e.tenants.length).toBeGreaterThan(0)
      expect(e.captureTenant).toBeTruthy()
      expect(catalogScreenshot(e)).toMatch(/^\/catalog\/.+--.+\.jpg$/)
    }
  })

  it("keeps workflow explanations actionable", () => {
    const wfs = CATALOG.filter(e => e.kind === "workflow")
    expect(wfs.length).toBeGreaterThanOrEqual(15)
    for (const e of wfs) {
      expect(e.steps?.length ?? 0).toBeGreaterThanOrEqual(3)
    }
  })

  it("filters by kind, tag, tenant, and search", () => {
    const sales = filterCatalog({ kind: "workflow", tag: "sales" })
    expect(sales.every(e => e.kind === "workflow" && e.tags.includes("sales"))).toBe(true)
    const mill = filterCatalog({ tenant: "manufacturing", kind: "tenant" })
    expect(mill).toHaveLength(1)
    expect(mill[0].id).toBe("tenant-manufacturing")
    const q = filterCatalog({ q: "zatca" })
    expect(q.some(e => e.title.toLowerCase().includes("zatca") || e.explanation.toLowerCase().includes("zatca"))).toBe(true)
  })

  it("slugifies hrefs without empty or slash characters", () => {
    expect(slugHref("/purchases/three-way-match")).toBe("purchases-three-way-match")
    expect(slugHref("/settings?tab=advanced")).toBe("settings-tab-advanced")
    expect(slugHref("/invoices/{id}/print")).toBe("invoices-id-print")
    expect(slugHref("/")).toBe("home")
  })

  it("dedupes capture jobs by tenant+path", () => {
    const jobs = catalogCaptureJobs()
    const keys = jobs.map(j => `${j.tenant}::${j.path}`)
    expect(new Set(keys).size).toBe(keys.length)
    expect(jobs.some(j => j.tenant === "anon" && j.path === "/login")).toBe(true)
    expect(jobs.some(j => j.path.includes("{id}"))).toBe(true)
    expect(jobs.some(j => j.path.includes("/settings/studio?tab=fields"))).toBe(true)
    writeFileSync(
      resolve(__dirname, "../../../e2e/catalog-shots.json"),
      JSON.stringify(jobs, null, 2) + "\n",
    )
    const slim = CATALOG.map(e => ({
      id: e.id,
      title: e.title,
      kind: e.kind,
      href: e.href,
      explanation: e.explanation,
      steps: e.steps,
      gl: e.gl,
      tags: e.tags,
      tenants: e.tenants,
      modules: e.modules,
      segment: e.segment,
      shot: shotKey(e),
    }))
    mkdirSync(resolve(__dirname, "../../../public/catalog"), { recursive: true })
    writeFileSync(
      resolve(__dirname, "../../../public/catalog/index.json"),
      JSON.stringify({ generated: new Date().toISOString().slice(0, 10), entries: slim }, null, 2) + "\n",
    )
    writeFileSync(
      resolve(__dirname, "../../../../docs/marketing/catalog-index.json"),
      JSON.stringify({ generated: new Date().toISOString().slice(0, 10), entries: slim }) + "\n",
    )
  })
})
