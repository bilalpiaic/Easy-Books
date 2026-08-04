import { describe, expect, it } from "vitest"
import {
  defaultGrid,
  migrateToV4,
  packItems,
  toV4Payload,
  type Meta,
} from "@/lib/dashboardLayoutLogic"
import {
  defaultViewForModel,
  hasOperationsHome,
  operationsSubtitle,
} from "@/lib/dashboardHome"

const baseMeta = (mods: string[], model?: string): Meta => ({
  model,
  role: "owner",
  installedModules: new Set(mods),
})

describe("dashboardHome helpers", () => {
  it("hides Operations when only base/hrm are installed", () => {
    expect(hasOperationsHome(new Set(["base"]))).toBe(false)
    expect(hasOperationsHome(new Set(["base", "hrm"]))).toBe(false)
    expect(hasOperationsHome(new Set(["base", "purchase_store"]))).toBe(true)
    expect(hasOperationsHome(new Set(["base", "spinning"]))).toBe(true)
  })

  it("defaults ops-heavy models to Operations", () => {
    expect(defaultViewForModel("yarn_spinning")).toBe("operations")
    expect(defaultViewForModel("manufacturing")).toBe("operations")
    expect(defaultViewForModel("hospital")).toBe("operations")
    expect(defaultViewForModel("simple")).toBe("financial")
    expect(defaultViewForModel("services")).toBe("financial")
    expect(defaultViewForModel("trader")).toBe("financial")
  })

  it("labels operations subtitle from modules", () => {
    expect(operationsSubtitle(new Set(["spinning"]), "yarn_spinning")).toBe("Spinning Operations")
    expect(operationsSubtitle(new Set(["healthcare"]), "hospital")).toBe("Healthcare Operations")
    expect(operationsSubtitle(new Set(["purchase_store"]))).toBe("Purchases & Store")
  })
})

describe("defaultGrid packs", () => {
  it("financial defaults exclude ops-only widgets", () => {
    const ids = defaultGrid("financial", new Set(["base", "inventory", "hrm"])).map(i => i.id)
    expect(ids).toContain("primary_kpis")
    expect(ids).toContain("hrm_summary")
    expect(ids).not.toContain("ops_primary_kpis")
    expect(ids).not.toContain("spinning_summary")
  })

  it("operations defaults include ops widgets, charts, and module tiles", () => {
    const ids = defaultGrid(
      "operations",
      new Set(["base", "inventory", "purchase_store", "spinning"]),
    ).map(i => i.id)
    expect(ids).toContain("ops_primary_kpis")
    expect(ids).toContain("ops_pipeline")
    expect(ids).toContain("ops_process_chart")
    expect(ids).toContain("ops_trend_chart")
    expect(ids).toContain("ops_status_table")
    expect(ids).toContain("ops_mix_chart")
    expect(ids).toContain("spinning_summary")
    expect(ids).toContain("purchases_pipeline")
    expect(ids).toContain("quick_actions")
    expect(ids).not.toContain("primary_kpis")
    expect(ids).not.toContain("monthly_rev_exp")
  })

  it("packItems wraps at 4 columns", () => {
    const packed = packItems([
      { id: "a", w: 2, h: 1 },
      { id: "b", w: 2, h: 1 },
      { id: "c", w: 2, h: 1 },
    ])
    expect(packed[0]).toMatchObject({ id: "a", x: 0, y: 0 })
    expect(packed[1]).toMatchObject({ id: "b", x: 2, y: 0 })
    expect(packed[2]).toMatchObject({ id: "c", x: 0, y: 1 })
  })
})

describe("migrateToV4", () => {
  it("wraps v3 financial layout and seeds operations defaults", () => {
    const v3 = {
      version: 3 as const,
      layouts: { lg: [{ id: "primary_kpis", x: 0, y: 0, w: 4, h: 1 }] },
      dismissed: ["day_book"],
      quickActions: ["new_invoice", "new_bill"],
    }
    const meta = baseMeta(["base", "spinning"], "yarn_spinning")
    const v4 = migrateToV4(v3, meta)
    expect(v4.version).toBe(4)
    expect(v4.financial.layouts.lg.some(i => i.id === "primary_kpis")).toBe(true)
    expect(v4.financial.dismissed).toContain("day_book")
    expect(v4.financial.quickActions).toEqual(["new_invoice", "new_bill"])
    expect(v4.operations.layouts.lg.some(i => i.id === "ops_primary_kpis")).toBe(true)
    expect(v4.operations.layouts.lg.some(i => i.id === "spinning_summary")).toBe(true)
  })

  it("round-trips via toV4Payload", () => {
    const meta = baseMeta(["base", "telecom"], "telecom_franchise")
    const migrated = migrateToV4(null, meta)
    const payload = toV4Payload(migrated.financial, migrated.operations, "operations")
    expect(payload.version).toBe(4)
    expect(payload.activeView).toBe("operations")
    const again = migrateToV4(payload, meta)
    expect(again.operations.layouts.lg.map(i => i.id)).toEqual(
      migrated.operations.layouts.lg.map(i => i.id),
    )
  })

  it("migrates null to dual defaults", () => {
    const meta = baseMeta(["base"])
    const v4 = migrateToV4(null, meta)
    expect(v4.financial.layouts.lg.length).toBeGreaterThan(0)
    expect(v4.operations.layouts.lg.some(i => i.id === "ops_primary_kpis")).toBe(true)
  })
})
