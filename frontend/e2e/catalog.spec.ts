import { test, expect } from "@playwright/test"
import { DEMO_PASSWORD, loginAs } from "./helpers"

test.describe("workflow catalog", () => {
  test("settings catalog lists tenants, tags, and opens a card", async ({ page }) => {
    await loginAs(page, "demo.services@easy-books.app", DEMO_PASSWORD)
    await page.goto("/settings")
    await page.getByRole("button", { name: /^Catalog$/ }).click()
    await expect(page).toHaveURL(/\/settings\/catalog/)
    await expect(page.locator("h1", { hasText: "Workflow catalog" })).toBeVisible()
    await expect(page.getByRole("button", { name: /^Tenants/ })).toBeVisible()
    await expect(page.getByRole("button", { name: /simple company/i })).toBeVisible()

    await page.getByRole("button", { name: /^Workflows/ }).click()
    await expect(page.getByRole("button", { name: /sales cycle/i })).toBeVisible()

    await page.locator("[data-kind='all']").click()
    await page.getByPlaceholder(/search invoices/i).fill("trial balance")
    await page.getByRole("heading", { name: "Trial Balance", exact: true }).click()
    await expect(page.locator("aside").getByRole("heading", { name: "Trial Balance" })).toBeVisible()
    await expect(page.getByRole("link", { name: /open live screen/i })).toBeVisible()
  })

  test("public explorer HTML is reachable without login and honors tenant deep-link", async ({ page }) => {
    await page.goto("/catalog-advertisement.html?tenant=spinning")
    await expect(page.locator("h1")).toContainText(/every tenant, form, and report/i)
    await expect(page.locator("#count")).toContainText(/Spinning/)
    await expect(page).toHaveURL(/tenant=spinning/)
    const img = page.locator(".grid .thumb img").first()
    await expect(img).toBeVisible()
    await expect.poll(async () => img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0)
  })
})
