import { describe, expect, it } from "vitest"
import { calculateWeaving, calculateSizing, LB_TO_KG } from "../weavingYarnCalc"

describe("calculateWeaving", () => {
  it("matches the Ne worked example", () => {
    const r = calculateWeaving({
      epi: 60,
      ppi: 50,
      width_in: 60,
      length_yd: 1000,
      warp_ne: 40,
      weft_ne: 30,
      warp_crimp_pct: 10,
      weft_crimp_pct: 5,
      visible_waste_pct: 3,
      invisible_waste_pct: 1,
    })
    expect(r.warp_lbs).toBeCloseTo(122.57, 1)
    expect(r.weft_lbs).toBeCloseTo(130, 1)
    expect(r.total_lbs).toBeCloseTo(252.57, 1)
    expect(r.warp_kg).toBeCloseTo(122.5714 * LB_TO_KG, 1)
    expect(r.waste_factor).toBeCloseTo(1.04, 5)
    expect(r.total.kg).toBeGreaterThan(0)
    expect(r.total.bags).toBeGreaterThan(0)
  })

  it("returns 0 warp when Ne is 0", () => {
    const r = calculateWeaving({
      epi: 60, ppi: 50, width_in: 60, length_yd: 1000,
      warp_ne: 0, weft_ne: 30,
    })
    expect(r.warp_lbs).toBe(0)
    expect(r.weft_lbs).toBeGreaterThan(0)
  })
})

describe("calculateSizing", () => {
  it("matches pickup/stretch/waste example", () => {
    const r = calculateSizing({
      unsized_kg: 100,
      pickup_pct: 12,
      stretch_pct: 1.5,
      visible_waste_pct: 0.7,
      invisible_waste_pct: 1.0,
    })
    expect(r.net_before_waste_kg).toBeCloseTo(113.68, 1)
    expect(r.gross_kg).toBeCloseTo(115.61, 1)
    expect(r.gross.bags).toBeGreaterThan(0)
  })
})
