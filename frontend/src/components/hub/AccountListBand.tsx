"use client"
import Link from "next/link"
import { useFmt } from "@/context/SettingsContext"
import { useTranslation } from "react-i18next"

export interface BankAccountRow {
  id: number
  name: string
  balance: number
}

export interface AccountListBandProps {
  accounts: BankAccountRow[]
}

export default function AccountListBand({ accounts }: AccountListBandProps) {
  const { t } = useTranslation()

  const fmt = useFmt()
  const sorted = [...accounts].sort((a, b) => b.balance - a.balance)
  const shown = sorted.slice(0, 5)
  const overflow = sorted.length - 5

  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/40 mb-2">
        Account Balances
      </div>
      <div className="flex flex-col gap-1.5">
        {shown.map(acc => (
          <div
            key={acc.id}
            className="flex justify-between items-center bg-[#f8f5ef] rounded-lg px-2.5 py-1.5"
          >
            <span className="text-xs text-[#1a1814] truncate">{acc.name}</span>
            <span className="text-xs font-bold text-[#1a1814] ml-2 shrink-0">{fmt(acc.balance)}</span>
          </div>
        ))}
        {overflow > 0 && (
          <Link
            href="/bank-accounts"
            className="text-[10px] text-[#b8943f] hover:underline text-right mt-0.5"
          >
            +{overflow} more →
          </Link>
        )}
      </div>
    </div>
  )
}
