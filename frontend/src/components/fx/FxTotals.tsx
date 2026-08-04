'use client'

import { effectiveRate, isForeignCurrency, toBase } from '@/lib/fx'

interface Props {
  amount: number
  currency?: string | null
  exchangeRate?: number | string | null
  carryingRate?: number | string | null
  baseCurrency: string
  fmt: (n: number) => string
  label?: string
}

/** Totals line: Total (CCY) + ≈ base when foreign. */
export default function FxTotals({
  amount,
  currency,
  exchangeRate,
  carryingRate,
  baseCurrency,
  fmt,
  label = 'Total',
}: Props) {
  const ccy = currency || baseCurrency
  const foreign = isForeignCurrency(ccy, baseCurrency)
  const rate = effectiveRate({ exchange_rate: exchangeRate, carrying_rate: carryingRate })
  return (
    <div className="space-y-1">
      <div className="flex justify-between font-bold">
        <span>{label} ({ccy})</span>
        <span className="font-mono">{fmt(amount)}</span>
      </div>
      {foreign && (
        <div className="flex justify-between text-xs text-[var(--text-muted)]">
          <span>≈ {baseCurrency} @ {rate}</span>
          <span className="font-mono">
            {fmt(toBase(amount, { exchange_rate: exchangeRate, carrying_rate: carryingRate }))}
          </span>
        </div>
      )}
    </div>
  )
}
