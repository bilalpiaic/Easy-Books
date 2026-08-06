"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { Plus, RefreshCw, Link2, CheckCircle2, AlertTriangle, Clock } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useModules } from "@/context/ModuleContext"
import { fmtDate } from "@/lib/utils"

type Conn = {
  id: number
  provider: string
  shop_domain: string
  shop_name: string
  stock_sync_direction: string
  sync_status: string
  last_sync: string | null
  last_error: string | null
  is_active: boolean
}

type ImportRow = {
  id: number
  external_order_number: string | null
  invoice_id: number | null
  status: string
  imported_at: string | null
}

const input =
  "border border-[var(--border)] rounded-lg px-3 py-2 text-sm w-full bg-[var(--surface)]"

export default function EcommercePage() {
  const { installedModules } = useModules()
  const has = installedModules.has("ecommerce")
  const [rows, setRows] = useState<Conn[]>([])
  const [err, setErr] = useState("")
  const [busy, setBusy] = useState<number | null>(null)
  const [imports, setImports] = useState<ImportRow[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [form, setForm] = useState({
    provider: "mock",
    shop_domain: "",
    shop_name: "",
    access_token: "",
    api_secret: "",
    stock_sync_direction: "off",
  })
  const [show, setShow] = useState(false)

  const load = useCallback(() => {
    if (!has) return
    apiFetch<Conn[]>("/api/ecommerce/connections")
      .then(d => setRows(Array.isArray(d) ? d : []))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : "Failed"))
  }, [has])

  useEffect(() => { load() }, [load])

  async function connect(e: React.FormEvent) {
    e.preventDefault()
    setErr("")
    try {
      await apiFetch("/api/ecommerce/connections", {
        method: "POST",
        body: JSON.stringify({
          ...form,
          shop_domain: form.provider === "mock" || form.provider === "daraz"
            ? (form.shop_domain || (form.provider === "daraz" ? "api.daraz.pk" : "mock.local"))
            : form.shop_domain,
          access_token: form.provider === "daraz" && !form.access_token ? "sandbox" : form.access_token,
        }),
      })
      setShow(false)
      load()
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Connect failed")
    }
  }

  async function sync(id: number) {
    setBusy(id); setErr("")
    try {
      await apiFetch(`/api/ecommerce/connections/${id}/products/auto-map`, { method: "POST" })
      const r = await apiFetch<{ created_count: number; skipped: number }>(
        `/api/ecommerce/connections/${id}/sync`,
        { method: "POST" },
      )
      setSelected(id)
      const imp = await apiFetch<ImportRow[]>(`/api/ecommerce/connections/${id}/imports`)
      setImports(Array.isArray(imp) ? imp : [])
      load()
      if (r.created_count === 0 && r.skipped > 0) {
        /* ok — idempotent */
      }
    } catch (ex: unknown) {
      setErr(ex instanceof Error ? ex.message : "Sync failed")
    } finally {
      setBusy(null)
    }
  }

  if (!has) {
    return (
      <div className="p-6 max-w-lg mx-auto text-sm text-[var(--text-muted)]">
        Install the <Link href="/apps" className="text-[var(--primary)]">eCommerce Connectors</Link> module to connect Shopify, WooCommerce, or Daraz.
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4 max-w-5xl mx-auto">
      <div className="flex items-center justify-between print:hidden">
        <div>
          <h1 className="text-xl font-semibold">eCommerce Stores</h1>
          <p className="text-xs text-[var(--text-muted)]">
            Connect Shopify / WooCommerce / Daraz · map SKUs · import orders as draft invoices
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShow(s => !s)}
          className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2 flex items-center gap-1"
        >
          <Plus className="w-4 h-4" /> Connect store
        </button>
      </div>

      {err && <p className="text-sm text-red-600">{err}</p>}

      {show && (
        <form onSubmit={connect} className="border border-[var(--border)] rounded-xl p-3 space-y-2 print:hidden">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <select className={input} value={form.provider}
              onChange={e => setForm({ ...form, provider: e.target.value })}>
              <option value="mock">Mock Store (demo)</option>
              <option value="shopify">Shopify</option>
              <option value="woocommerce">WooCommerce</option>
              <option value="daraz">Daraz (sandbox token OK)</option>
            </select>
            <input className={input} placeholder="Shop name" value={form.shop_name}
              onChange={e => setForm({ ...form, shop_name: e.target.value })} />
            <input className={input} placeholder="Shop domain (mystore.myshopify.com)"
              value={form.shop_domain}
              onChange={e => setForm({ ...form, shop_domain: e.target.value })}
              required={form.provider !== "mock" && form.provider !== "daraz"} />
            <select className={input} value={form.stock_sync_direction}
              onChange={e => setForm({ ...form, stock_sync_direction: e.target.value })}>
              <option value="off">Stock sync: off</option>
              <option value="store_to_eb">Stock: store → Easy-Books</option>
              <option value="eb_to_store">Stock: Easy-Books → store</option>
            </select>
            {form.provider !== "mock" && (
              <>
                <input className={input} placeholder={
                  form.provider === "shopify" ? "Access token"
                    : form.provider === "daraz" ? "Access token (or sandbox)"
                    : "Consumer key"
                }
                  value={form.access_token}
                  onChange={e => setForm({ ...form, access_token: e.target.value })}
                  required={form.provider !== "daraz"} />
                {form.provider === "woocommerce" && (
                  <input className={input} placeholder="Consumer secret" type="password"
                    value={form.api_secret}
                    onChange={e => setForm({ ...form, api_secret: e.target.value })}
                    required />
                )}
              </>
            )}
          </div>
          <button type="submit" className="rounded-lg bg-[var(--primary)] text-white text-sm px-3 py-2">
            Save connection
          </button>
        </form>
      )}

      <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b border-[var(--border)]">
              <th className="p-2">Store</th>
              <th className="p-2">Provider</th>
              <th className="p-2">Stock sync</th>
              <th className="p-2">Status</th>
              <th className="p-2">Last sync</th>
              <th className="p-2 print:hidden" />
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id} className="border-b border-[var(--border)]/60">
                <td className="p-2">
                  <div className="font-medium">{r.shop_name || r.shop_domain}</div>
                  <div className="text-xs text-[var(--text-muted)]">{r.shop_domain}</div>
                </td>
                <td className="p-2 capitalize">{r.provider}</td>
                <td className="p-2 text-xs">{r.stock_sync_direction}</td>
                <td className="p-2">
                  {r.sync_status === "ok" ? (
                    <span className="inline-flex items-center gap-1 text-emerald-700 text-xs"><CheckCircle2 className="w-3 h-3" /> OK</span>
                  ) : r.sync_status === "error" ? (
                    <span className="inline-flex items-center gap-1 text-red-600 text-xs" title={r.last_error || ""}><AlertTriangle className="w-3 h-3" /> Error</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[var(--text-muted)] text-xs"><Clock className="w-3 h-3" /> Never</span>
                  )}
                </td>
                <td className="p-2 whitespace-nowrap">{r.last_sync ? fmtDate(r.last_sync) : "—"}</td>
                <td className="p-2 print:hidden">
                  <button type="button" disabled={busy === r.id}
                    onClick={() => sync(r.id)}
                    className="text-xs text-[var(--primary)] flex items-center gap-1 disabled:opacity-50">
                    <RefreshCw className={`w-3.5 h-3.5 ${busy === r.id ? "animate-spin" : ""}`} />
                    Sync orders
                  </button>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr><td colSpan={6} className="p-6 text-center text-[var(--text-muted)]">No stores connected yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {selected && imports.length > 0 && (
        <div>
          <h2 className="font-semibold mb-2 text-sm flex items-center gap-1"><Link2 className="w-4 h-4" /> Recent imports</h2>
          <div className="table-freeze overflow-auto border border-[var(--border)] rounded-xl">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left border-b border-[var(--border)]">
                  <th className="p-2">Order</th>
                  <th className="p-2">Invoice</th>
                  <th className="p-2">Status</th>
                  <th className="p-2">Imported</th>
                </tr>
              </thead>
              <tbody>
                {imports.map(i => (
                  <tr key={i.id} className="border-b border-[var(--border)]/60">
                    <td className="p-2">{i.external_order_number || "—"}</td>
                    <td className="p-2">
                      {i.invoice_id ? (
                        <Link href={`/invoices/${i.invoice_id}`} className="text-[var(--primary)]">#{i.invoice_id}</Link>
                      ) : "—"}
                    </td>
                    <td className="p-2">{i.status}</td>
                    <td className="p-2 whitespace-nowrap">{i.imported_at ? fmtDate(i.imported_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
