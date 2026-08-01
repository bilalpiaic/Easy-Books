import { test, expect } from "@playwright/test"
import {
  ACCOUNTANT_EMAIL,
  OWNER_EMAIL,
  loginAs,
  logoutViaClear,
} from "./helpers"

/**
 * Happy path: demand → quotation → comparative → PO → gate inward.
 * Uses accountant (create) + owner (approve) to satisfy self-approval rules.
 * Requires manufacturing demo tenant with purchase_store (seed_demo).
 */
test.describe("purchase chain", () => {
  test("demand through gate inward", async ({ page }) => {
    const purpose = `E2E steel restock ${Date.now()}`

    // ── 1. Accountant creates a demand ──────────────────────────────────────
    await loginAs(page, ACCOUNTANT_EMAIL)
    await page.goto("/purchases/demands/new")
    await expect(page.getByRole("heading", { name: /new purchase demand/i })).toBeVisible({
      timeout: 30_000,
    })

    await page.getByPlaceholder("What is this requisition for?").fill(purpose)
    const row = page.locator("table tbody tr").first()
    await row.locator("td").nth(1).locator("input").fill("E2E Mild Steel Plate")
    await row.locator("td").nth(2).locator("input").fill("5")
    await row.locator("td").nth(3).locator("input").fill("kg")

    await page.getByRole("button", { name: /save demand/i }).click()
    await page.waitForURL(/\/purchases\/demands\/\d+/, { timeout: 30_000 })
    const demandUrl = page.url()
    await expect(page.locator("dd").filter({ hasText: /^draft$/i })).toBeVisible()

    // ── 2. Owner approves (segregation of duties) ───────────────────────────
    await logoutViaClear(page)
    await loginAs(page, OWNER_EMAIL)
    await page.goto(demandUrl)
    await page.getByRole("button", { name: /^Approve$/ }).click()
    await expect(page.locator("dd").filter({ hasText: /^approved$/i })).toBeVisible({
      timeout: 20_000,
    })

    // ── 3. Accountant adds a quotation ──────────────────────────────────────
    await logoutViaClear(page)
    await loginAs(page, ACCOUNTANT_EMAIL)
    await page.goto(demandUrl)
    await page.getByRole("link", { name: /new quotation/i }).click()
    await page.waitForURL(/\/purchases\/demands\/\d+\/quotations\/new/)
    await expect(page.getByRole("heading", { name: /new quotation/i })).toBeVisible({
      timeout: 30_000,
    })

    // Vendor <select> — blank option first; wait until seeded vendors hydrate
    const vendorSelect = page.locator("select").first()
    await expect(vendorSelect.locator("option").nth(1)).toBeAttached({ timeout: 20_000 })
    await vendorSelect.selectOption({ index: 1 })

    await page.getByPlaceholder("0.00").first().fill("125.50")
    await page.getByRole("button", { name: /save quotation/i }).click()
    await page.waitForURL(/\/purchases\/demands\/\d+/, { timeout: 30_000 })

    // ── 4. Create comparative, select + justify ───────────────────────────
    await page.getByRole("button", { name: /create comparative/i }).click()
    await page.waitForURL(/\/purchases\/comparatives\/\d+/, { timeout: 30_000 })
    const csUrl = page.url()

    await page.locator('input[type="radio"][name="winner"]').first().check()
    await page.getByPlaceholder(/why this vendor/i).fill("E2E single-quote justification")
    await page.getByRole("button", { name: /save selection/i }).click()
    await page.waitForTimeout(1000)

    // Owner approves CS
    await logoutViaClear(page)
    await loginAs(page, OWNER_EMAIL)
    await page.goto(csUrl)
    await page.getByRole("button", { name: /^Approve$/ }).click()
    await expect(page.getByText(/^approved$/i).first()).toBeVisible({ timeout: 20_000 })

    // ── 5. Convert to PO, then approve (GI requires approved/received) ──────
    await page.getByRole("button", { name: /convert to po/i }).click()
    await page.waitForURL(/\/manufacturing\/purchase-orders\/\d+/, { timeout: 30_000 })
    const poUrl = page.url()
    const poId = poUrl.match(/purchase-orders\/(\d+)/)?.[1]
    expect(poId).toBeTruthy()

    await page.getByRole("button", { name: /approve po/i }).click()
    await expect(page.getByText(/^approved$/i).first()).toBeVisible({ timeout: 20_000 })

    // ── 6. Gate inward against the PO ───────────────────────────────────────
    await page.goto(`/purchases/gate-inward/new?po=${poId}`)
    await expect(page.getByRole("heading", { name: /new gate inward/i })).toBeVisible({
      timeout: 30_000,
    })
    // Wait until the PO is selected in the dropdown (list is approved-only)
    await expect(page.locator("select").first()).not.toHaveValue("", { timeout: 20_000 })
    // PO lines auto-load from ?po=; qty_received prefilled with remaining
    await page.getByRole("button", { name: /save gate inward/i }).click()
    await page.waitForURL(/\/purchases\/gate-inward\/\d+/, { timeout: 30_000 })
    await expect(page.getByRole("heading").first()).toBeVisible()
  })
})
