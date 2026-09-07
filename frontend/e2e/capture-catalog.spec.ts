import { test } from "@playwright/test"
import { mkdirSync, readFileSync } from "node:fs"
import { resolve } from "node:path"
import { DEMO_PASSWORD, loginAs } from "./helpers"

/**
 * Captures JPEG snapshots for Settings → Catalog.
 * Run with: CAPTURE_CATALOG=1 npx playwright test e2e/capture-catalog.spec.ts
 * Skipped in normal CI / e2e runs.
 */
const ENABLED = process.env.CAPTURE_CATALOG === "1"
const ROOT = process.cwd()
const OUT = resolve(ROOT, "public/catalog")
const SHOTS_FILE = resolve(ROOT, "e2e/catalog-shots.json")

type Job = { id: string; path: string; tenant: string }
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

test.describe("catalog snapshots", () => {
  test.skip(!ENABLED, "set CAPTURE_CATALOG=1 to recapture")

  const jobs = ENABLED ? loadJobs() : []

  test("login screen", async ({ page }) => {
    mkdirSync(OUT, { recursive: true })
    await page.setViewportSize({ width: 1440, height: 900 })
    await page.goto("/login")
    await page.waitForTimeout(800)
    const job = jobs.find(j => j.tenant === "anon")
    if (job) {
      await page.screenshot({
        path: resolve(OUT, `${job.id}.jpg`),
        type: "jpeg",
        quality: 72,
      })
    }
  })

  for (const [tenant, tenantJobs] of jobsByTenant(jobs.filter(j => j.tenant !== "anon"))) {
    test(`tenant ${tenant}`, async ({ page }) => {
      mkdirSync(OUT, { recursive: true })
      await page.setViewportSize({ width: 1440, height: 900 })
      const email = EMAIL[tenant as TenantKey]
      await loginAs(page, email, DEMO_PASSWORD)
      test.setTimeout(15 * 60_000)
      for (const job of tenantJobs) {
        try {
          await page.goto(job.path, { waitUntil: "domcontentloaded", timeout: 25_000 })
          await page.waitForTimeout(1200)
          const later = page.getByRole("button", { name: /^Later$/ })
          if (await later.isVisible().catch(() => false)) await later.click()
          await page.screenshot({
            path: resolve(OUT, `${job.id}.jpg`),
            type: "jpeg",
            quality: 72,
          })
        } catch (err) {
          console.warn(`skip ${tenant} ${job.path}:`, err)
        }
      }
    })
  }
})
