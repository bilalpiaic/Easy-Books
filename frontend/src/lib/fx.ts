/** Shared multi-currency / FX display helpers (#300). */

export const CURRENCIES = [
  'AED', 'AUD', 'BDT', 'BHD', 'CAD', 'CHF', 'CNY', 'EUR', 'GBP',
  'HKD', 'IDR', 'INR', 'JPY', 'KWD', 'MYR', 'OMR', 'PKR', 'QAR',
  'SAR', 'SGD', 'THB', 'TRY', 'USD', 'ZAR',
] as const

export function effectiveRate(doc: {
  exchange_rate?: number | string | null
  carrying_rate?: number | string | null
}): number {
  const carrying = doc.carrying_rate != null ? Number(doc.carrying_rate) : NaN
  if (Number.isFinite(carrying) && carrying > 0) return carrying
  const rate = doc.exchange_rate != null ? Number(doc.exchange_rate) : NaN
  if (Number.isFinite(rate) && rate > 0) return rate
  return 1
}

export function isForeignCurrency(
  currency: string | null | undefined,
  baseCurrency: string | null | undefined,
): boolean {
  if (!currency) return false
  const base = (baseCurrency || 'USD').toUpperCase()
  return currency.toUpperCase() !== base
}

export function toBase(
  amount: number,
  doc: { exchange_rate?: number | string | null; carrying_rate?: number | string | null },
): number {
  return Math.round(amount * effectiveRate(doc) * 100) / 100
}

/** Preview realised FX for a settlement (mirrors payment_fx.build_settlement). */
export function previewRealisedFx(opts: {
  paymentAmount: number
  settlementRate: number
  allocations: Array<{ amount: number; carryingRate: number }>
}): { cashBase: number; clearedBase: number; realised: number } {
  const settle = opts.settlementRate > 0 ? opts.settlementRate : 1
  const cashBase = Math.round(opts.paymentAmount * settle * 100) / 100
  const clearedBase = Math.round(
    opts.allocations.reduce((s, a) => s + a.amount * (a.carryingRate > 0 ? a.carryingRate : 1), 0) * 100,
  ) / 100
  return {
    cashBase,
    clearedBase,
    realised: Math.round((cashBase - clearedBase) * 100) / 100,
  }
}

export function fxGainLossLabel(realised: number, side: 'receipt' | 'bill_payment' = 'receipt'): string {
  if (Math.abs(realised) < 0.005) return 'No FX gain/loss'
  // Receipts: cash_base > cleared → gain. Bill payments: cash_base < cleared → gain (paid less in base).
  const isGain = side === 'receipt' ? realised > 0 : realised < 0
  const abs = Math.abs(realised)
  return isGain ? `FX gain ${abs.toFixed(2)}` : `FX loss ${abs.toFixed(2)}`
}
