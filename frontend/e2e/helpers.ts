import { type Page, expect } from "@playwright/test"

export const DEMO_PASSWORD = "demo1234"
export const OWNER_EMAIL = "demo.manufacturing@easy-books.app"
export const ACCOUNTANT_EMAIL = "demo.manufacturing+accountant@easy-books.app"

/** Login via the email/password form and wait for the dashboard shell. */
export async function loginAs(page: Page, email: string, password = DEMO_PASSWORD) {
  await page.goto("/login")
  await page.locator('input[type="email"]').fill(email)
  await page.locator('input[type="password"]').fill(password)
  await page.locator('button[type="submit"]').click()
  await page.waitForURL(/\/dashboard/, { timeout: 30_000 })
  // ModuleContext fetch — purchase_store nav appears after this
  await page.waitForTimeout(1600)
  await expect(page.locator("body")).toBeVisible()
}

export async function logoutViaClear(page: Page) {
  await page.evaluate(() => {
    localStorage.clear()
    sessionStorage.clear()
  })
}
