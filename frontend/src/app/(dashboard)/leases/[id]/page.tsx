"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"
import { ArrowLeft, Play, Ban, Printer } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useMessages } from "@/context/MessageContext"
import PrintHeader from "@/components/PrintHeader"
import { fmtDate } from "@/lib/utils"

interface ScheduleLine {
  id: number
  period_index: number
  period_date: string
  opening_liability: number
  interest: number
  payment: number
  principal: number
  closing_liability: number
  depreciation: number
  status: string
}

interface LeaseDetail {
  id: number
  number: string
  name: string
  lessor: string | null
  commencement_date: string
  term_months: number
  payment_amount: number
  annual_discount_rate: number
  present_value: number
  rou_cost: number
  liability_carrying: number
  accumulated_depreciation: number
  rou_nbv: number
  status: string
  schedule: ScheduleLine[]
}

export default function LeaseDetailPage() {
  const params = useParams()
  const id = Number(params.id)
  const fmt = useFmt()
  const { toast, confirm } = useMessages()
  const [lease, setLease] = useState<LeaseDetail | null>(null)
  const [busy, setBusy] = useState(false)

  async function load() {
    const d = await apiFetch<LeaseDetail>(`/api/leases/${id}`)
    setLease(d)
  }

  useEffect(() => {
    if (!id) return
    load().catch((err: unknown) => toast(err instanceof Error ? err.message : "Load failed", "error"))
  }, [id])

  async function activate() {
    setBusy(true)
    try {
      await apiFetch(`/api/leases/${id}/activate`, { method: "POST" })
      toast("Lease activated", "success")
      await load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Activate failed", "error")
    } finally {
      setBusy(false)
    }
  }

  async function postPeriod(periodIndex: number) {
    setBusy(true)
    try {
      await apiFetch(`/api/leases/${id}/periods/${periodIndex}/post`, { method: "POST" })
      toast(`Period ${periodIndex} posted`, "success")
      await load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Post failed", "error")
    } finally {
      setBusy(false)
    }
  }

  async function terminate() {
    const ok = await confirm({
      title: "Terminate this lease?",
      message: "Clears remaining RoU NBV and liability to P&L (simplified IFRS 16 path).",
      confirmLabel: "Terminate",
      danger: true,
    })
    if (!ok) return
    setBusy(true)
    try {
      await apiFetch(`/api/leases/${id}/terminate`, {
        method: "POST",
        body: JSON.stringify({ termination_date: new Date().toISOString().slice(0, 10) }),
      })
      toast("Lease terminated", "success")
      await load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : "Terminate failed", "error")
    } finally {
      setBusy(false)
    }
  }

  if (!lease) return <p className="text-sm text-[var(--text-muted)]">Loading…</p>

  const nextPending = lease.schedule.find((s) => s.status === "pending")

  return (
    <div className="space-y-6">
      <PrintHeader
        title={`${lease.number} — ${lease.name}`}
        subtitle={`Commenced ${fmtDate(lease.commencement_date)} · ${lease.term_months} months · ${lease.status}`}
        orientation="landscape"
      />

      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="flex items-center gap-3">
          <Link href="/leases" className="text-[var(--text-muted)] hover:text-[var(--text-primary)]">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="font-serif text-xl">{lease.number} — {lease.name}</h1>
            <p className="text-sm text-[var(--text-muted)]">
              {lease.lessor || "—"} · {fmtDate(lease.commencement_date)} · {lease.term_months} mo @ {lease.annual_discount_rate}% · <span className="capitalize">{lease.status}</span>
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {lease.status === "draft" && (
            <button type="button" disabled={busy} onClick={activate} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--text-primary)] text-white disabled:opacity-40">
              Activate
            </button>
          )}
          {lease.status === "active" && nextPending && (
            <button type="button" disabled={busy} onClick={() => postPeriod(nextPending.period_index)} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-[var(--accent)] text-white disabled:opacity-40">
              <Play className="w-4 h-4" /> Post period {nextPending.period_index}
            </button>
          )}
          {lease.status === "active" && (
            <button type="button" disabled={busy} onClick={terminate} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-red-300 text-red-700 disabled:opacity-40">
              <Ban className="w-4 h-4" /> Terminate
            </button>
          )}
          <button type="button" onClick={() => window.print()} className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--text-primary)]/20">
            <Printer className="w-4 h-4" /> Print
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div><div className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Present value</div><div className="font-mono font-bold">{fmt(lease.present_value)}</div></div>
        <div><div className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">RoU cost</div><div className="font-mono font-bold">{fmt(lease.rou_cost)}</div></div>
        <div><div className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">Liability</div><div className="font-mono font-bold">{fmt(lease.liability_carrying)}</div></div>
        <div><div className="text-[10px] uppercase tracking-widest text-[var(--text-muted)]">RoU NBV</div><div className="font-mono font-bold">{fmt(lease.rou_nbv)}</div></div>
      </div>

      <section>
        <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-primary)]/70 mb-2">Amortisation schedule</h2>
        <div className="overflow-x-auto table-freeze">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-primary)]/50 border-b">
                <th className="py-2 text-left">#</th>
                <th className="py-2 text-left whitespace-nowrap">Date</th>
                <th className="py-2 text-right">Opening</th>
                <th className="py-2 text-right">Interest</th>
                <th className="py-2 text-right">Payment</th>
                <th className="py-2 text-right">Principal</th>
                <th className="py-2 text-right">Closing</th>
                <th className="py-2 text-right">Depreciation</th>
                <th className="py-2 text-left print:hidden">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--text-primary)]/5">
              {lease.schedule.map((s) => (
                <tr key={s.id}>
                  <td className="py-2">{s.period_index}</td>
                  <td className="py-2 whitespace-nowrap">{fmtDate(s.period_date)}</td>
                  <td className="py-2 text-right font-mono">{fmt(s.opening_liability)}</td>
                  <td className="py-2 text-right font-mono">{fmt(s.interest)}</td>
                  <td className="py-2 text-right font-mono">{fmt(s.payment)}</td>
                  <td className="py-2 text-right font-mono">{fmt(s.principal)}</td>
                  <td className="py-2 text-right font-mono">{fmt(s.closing_liability)}</td>
                  <td className="py-2 text-right font-mono">{fmt(s.depreciation)}</td>
                  <td className="py-2 capitalize print:hidden text-[var(--text-muted)]">{s.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}
