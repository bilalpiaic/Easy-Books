import { afterEach, describe, expect, it, vi } from "vitest"

describe("networkErrorMessage", () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.resetModules()
  })

  it("rewrites Failed to fetch into a reachable-API hint", async () => {
    const { networkErrorMessage } = await import("../api")
    const msg = networkErrorMessage(new TypeError("Failed to fetch"))
    expect(msg).not.toBe("Failed to fetch")
    expect(msg).toMatch(/Can't reach the API/)
  })

  it("calls out mixed content when an HTTPS page points at http:// API", async () => {
    vi.stubGlobal("window", { location: { protocol: "https:" } })
    vi.resetModules()
    const { networkErrorMessage } = await import("../api")
    const msg = networkErrorMessage(new TypeError("Failed to fetch"))
    expect(msg).toMatch(/mixed content/i)
    expect(msg).toMatch(/NEXT_PUBLIC_API_URL/)
  })

  it("passes through non-network errors", async () => {
    const { networkErrorMessage } = await import("../api")
    expect(networkErrorMessage(new Error("Too many reset requests"))).toBe(
      "Too many reset requests",
    )
  })
})
