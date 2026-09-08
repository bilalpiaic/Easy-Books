import { test } from "@playwright/test"
import { existsSync, mkdirSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { DEMO_PASSWORD, loginAs } from "./helpers"

/**
 * Captures JPEG snapshots for Settings → Catalog.
 * Run with: CAPTURE_CATALOG=1 npx playwright test e2e/capture-catalog.spec.ts
 * Skips files that already exist unless CAPTURE_CATALOG_FORCE=1.
 */
const ENABLED = process.env.CAPTURE_CATALOG === "1"
const FORCE = process.env.CAPTURE_CATALOG_FORCE === "1"
const ROOT = process.cwd()
const OUT = resolve(ROOT, "public/catalog")
const SHOTS_FILE = resolve(ROOT, "e2e/catalog-shots.json")
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

type Job = {
  id: string
  path: string
  tenant: string
  idFrom?: string
  idFrom2?: string
  idField?: string
}
type TenantKey = Exclude<Job["tenant"], "anon">

const EMAIL: Record<TenantKey, string> = {
  simple: "demo.simple@easy-books.app",
  services: "demo.services@easy-books.app",
  trader: "demo.trader@easy-books.app",
  manufacturing: "demo.manufacturing@easy-books.app",
  telecom: "demo.telecom@easy-books.app",
  pra: "demo.pra@easy-books.app",
  hospital: "demo.hospital@easy-books.app",
  spinning: "demo.spinning@easy-books.app",
  processing: "demo.processing@easy-books.app",
}

function loadJobs(): Job[] {
  try {
    return JSON.parse(readFileSync(SHOTS_FILE, "utf8")) as Job[]
  } catch {
    return []
  }
}

function jobsByTenant(list: Job[]): [string, Job[]][] {
  const map = new Map<string, Job[]>()
  for (const job of list) {
    const arr = map.get(job.tenant) ?? []
    arr.push(job)
    map.set(job.tenant, arr)
  }
  return [...map.entries()]
}

function firstRow(data: unknown): Record<string, unknown> | null {
  if (!data) return null
  if (Array.isArray(data)) return (data[0] as Record<string, unknown>) ?? null
  if (typeof data === "object") {
    const o = data as Record<string, unknown>
    for (const key of ["items", "runs", "data", "results", "tickets", "lots"]) {
      if (Array.isArray(o[key]) && (o[key] as unknown[]).length) {
        return (o[key] as Record<string, unknown>[])[0]
      }
    }
  }
  return null
}

async function firstId(
  page: import("@playwright/test").Page,
  apiPath: string,
  field = "id",
): Promise<string | null> {
  const token = await page.evaluate(() => localStorage.getItem("access_token"))
  if (!token) return null
  const url = apiPath.startsWith("http") ? apiPath : `${API}${apiPath}`
  const res = await page.request.get(url, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!res.ok()) return null
  const data = await res.json().catch(() => null)
  const row = firstRow(data)
  if (!row) return null
  const raw = row[field] ?? row.id ?? row.transaction_id
  return raw == null ? null : String(raw)
}

async function resolvePath(
  page: import("@playwright/test").Page,
  job: Job,
): Promise<string | null> {
  let path = job.path
  if (!path.includes("{id}") && !path.includes("{eid}")) return path
  if (!job.idFrom) return null
  const id = await firstId(page, job.idFrom, job.idField || "id")
  if (!id) return null
  path = path.replaceAll("{id}", id)
  if (path.includes("{eid}")) {
    const eid = job.idFrom2
      ? await firstId(page, job.idFrom2, "id")
      : null
    if (!eid) return null
    path = path.replaceAll("{eid}", eid)
  }
  return path
}

test.describe("catalog snapshots", () => {
  test.skip(!ENABLED, "set CAPTURE_CATALOG=1 to recapture")

  const jobs = ENABLED ? loadJobs() : []

  test("login screen", async ({ page }) => {
    mkdirSync(OUT, { recursive: true })
    await page.setViewportSize({ width: 1440, height: 900 })
    const job = jobs.find(j => j.tenant === "anon")
    if (!job) return
    const dest = resolve(OUT, `${job.id}.jpg`)
    if (existsSync(dest) && !FORCE) return
    await page.goto("/login")
    await page.waitForTimeout(800)
    await page.screenshot({ path: dest, type: "jpeg", quality: 72 })
  })

  for (const [tenant, tenantJobs] of jobsByTenant(jobs.filter(j => j.tenant !== "anon"))) {
    test(`tenant ${tenant}`, async ({ page }) => {
      mkdirSync(OUT, { recursive: true })
      await page.setViewportSize({ width: 1440, height: 900 })
      const email = EMAIL[tenant as TenantKey]
      await loginAs(page, email, DEMO_PASSWORD)
      test.setTimeout(20 * 60_000)
      for (const job of tenantJobs) {
        const dest = resolve(OUT, `${job.id}.jpg`)
        if (existsSync(dest) && !FORCE) continue
        try {
          const path = await resolvePath(page, job)
          if (!path) {
            console.warn(`skip ${tenant} ${job.path}: no id`)
            continue
          }
          await page.goto(path, { waitUntil: "domcontentloaded", timeout: 25_000 })
          await page.waitForTimeout(1400)
          const later = page.getByRole("button", { name: /^Later$/ })
          if (await later.isVisible().catch(() => false)) await later.click()
          const close = page.getByRole("button", { name: /^Close$/ })
          if (await close.isVisible().catch(() => false)) {
            const label = await close.getAttribute("aria-label")
            if (label === "Close") await close.click()
          }
          await page.screenshot({ path: dest, type: "jpeg", quality: 72 })
        } catch (err) {
          console.warn(`skip ${tenant} ${job.path}:`, err)
        }
      }
    })
  }
})
