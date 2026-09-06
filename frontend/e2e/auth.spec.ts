import { test, expect } from "@playwright/test"
import { DEMO_PASSWORD, loginAs } from "./helpers"

test.describe("auth", () => {
  test("demo login reaches dashboard", async ({ page }) => {
    await loginAs(page, "demo.simple@easy-books.app", DEMO_PASSWORD)
    await expect(page).toHaveURL(/\/dashboard/)
    // Bottom or top nav should show once authenticated
    await expect(page.getByText(/Easy-Books|Dashboard|Home/i).first()).toBeVisible()
  })

  test("invalid credentials stay on login", async ({ page }) => {
    await page.goto("/login")
    await page.locator('input[type="email"]').fill("nobody@example.com")
    await page.locator('input[type="password"]').fill("wrong-password")
    await page.locator('button[type="submit"]').click()
    await expect(page.getByText(/invalid email or password/i)).toBeVisible({ timeout: 15_000 })
    await expect(page).toHaveURL(/\/login/)
  })

  test("login offers forgot password", async ({ page }) => {
    await page.goto("/login")
    await page.getByRole("link", { name: /forgot password/i }).click()
    await expect(page).toHaveURL(/\/forgot-password/)
    await expect(page.getByRole("button", { name: /send reset link/i })).toBeVisible()
  })
})
