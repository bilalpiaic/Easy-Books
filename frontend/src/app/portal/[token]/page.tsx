"use client"

import { useEffect, useState } from "react"
import { useParams } from "next/navigation"
import { apiBase } from "@/lib/api"
import { downloadPublicPdf } from "@/lib/downloadPdf"
import { fmtDate } from "@/lib/utils"

type Inv = {
  id: number
  number: string
  issue_date: string
  due_date: string
  total: number
  status: string
  currency: string
}

type Bill = {
  id: number
  number: string
  bill_date: string
  due_date: string
  total: number
  status: string
  currency: string
}

type LabOrder = {
  id: number
  order_number: string
  order_date: string
  status: string
  source: string
}

type Home = {
  company_name: string
  entity_name: string
  entity_type: string
}

type VendorStatement = {
  outstanding: number
  open_bills: Bill[]
  payments: { id: number; payment_date: string; amount: number; method: string; reference: string | null }[]
}

export default function PortalPage() {
  const { token } = useParams<{ token: string }>()
  const [home, setHome] = useState<Home | null>(null)
  const [invoices, setInvoices] = useState<Inv[]>([])
  const [labOrders, setLabOrders] = useState<LabOrder[]>([])
  const [statement, setStatement] = useState<VendorStatement | null>(null)
  const [err, setErr] = useState("")
  const [pdfBusyId, setPdfBusyId] = useState<number | null>(null)

  useEffect(() => {
    if (!token) return
    fetch(`${apiBase}/api/portal/${token}`)
      .then(async (r) => {
        if (!r.ok) throw new Error("Invalid portal link")
        return r.json()
      })
      .then((h: Home) => {
        setHome(h)
        if (h.entity_type === "vendor") {
          return fetch(`${apiBase}/api/portal/${token}/statement`)
            .then((r) => r.json())
            .then(setStatement)
        }
        if (h.entity_type === "patient") {
          return fetch(`${apiBase}/api/portal/${token}/lab-orders`)
            .then((r) => r.json())
            .then(setLabOrders)
        }
        return fetch(`${apiBase}/api/portal/${token}/invoices`)
          .then((r) => r.json())
          .then(setInvoices)
      })
      .catch((e) => setErr(e.message))
  }, [token])

  const pay = async (id: number) => {
    const r = await fetch(`${apiBase}/api/portal/${token}/invoices/${id}/pay`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    })
    const data = await r.json()
    if (data.checkout_url) window.location.href = data.checkout_url
    else alert(data.message || "Payment not available")
  }

  const downloadLabPdf = async (order: LabOrder) => {
    setPdfBusyId(order.id)
    try {
      await downloadPublicPdf(
        `${apiBase}/api/portal/${token}/lab-orders/${order.id}/pdf`,
        `${order.order_number}.pdf`,
      )
    } catch {
      alert("PDF download failed")
    } finally {
      setPdfBusyId(null)
    }
  }

  if (err) {
    return <div className="min-h-screen bg-[#f6f3ee] flex items-center justify-center text-red-700">{err}</div>
  }

  const isVendor = home?.entity_type === "vendor"
  const isPatient = home?.entity_type === "patient"
  const portalLabel = isPatient ? "Patient portal" : isVendor ? "Vendor portal" : "Customer portal"

  return (
    <div className="min-h-screen bg-[#f6f3ee] px-4 py-10">
      <div className="max-w-2xl mx-auto space-y-6">
        <header>
          <h1 className="font-serif text-3xl text-[#1a1814]">{home?.company_name || "…"}</h1>
          <p className="text-sm text-[#1a1814]/70">
            {portalLabel}
            {home?.entity_name ? ` · ${home.entity_name}` : ""}
          </p>
        </header>

        {isPatient ? (
          <div className="bg-white/70 border border-[#1a1814]/10 rounded-2xl overflow-hidden divide-y divide-[#1a1814]/10">
            {labOrders.map((lo) => (
              <div key={lo.id} className="p-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-[#1a1814]">{lo.order_number}</p>
                  <p className="text-xs text-[#1a1814]/60 mt-0.5">
                    {fmtDate(lo.order_date)} · {lo.status}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => downloadLabPdf(lo)}
                  disabled={pdfBusyId === lo.id}
                  className="shrink-0 text-xs bg-[#b8943f] text-white px-3 py-1.5 rounded-lg disabled:opacity-50"
                >
                  {pdfBusyId === lo.id ? "…" : "Download PDF"}
                </button>
              </div>
            ))}
            {!labOrders.length && (
              <div className="p-8 text-center text-sm text-[#1a1814]/50">
                No lab reports available yet
              </div>
            )}
          </div>
        ) : isVendor ? (
          <>
            <div className="bg-white/70 border border-[#1a1814]/10 rounded-2xl p-4">
              <div className="text-xs uppercase tracking-widest text-[#1a1814]/50">Outstanding</div>
              <div className="text-2xl font-semibold text-[#1a1814]">
                {(statement?.outstanding ?? 0).toLocaleString()}
              </div>
            </div>
            <div className="bg-white/70 border border-[#1a1814]/10 rounded-2xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-[#1a1814]/5 text-left">
                  <tr>
                    <th className="p-3">Bill</th>
                    <th className="p-3">Due</th>
                    <th className="p-3 text-right">Amount</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(statement?.open_bills || []).map((b) => (
                    <tr key={b.id} className="border-t border-[#1a1814]/10">
                      <td className="p-3 whitespace-nowrap">{b.number}</td>
                      <td className="p-3 whitespace-nowrap">{b.due_date}</td>
                      <td className="p-3 text-right">{b.currency} {b.total.toLocaleString()}</td>
                      <td className="p-3">{b.status}</td>
                    </tr>
                  ))}
                  {!statement?.open_bills?.length && (
                    <tr><td className="p-6 text-center text-[#1a1814]/50" colSpan={4}>No open bills</td></tr>
                  )}
                </tbody>
              </table>
            </div>
            {(statement?.payments?.length ?? 0) > 0 && (
              <div className="bg-white/70 border border-[#1a1814]/10 rounded-2xl overflow-hidden">
                <div className="px-3 py-2 text-xs uppercase tracking-widest text-[#1a1814]/50 bg-[#1a1814]/5">
                  Recent payments
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    {statement!.payments.map((p) => (
                      <tr key={p.id} className="border-t border-[#1a1814]/10">
                        <td className="p-3 whitespace-nowrap">{p.payment_date}</td>
                        <td className="p-3">{p.method}{p.reference ? ` · ${p.reference}` : ""}</td>
                        <td className="p-3 text-right">{p.amount.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          <div className="bg-white/70 border border-[#1a1814]/10 rounded-2xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-[#1a1814]/5 text-left">
                <tr>
                  <th className="p-3">Invoice</th>
                  <th className="p-3">Due</th>
                  <th className="p-3 text-right">Amount</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id} className="border-t border-[#1a1814]/10">
                    <td className="p-3 whitespace-nowrap">{inv.number}</td>
                    <td className="p-3 whitespace-nowrap">{inv.due_date}</td>
                    <td className="p-3 text-right">{inv.currency} {inv.total.toLocaleString()}</td>
                    <td className="p-3 text-right space-x-2">
                      <button
                        type="button"
                        className="underline text-xs disabled:opacity-50"
                        disabled={pdfBusyId === inv.id}
                        onClick={async () => {
                          setPdfBusyId(inv.id)
                          try {
                            await downloadPublicPdf(
                              `${apiBase}/api/portal/${token}/invoices/${inv.id}/pdf`,
                              `${inv.number}.pdf`,
                            )
                          } catch {
                            alert("PDF download failed")
                          } finally {
                            setPdfBusyId(null)
                          }
                        }}
                      >
                        {pdfBusyId === inv.id ? "…" : "PDF"}
                      </button>
                      <button type="button" className="text-xs bg-[#b8943f] px-2 py-1 rounded" onClick={() => pay(inv.id)}>
                        Pay
                      </button>
                    </td>
                  </tr>
                ))}
                {!invoices.length && (
                  <tr><td className="p-6 text-center text-[#1a1814]/50" colSpan={4}>No outstanding invoices</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
