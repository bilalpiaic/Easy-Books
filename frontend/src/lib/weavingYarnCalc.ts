/** Weaving / sizing yarn planning calculators (#196) — mirrors backend weaving_yarn_calc. */
import { KG_TO_LB, weightTriple, type WeightTriple } from "./weavingUnits"

export const LB_TO_KG = 1 / KG_TO_LB

export type WeavingCalcInput = {
  epi: number
  ppi: number
  width_in: number
  length_yd: number
  warp_ne: number
  weft_ne: number
  warp_crimp_pct?: number
  weft_crimp_pct?: number
  visible_waste_pct?: number
  invisible_waste_pct?: number
}

export type SizingCalcInput = {
  unsized_kg: number
  pickup_pct?: number
  stretch_pct?: number
  visible_waste_pct?: number
  invisible_waste_pct?: number
}

export type WeavingCalcResult = {
  warp_lbs: number
  weft_lbs: number
  total_lbs: number
  warp_kg: number
  weft_kg: number
  total_kg: number
  waste_factor: number
  net_lbs_before_waste: number
  warp_ne: number
  weft_ne: number
  warp: WeightTriple
  weft: WeightTriple
  total: WeightTriple
  net_before_waste: WeightTriple
}

export type SizingCalcResult = {
  unsized_kg: number
  net_before_waste_kg: number
  gross_kg: number
  waste_factor: number
  total_kg: number
  unsized: WeightTriple
  net_before_waste: WeightTriple
  gross: WeightTriple
  total: WeightTriple
}

function wasteFactor(vis = 0, inv = 0): number {
  return 1 + (Number(vis) || 0) / 100 + (Number(inv) || 0) / 100
}

function legLbs(
  ends: number,
  width: number,
  length: number,
  crimpPct: number,
  waste: number,
  ne: number,
): number {
  const n = Number(ne) || 0
  if (!n) return 0
  const crimp = 1 + (Number(crimpPct) || 0) / 100
  return ((Number(ends) || 0) * (Number(width) || 0) * (Number(length) || 0) * crimp * waste) / (840 * n)
}

function round2(n: number): number {
  return Math.round(n * 100) / 100
}

export function calculateWeaving(input: WeavingCalcInput): WeavingCalcResult {
  const waste = wasteFactor(input.visible_waste_pct, input.invisible_waste_pct)
  const warp_lbs = legLbs(input.epi, input.width_in, input.length_yd, input.warp_crimp_pct ?? 0, waste, input.warp_ne)
  const weft_lbs = legLbs(input.ppi, input.width_in, input.length_yd, input.weft_crimp_pct ?? 0, waste, input.weft_ne)
  const total_lbs = warp_lbs + weft_lbs
  const warp_kg = warp_lbs * LB_TO_KG
  const weft_kg = weft_lbs * LB_TO_KG
  const total_kg = total_lbs * LB_TO_KG
  const net_lbs = waste ? total_lbs / waste : 0
  return {
    warp_lbs: round2(warp_lbs),
    weft_lbs: round2(weft_lbs),
    total_lbs: round2(total_lbs),
    warp_kg: round2(warp_kg),
    weft_kg: round2(weft_kg),
    total_kg: round2(total_kg),
    waste_factor: waste,
    net_lbs_before_waste: round2(net_lbs),
    warp_ne: Number(input.warp_ne) || 0,
    weft_ne: Number(input.weft_ne) || 0,
    warp: weightTriple(warp_kg),
    weft: weightTriple(weft_kg),
    total: weightTriple(total_kg),
    net_before_waste: weightTriple(net_lbs * LB_TO_KG),
  }
}

export function calculateSizing(input: SizingCalcInput): SizingCalcResult {
  const unsized = Number(input.unsized_kg) || 0
  const pickup = 1 + (Number(input.pickup_pct) || 0) / 100
  const stretch = 1 + (Number(input.stretch_pct) || 0) / 100
  const waste = wasteFactor(input.visible_waste_pct, input.invisible_waste_pct)
  const net = unsized * pickup * stretch
  const gross = net * waste
  return {
    unsized_kg: round2(unsized),
    net_before_waste_kg: round2(net),
    gross_kg: round2(gross),
    waste_factor: waste,
    total_kg: round2(gross),
    unsized: weightTriple(unsized),
    net_before_waste: weightTriple(net),
    gross: weightTriple(gross),
    total: weightTriple(gross),
  }
}
