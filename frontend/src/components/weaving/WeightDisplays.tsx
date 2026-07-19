"use client"

import { fmtWeight, formatWeightTriple, ratePerLb, type WeightTriple } from "@/lib/weavingUnits"

/** Read-only Kg | Lbs | Bags display next to a kg amount. */
export function WeightTripleDisplay({
  kg,
  lbs,
  bags,
  triple,
}: {
  kg?: number
  lbs?: number
  bags?: number
  triple?: WeightTriple | null
}) {
  const t = triple ?? { kg: kg ?? 0, lbs: lbs ?? 0, bags: bags ?? 0 }
  return (
    <span className="text-xs text-[var(--muted)] whitespace-nowrap" title={formatWeightTriple(t)}>
      {fmtWeight(t.kg)} kg · {fmtWeight(t.lbs)} lb · {fmtWeight(t.bags)} bags
    </span>
  )
}

/** Rate/Kg with derived Rate/Lb. */
export function RateKgLb({ ratePerKg, ratePerLbValue }: { ratePerKg?: number; ratePerLbValue?: number }) {
  const perKg = ratePerKg ?? 0
  const perLb = ratePerLbValue ?? ratePerLb(perKg)
  return (
    <span className="text-xs whitespace-nowrap">
      <span className="font-medium">{fmtWeight(perKg, 4)}</span>
      <span className="text-[var(--muted)]"> /kg</span>
      <span className="text-[var(--muted)] mx-1">·</span>
      <span className="font-medium">{fmtWeight(perLb, 4)}</span>
      <span className="text-[var(--muted)]"> /lb</span>
    </span>
  )
}
