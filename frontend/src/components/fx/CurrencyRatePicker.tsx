'use client'

import { useState } from 'react'
import { Loader2, RefreshCw } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { CURRENCIES } from '@/lib/fx'

export interface CurrencyRatePickerProps {
  currency: string
  exchangeRate: string
  baseCurrency: string
  /** Document date used for live-rate lookup (YYYY-MM-DD). */
  onDate?: string
  onCurrencyChange: (currency: string) => void
  onRateChange: (rate: string) => void
  /** Called after a successful live fetch with source label. */
  onRateFetched?: (info: { rate: number; date: string; source: string }) => void
  className?: string
}

export default function CurrencyRatePicker({
  currency,
  exchangeRate,
  baseCurrency,
  onDate,
  onCurrencyChange,
  onRateChange,
  onRateFetched,
  className = '',
}: CurrencyRatePickerProps) {
  const [fetchingRate, setFetchingRate] = useState(false)
  const [rateError, setRateError] = useState('')
  const [rateSource, setRateSource] = useState('')
  const isBase = currency.toUpperCase() === baseCurrency.toUpperCase()

  const fetchLiveRate = async (fromCurrency: string, date?: string) => {
    if (fromCurrency.toUpperCase() === baseCurrency.toUpperCase()) return
    setFetchingRate(true)
    setRateError('')
    setRateSource('')
    const qs = `from_currency=${fromCurrency}&to_currency=${baseCurrency}${date || onDate ? `&on_date=${date ?? onDate}` : ''}`
    try {
      const data = await apiFetch<{ rate: number; date: string; source: string }>(
        `/api/exchange-rates/live?${qs}`,
      )
      onRateChange(String(data.rate))
      setRateSource(`${data.date} · ${data.source}`)
      onRateFetched?.(data)
    } catch (e) {
      setRateError(e instanceof Error ? e.message : 'Failed to fetch rate')
    } finally {
      setFetchingRate(false)
    }
  }

  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 gap-4 ${className}`}>
      <div>
        <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
          Currency
        </label>
        <select
          value={currency}
          onChange={e => {
            const cur = e.target.value
            setRateError('')
            setRateSource('')
            onCurrencyChange(cur)
            if (cur.toUpperCase() === baseCurrency.toUpperCase()) {
              onRateChange('1')
            } else {
              void fetchLiveRate(cur)
            }
          }}
          className="w-full px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm"
        >
          {Array.from(new Set([baseCurrency, ...CURRENCIES])).sort().map(c => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-xs font-bold uppercase tracking-widest text-[var(--text-primary)]/75 mb-1">
          Exchange Rate (1 {currency} = ? {baseCurrency})
        </label>
        <div className="flex gap-2">
          <input
            type="number"
            step="0.0001"
            min="0"
            value={exchangeRate}
            onChange={e => onRateChange(e.target.value)}
            disabled={isBase}
            className="flex-1 px-3 py-2 bg-[var(--bg-page)] rounded-xl outline-none focus:ring-2 focus:ring-[var(--primary)] text-sm disabled:opacity-50"
          />
          <button
            type="button"
            onClick={() => fetchLiveRate(currency)}
            disabled={isBase || fetchingRate}
            title="Fetch live rate from ECB via Frankfurter"
            className="px-3 py-2 bg-[var(--bg-page)] border border-[var(--border)] rounded-xl text-[var(--primary)] hover:bg-[var(--primary)]/10 disabled:opacity-40 transition-colors"
          >
            {fetchingRate ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          </button>
        </div>
        {rateError && <p className="text-xs text-red-500 mt-1">{rateError}</p>}
        {rateSource && !rateError && <p className="text-xs text-[var(--text-muted)] mt-1">{rateSource}</p>}
      </div>
    </div>
  )
}
