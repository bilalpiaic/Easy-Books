import { describe, expect, it } from 'vitest'
import {
  effectiveRate,
  fxGainLossLabel,
  isForeignCurrency,
  previewRealisedFx,
  toBase,
} from './fx'

describe('fx helpers (#300)', () => {
  it('prefers carrying_rate over exchange_rate', () => {
    expect(effectiveRate({ exchange_rate: 280, carrying_rate: 290 })).toBe(290)
    expect(effectiveRate({ exchange_rate: 280 })).toBe(280)
  })

  it('detects foreign currency case-insensitively', () => {
    expect(isForeignCurrency('usd', 'PKR')).toBe(true)
    expect(isForeignCurrency('pkr', 'PKR')).toBe(false)
  })

  it('converts to base', () => {
    expect(toBase(100, { exchange_rate: 280 })).toBe(28000)
  })

  it('previews realised FX for receipts', () => {
    const p = previewRealisedFx({
      paymentAmount: 100,
      settlementRate: 290,
      allocations: [{ amount: 100, carryingRate: 280 }],
    })
    expect(p.cashBase).toBe(29000)
    expect(p.clearedBase).toBe(28000)
    expect(p.realised).toBe(1000)
    expect(fxGainLossLabel(p.realised, 'receipt')).toContain('gain')
  })
})
