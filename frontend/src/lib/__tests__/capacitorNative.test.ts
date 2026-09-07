import { describe, expect, it } from "vitest"
import { isCapacitorNative } from "../capacitorNative"

describe("isCapacitorNative", () => {
  it("is false without a window", () => {
    expect(isCapacitorNative(undefined)).toBe(false)
  })

  it("is false on a normal browser window", () => {
    const fake = { Capacitor: undefined } as unknown as Window
    expect(isCapacitorNative(fake)).toBe(false)
  })

  it("is true when Capacitor reports a native platform", () => {
    const fake = { Capacitor: { isNativePlatform: () => true } } as unknown as Window
    expect(isCapacitorNative(fake)).toBe(true)
  })
})
