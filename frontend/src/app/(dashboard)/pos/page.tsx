"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import Link from "next/link"
import { Plus, Trash2, ShoppingCart } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"
import { useModules } from "@/context/ModuleContext"

interface Product {
  id: number
  name: string
  default_rate: number
  unit: string
  product_type: string
  stock_qty?: number
}

interface Register {
  id: number
  name: string
  code: string
  is_active: boolean
}

interface Shift {
  id: number
  register_id: number
  status: string
  opening_float: number
}

interface CartLine {
  key: string
  product_id: number
  description: string
  qty: number
  rate: number
  unit: string
}

export default function PosRegisterPage() {
  const fmt = useFmt()
  const { installedModules } = useModules()
  const hasPos = installedModules.has("pos")

  const [registers, setRegisters] = useState<Register[]>([])
  const [products, setProducts] = useState<Product[]>([])
  const [shift, setShift] = useState<Shift | null>(null)
  const [registerId, setRegisterId] = useState<number | "">("")
  const [floatAmt, setFloatAmt] = useState("0")
  const [q, setQ] = useState("")
  const [cart, setCart] = useState<CartLine[]>([])
  const [tender, setTender] = useState<"cash" | "card" | "bank">("cash")
  const [cashTendered, setCashTendered] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [ok, setOk] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    if (!hasPos) return
    const [regs, prods, shifts] = await Promise.all([
      apiFetch<Register[]>("/api/pos/registers"),
      apiFetch<{ items: Product[] } | Product[]>("/api/products?limit=200"),
      apiFetch<Shift[]>("/api/pos/shifts?status=open"),
    ])
    setRegisters(regs)
    const list = Array.isArray(prods) ? prods : prods.items || []
    setProducts(list)
    if (regs.length && registerId === "") setRegisterId(regs[0].id)
    setShift(shifts[0] || null)
  }, [hasPos, registerId])

  useEffect(() => {
    load().catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
  }, [load])

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return products.slice(0, 40)
    return products.filter((p) => p.name.toLowerCase().includes(s)).slice(0, 40)
  }, [products, q])

  const total = cart.reduce((a, l) => a + l.qty * l.rate, 0)

  const ensureRegister = async () => {
    if (registers.length) return registers[0].id
    const r = await apiFetch<Register>("/api/pos/registers", {
      method: "POST",
      body: JSON.stringify({ name: "Front Counter", code: "REG1" }),
    })
    setRegisters([r])
    setRegisterId(r.id)
    return r.id
  }

  const openShift = async () => {
    setBusy(true)
    setError(null)
    try {
      const rid = registerId === "" ? await ensureRegister() : registerId
      const s = await apiFetch<Shift>("/api/pos/shifts/open", {
        method: "POST",
        body: JSON.stringify({ register_id: rid, opening_float: Number(floatAmt) || 0 }),
      })
      setShift(s)
      setOk(`Shift #${s.id} opened`)
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not open shift")
    } finally {
      setBusy(false)
    }
  }

  const addProduct = (p: Product) => {
    setCart((prev) => {
      const existing = prev.find((l) => l.product_id === p.id)
      if (existing) {
        return prev.map((l) =>
          l.product_id === p.id ? { ...l, qty: l.qty + 1 } : l
        )
      }
      return [
        ...prev,
        {
          key: `${p.id}-${Date.now()}`,
          product_id: p.id,
          description: p.name,
          qty: 1,
          rate: Number(p.default_rate) || 0,
          unit: p.unit || "pcs",
        },
      ]
    })
  }

  const checkout = async () => {
    if (!shift) {
      setError("Open a shift first")
      return
    }
    if (!cart.length) {
      setError("Cart is empty")
      return
    }
    setBusy(true)
    setError(null)
    setOk(null)
    try {
      const body: Record<string, unknown> = {
        shift_id: shift.id,
        tender,
        gst_rate: 0,
        lines: cart.map((l) => ({
          product_id: l.product_id,
          description: l.description,
          qty: l.qty,
          rate: l.rate,
          unit: l.unit,
        })),
      }
      if (tender === "cash") {
        body.cash_tendered = cashTendered ? Number(cashTendered) : total
      }
      const sale = await apiFetch<{
        invoice_number: string
        total: number
        change_given?: number
      }>("/api/pos/sales", { method: "POST", body: JSON.stringify(body) })
      setOk(
        `Sold ${sale.invoice_number} — ${fmt(Number(sale.total))}` +
          (sale.change_given ? ` · change ${fmt(Number(sale.change_given))}` : "")
      )
      setCart([])
      setCashTendered("")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sale failed")
    } finally {
      setBusy(false)
    }
  }

  if (!hasPos) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center space-y-3">
        <ShoppingCart className="w-10 h-10 mx-auto text-[var(--primary)]/50" />
        <h1 className="text-xl font-bold">Point of Sale</h1>
        <p className="text-sm text-[var(--text-primary)]/60">
          Install the POS module from System → Apps to use the register.
        </p>
        <Link href="/apps" className="text-[var(--primary)] text-sm font-medium underline">
          Open Apps
        </Link>
      </div>
    )
  }

  return (
    <div className="grid lg:grid-cols-5 gap-6">
      <div className="lg:col-span-3 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">POS Register</h1>
            <p className="text-sm text-[var(--text-primary)]/55">
              {shift
                ? `Shift #${shift.id} open · float ${fmt(Number(shift.opening_float || 0))}`
                : "No open shift — open one to start selling"}
            </p>
          </div>
          <Link href="/pos/shifts" className="text-sm text-[var(--primary)] font-medium hover:underline">
            Shifts →
          </Link>
        </div>

        {!shift && (
          <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl p-4 flex flex-wrap gap-2 items-end">
            <label className="text-sm">
              <span className="block text-xs text-[var(--text-primary)]/50 mb-1">Register</span>
              <select
                className="border rounded-lg px-3 py-2 text-sm"
                value={registerId === "" ? "" : String(registerId)}
                onChange={(e) => setRegisterId(e.target.value ? Number(e.target.value) : "")}
              >
                {!registers.length && <option value="">Auto-create</option>}
                {registers.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              <span className="block text-xs text-[var(--text-primary)]/50 mb-1">Opening float</span>
              <input
                type="number"
                className="border rounded-lg px-3 py-2 text-sm w-28"
                value={floatAmt}
                onChange={(e) => setFloatAmt(e.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={busy}
              onClick={openShift}
              className="bg-[var(--primary)] text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-40"
            >
              Open shift
            </button>
          </div>
        )}

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search products…"
          className="w-full border border-[var(--border)] rounded-xl px-4 py-2.5 text-sm bg-white"
        />

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[28rem] overflow-y-auto">
          {filtered.map((p) => (
            <button
              key={p.id}
              type="button"
              disabled={!shift}
              onClick={() => addProduct(p)}
              className="text-left bg-white border border-[var(--text-primary)]/10 rounded-xl p-3 hover:border-[var(--primary)]/40 disabled:opacity-40"
            >
              <div className="text-sm font-semibold text-[var(--text-primary)] line-clamp-2">{p.name}</div>
              <div className="text-xs text-[var(--text-primary)]/50 mt-1">
                {fmt(Number(p.default_rate) || 0)}
                {p.product_type === "stock" ? ` · qty ${p.stock_qty ?? 0}` : ""}
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="lg:col-span-2 space-y-3">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-3 py-2 text-sm">{error}</div>
        )}
        {ok && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl px-3 py-2 text-sm">{ok}</div>
        )}

        <div className="bg-white border border-[var(--text-primary)]/10 rounded-2xl p-4 space-y-3">
          <div className="font-semibold text-[var(--text-primary)]">Cart</div>
          {!cart.length && (
            <p className="text-sm text-[var(--text-primary)]/45">Tap products to add lines.</p>
          )}
          {cart.map((l) => (
            <div key={l.key} className="flex items-center gap-2 text-sm">
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{l.description}</div>
                <div className="text-xs text-[var(--text-primary)]/50">
                  {fmt(l.rate)} ×
                  <input
                    type="number"
                    min={0.01}
                    step="any"
                    className="w-14 mx-1 border rounded px-1 py-0.5"
                    value={l.qty}
                    onChange={(e) => {
                      const qty = Number(e.target.value) || 1
                      setCart((prev) =>
                        prev.map((x) => (x.key === l.key ? { ...x, qty } : x))
                      )
                    }}
                  />
                  {l.unit}
                </div>
              </div>
              <div className="font-semibold whitespace-nowrap">{fmt(l.qty * l.rate)}</div>
              <button type="button" onClick={() => setCart((p) => p.filter((x) => x.key !== l.key))}>
                <Trash2 className="w-4 h-4 text-red-500" />
              </button>
            </div>
          ))}

          <div className="border-t pt-3 flex justify-between font-bold text-[var(--text-primary)]">
            <span>Total</span>
            <span>{fmt(total)}</span>
          </div>

          <div className="flex gap-2">
            {(["cash", "card", "bank"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTender(t)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium border ${
                  tender === t
                    ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                    : "bg-white text-[var(--text-primary)]"
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          {tender === "cash" && (
            <label className="block text-sm">
              <span className="text-xs text-[var(--text-primary)]/50">Cash tendered</span>
              <input
                type="number"
                className="w-full border rounded-lg px-3 py-2 mt-1"
                placeholder={String(total || "")}
                value={cashTendered}
                onChange={(e) => setCashTendered(e.target.value)}
              />
            </label>
          )}

          <button
            type="button"
            disabled={busy || !shift || !cart.length}
            onClick={checkout}
            className="w-full inline-flex items-center justify-center gap-2 bg-[var(--primary)] text-white py-3 rounded-xl text-sm font-bold disabled:opacity-40"
          >
            <Plus className="w-4 h-4" />
            Complete sale
          </button>
        </div>
      </div>
    </div>
  )
}
