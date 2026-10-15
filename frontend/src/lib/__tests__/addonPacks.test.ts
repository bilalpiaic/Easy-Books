import { describe, expect, it } from "vitest"
import {
  ADDON_PACKS,
  ADDON_PACK_GROUPS,
  MODULE_CATEGORY_ORDER,
} from "../addonPacks"

describe("addon packs by category of use", () => {
  it("lists recommended groups in industry → localization → intelligence order", () => {
    expect(ADDON_PACK_GROUPS.map(g => g.id)).toEqual([
      "industry",
      "localization",
      "intelligence",
    ])
  })

  it("keeps country packs out of the business-nature group", () => {
    const loc = ADDON_PACKS.filter(p => p.group === "localization").map(p => p.id)
    expect(loc).toEqual([
      "pra",
      "uae_vat",
      "sa_zatca",
      "in_gst",
      "eu_peppol",
      "uk_mtd",
      "my_invois",
    ])
    const industry = ADDON_PACKS.filter(p => p.group === "industry").map(p => p.id)
    expect(industry).toEqual([
      "trader",
      "manufacturing",
      "yarn_spinning",
      "textile_processing",
      "healthcare",
      "telecom",
    ])
    expect(ADDON_PACKS.filter(p => p.group === "intelligence").map(p => p.id)).toEqual(["ai"])
  })

  it("orders Optional categories with Localization beside Industry, before Intelligence", () => {
    expect([...MODULE_CATEGORY_ORDER]).toEqual([
      "Core",
      "Operations",
      "HR",
      "Industry",
      "Localization",
      "Intelligence",
    ])
  })

  it("assigns every pack a known group", () => {
    const groups = new Set(ADDON_PACK_GROUPS.map(g => g.id))
    for (const pack of ADDON_PACKS) {
      expect(groups.has(pack.group)).toBe(true)
      expect(pack.modules.length).toBeGreaterThan(0)
      expect(pack.features.length).toBeGreaterThan(0)
    }
  })

  it("preinstalls weighbridge on mill packs, not hospital or telecom", () => {
    const byId = Object.fromEntries(ADDON_PACKS.map(p => [p.id, p.modules]))
    expect(byId.manufacturing).toContain("weighbridge")
    expect(byId.yarn_spinning).toContain("weighbridge")
    expect(byId.textile_processing).toContain("weighbridge")
    expect(byId.trader).not.toContain("weighbridge")
    expect(byId.healthcare).not.toContain("weighbridge")
    expect(byId.telecom).not.toContain("weighbridge")
  })

  it("injects PLC Shop Floor via mill Add-on packs, not hospital or telecom", () => {
    const byId = Object.fromEntries(ADDON_PACKS.map(p => [p.id, p.modules]))
    expect(byId.manufacturing).toContain("shop_floor")
    expect(byId.yarn_spinning).toContain("shop_floor")
    expect(byId.textile_processing).toContain("shop_floor")
    expect(byId.trader).not.toContain("shop_floor")
    expect(byId.healthcare).not.toContain("shop_floor")
    expect(byId.telecom).not.toContain("shop_floor")
  })
})
