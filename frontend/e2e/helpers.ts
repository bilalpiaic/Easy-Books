import { type Page, expect } from "@playwright/test"

export const DEMO_PASSWORD = "demo1234"
export const OWNER_EMAIL = "demo.manufacturing@easy-books.app"
export const ACCOUNTANT_EMAIL = "demo.manufacturing+accountant@easy-books.app"

/** Login via the email/password form and wait for the dashboard shell. */
export async function loginAs(page: Page, email: string, password = DEMO_PASSWORD) {
  // Owners/admins hit the in-app update checker; on CI that modal (z-600)
  // sits on top of Approve buttons and flakes the purchase-chain walk.
  await page.route("**/api/system/update/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "up_to_date",
        local: "e2e",
        remote: null,
        behind: false,
      }),
    })
  })

  await page.goto("/login")
  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/\/dashboard/, { timeout: 30_000 })
  // ModuleContext fetch — purchase_store nav appears after this
  await page.waitForTimeout(1600)
  // Belt-and-suspenders if a prior session already opened the popup
  const later = page.getByRole("button", { name: /^Later$/ })
  if (await later.isVisible().catch(() => false)) {
    await later.click()
  }
  await expect(page.locator("body")).toBeVisible()
}

export async function logoutViaClear(page: Page) {
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
}
