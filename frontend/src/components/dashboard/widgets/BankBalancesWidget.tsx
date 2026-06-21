"use client"

import { useEffect, useState } from "react"
import { useFmt } from "@/context/SettingsContext"
import { apiFetch } from "@/lib/api"
import { useTranslation } from "react-i18next"

interface BankAccountRow { id: number; name: string; bank_name?: string | null; balance: number | string }

export default function BankBalancesWidget() {
  const { t } = useTranslation()

  const fmt = useFmt()
  const [rows, setRows] = useState<BankAccountRow[] | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiFetch<BankAccountRow[]>("/api/bank-accounts")
      .then(setRows)
      .catch(() => setError(true))
  }, [])

  const total = rows ? rows.reduce((s, r) => s + Number(r.balance), 0) : 0

  return (
    <div className="h-full flex flex-col bg-white border border-[#ede9e2] rounded-xl p-4 shadow-sm">
      <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/55 mb-2">Bank Balances</p>
      {error ? (
        <div className="text-sm text-red-600">Failed to load.</div>
      ) : !rows ? (
        <div className="shimmer h-20 rounded-lg" />
      ) : rows.length === 0 ? (
        <div className="text-sm text-[#1a1814]/40">No bank accounts.</div>
      ) : (
        <>
          <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1">
            {rows.map(r => (
              <div key={r.id} className="flex items-center justify-between gap-2 py-1.5 border-b border-[#ede9e2] last:border-0 text-sm">
                <span className="truncate text-[#1a1814]/80">{r.name}</span>
                <span className="font-medium tabular-nums whitespace-nowrap">{fmt(Number(r.balance))}</span>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between pt-2 mt-1 border-t-2 border-[#b8943f]/30 text-sm font-bold">
            <span>{t('col.total', 'Total')}</span>
            <span className="tabular-nums">{fmt(total)}</span>
          </div>
        </>
      )}
    </div>
  )
}
