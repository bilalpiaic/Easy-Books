import { describe, expect, it } from "vitest"
import { writeFileSync } from "node:fs"
import { resolve } from "node:path"
import { NAV, TOP_NAV } from "../nav"
import {
  CATALOG,
  DEMO_TENANTS,
  catalogCaptureJobs,
  catalogScreenshot,
  filterCatalog,
  slugHref,
} from "../workflowCatalog"

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
      CATALOG.filter(e => e.kind === "screen" || e.kind === "report").map(e => e.href.split("?")[0]),
    )
    const missing: string[] = []
    const seen = new Set<string>()
    for (const item of NAV) {
      if (seen.has(item.href)) continue
      seen.add(item.href)
      if (!hrefs.has(item.href)) missing.push(item.href)
    }
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
    expect(slugHref("/")).toBe("home")
  })

  it("dedupes capture jobs by tenant+path", () => {
    const jobs = catalogCaptureJobs()
    const keys = jobs.map(j => `${j.tenant}::${j.path}`)
    expect(new Set(keys).size).toBe(keys.length)
    expect(jobs.some(j => j.tenant === "anon" && j.path === "/login")).toBe(true)
    writeFileSync(
      resolve(__dirname, "../../../e2e/catalog-shots.json"),
      JSON.stringify(jobs, null, 2) + "\n",
    )
  })
})
