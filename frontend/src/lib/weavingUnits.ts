/** Shared Kg → Lbs → Bags conversion (mirrors backend services.weaving_calc). */
export const KG_TO_LB = 2.2046226218

export type WeightTriple = { kg: number; lbs: number; bags: number }

export function weightTriple(kg: number | string | null | undefined): WeightTriple {
  const k = Number(kg) || 0
  const lbs = k * KG_TO_LB
  return { kg: k, lbs, bags: lbs / 100 }
}

export function ratePerLb(ratePerKg: number | string | null | undefined): number {
  const r = Number(ratePerKg) || 0
  if (!r) return 0
  return r / KG_TO_LB
}

export function fmtWeight(n: number | undefined | null, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—"
  return Number(n).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

/** Display "Kg | Lbs | Bags" for a weight triple from the API. */
export function formatWeightTriple(t: WeightTriple | { kg?: number; lbs?: number; bags?: number } | null | undefined): string {
  if (!t) return "—"
  return `${fmtWeight(t.kg)} kg · ${fmtWeight(t.lbs)} lb · ${fmtWeight(t.bags)} bags`
}
