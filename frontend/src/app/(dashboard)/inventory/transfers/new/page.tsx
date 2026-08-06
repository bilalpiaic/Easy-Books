"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import Link from "next/link"
import { apiFetch } from "@/lib/api"

interface Loc { id: number; code: string; name: string; type: string }
interface Product { id: number; name: string; product_type: string }

interface Line { product_id: number; qty: string }

export default function NewStockTransferPage() {
  const router = useRouter()
  const [locs, setLocs] = useState<Loc[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [fromId, setFromId] = useState<number | "">("")
  const [toId, setToId] = useState<number | "">("")
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [notes, setNotes] = useState("")
  const [lines, setLines] = useState<Line[]>([{ product_id: 0, qty: "1" }])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch<{ items: Loc[] }>("/api/stock-locations?type=own"),
      apiFetch<{ items: Product[] } | Product[]>("/api/products?product_type=stock&limit=200"),
    ]).then(([l, p]) => {
      setLocs(l.items || [])
      setProducts(Array.isArray(p) ? p : p.items || [])
      if (l.items?.length >= 2) {
        setFromId(l.items[0].id)
        setToId(l.items[1].id)
      } else if (l.items?.length === 1) {
        setFromId(l.items[0].id)
      }
    }).catch((e) => setError(e instanceof Error ? e.message : "Load failed"))
  }, [])

  const submit = async () => {
    if (!fromId || !toId) {
      setError("Select from and to warehouses")
      return
    }
    const bodyLines = lines
      .filter((l) => l.product_id && Number(l.qty) > 0)
      .map((l) => ({ product_id: l.product_id, qty: Number(l.qty) }))
    if (!bodyLines.length) {
      setError("Add at least one product line")
      return
    }
    setBusy(true)
    setError(null)
    try {
      const t = await apiFetch<{ id: number }>("/api/stock-transfers", {
        method: "POST",
        body: JSON.stringify({
          transfer_date: date,
          from_location_id: fromId,
          to_location_id: toId,
          notes: notes || null,
          lines: bodyLines,
        }),
      })
      router.push(`/inventory/transfers/${t.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create failed")
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-4 max-w-2xl">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">New Stock Transfer</h1>
        <Link href="/inventory/transfers" className="text-sm text-[var(--primary)] hover:underline">← List</Link>
      </div>
      {error && <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-3 py-2 text-sm">{error}</div>}

      <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl p-4 space-y-3">
        <label className="block text-sm">
          <span className="text-xs text-[var(--text-primary)]/50">Date</span>
          <input type="date" className="block w-full border rounded-lg px-3 py-2 mt-1" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
        <div className="grid sm:grid-cols-2 gap-3">
          <label className="block text-sm">
            <span className="text-xs text-[var(--text-primary)]/50">From warehouse</span>
            <select className="block w-full border rounded-lg px-3 py-2 mt-1" value={fromId === "" ? "" : String(fromId)} onChange={(e) => setFromId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Select…</option>
              {locs.map((l) => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-xs text-[var(--text-primary)]/50">To warehouse</span>
            <select className="block w-full border rounded-lg px-3 py-2 mt-1" value={toId === "" ? "" : String(toId)} onChange={(e) => setToId(e.target.value ? Number(e.target.value) : "")}>
              <option value="">Select…</option>
              {locs.map((l) => <option key={l.id} value={l.id}>{l.code} — {l.name}</option>)}
            </select>
          </label>
        </div>
        <label className="block text-sm">
          <span className="text-xs text-[var(--text-primary)]/50">Notes</span>
          <input className="block w-full border rounded-lg px-3 py-2 mt-1" value={notes} onChange={(e) => setNotes(e.target.value)} />
        </label>

        <div className="space-y-2 pt-2">
          <div className="text-xs font-medium text-[var(--text-primary)]/50 uppercase tracking-wide">Lines</div>
          {lines.map((ln, i) => (
            <div key={i} className="flex gap-2">
              <select
                className="flex-1 border rounded-lg px-3 py-2 text-sm"
                value={ln.product_id || ""}
                onChange={(e) => {
                  const v = Number(e.target.value) || 0
                  setLines((prev) => prev.map((x, j) => j === i ? { ...x, product_id: v } : x))
                }}
              >
                <option value="">Product…</option>
                {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
              <input
                type="number"
                min="0"
                step="any"
                className="w-24 border rounded-lg px-3 py-2 text-sm"
                value={ln.qty}
                onChange={(e) => setLines((prev) => prev.map((x, j) => j === i ? { ...x, qty: e.target.value } : x))}
              />
            </div>
          ))}
          <button type="button" className="text-sm text-[var(--primary)]" onClick={() => setLines((p) => [...p, { product_id: 0, qty: "1" }])}>
            + Add line
          </button>
        </div>

        <button
          type="button"
          disabled={busy}
          onClick={submit}
          className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40"
        >
          Create draft
        </button>
      </div>
    </div>
  )
}
