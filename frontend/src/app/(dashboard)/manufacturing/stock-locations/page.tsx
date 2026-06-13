"use client"

import { useEffect, useState } from "react"
import { Plus, Pencil, ToggleLeft, ToggleRight, Warehouse, ChevronDown, ChevronRight } from "lucide-react"
import { apiFetch } from "@/lib/api"
import { useFmt } from "@/context/SettingsContext"

interface StockLocation {
  id: number
  code: string
  name: string
  type: "own" | "customer_custodial" | "wip"
  is_active: boolean
}

interface StockItem {
  product_id: number
  product_code: string
  product_name: string
  lot_no: string | null
  qty: number
  value: number
}

interface StockView {
  location: StockLocation
  items: StockItem[]
  total_lines: number
}

const TYPE_LABELS: Record<string, string> = {
  own:                "Own",
  customer_custodial: "Customer Custodial",
  wip:                "WIP",
}

const TYPE_TONE: Record<string, string> = {
  own:                "bg-blue-50 text-blue-800 border-blue-200",
  customer_custodial: "bg-violet-50 text-violet-800 border-violet-200",
  wip:                "bg-amber-50 text-amber-800 border-amber-200",
}

interface FormState { code: string; name: string; type: string }
const emptyForm: FormState = { code: "", name: "", type: "own" }

export default function StockLocationsPage() {
  const fmt = useFmt()

  const [locations, setLocations]     = useState<StockLocation[]>([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState<string | null>(null)
  const [modalOpen, setModalOpen]     = useState(false)
  const [editing, setEditing]         = useState<StockLocation | null>(null)
  const [form, setForm]               = useState<FormState>(emptyForm)
  const [saving, setSaving]           = useState(false)
  const [formErr, setFormErr]         = useState<string | null>(null)

  // Expanded stock views: location_id → StockView | "loading" | null
  const [expanded, setExpanded]       = useState<Record<number, StockView | "loading" | null>>({})

  const load = () => {
    setLoading(true)
    apiFetch<{ total: number; items: StockLocation[] }>("/api/stock-locations?limit=200")
      .then(d => setLocations(d.items))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    const h = () => openAdd()
    window.addEventListener("kbd:new", h)
    return () => window.removeEventListener("kbd:new", h)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const toggleExpand = async (loc: StockLocation) => {
    if (expanded[loc.id] !== undefined) {
      setExpanded(prev => { const n = { ...prev }; delete n[loc.id]; return n })
      return
    }
    setExpanded(prev => ({ ...prev, [loc.id]: "loading" }))
    try {
      const sv = await apiFetch<StockView>(`/api/stock-locations/${loc.id}/stock`)
      setExpanded(prev => ({ ...prev, [loc.id]: sv }))
    } catch {
      setExpanded(prev => ({ ...prev, [loc.id]: null }))
    }
  }

  const openAdd = () => {
    setEditing(null); setForm(emptyForm); setFormErr(null); setModalOpen(true)
  }

  const openEdit = (loc: StockLocation) => {
    setEditing(loc)
    setForm({ code: loc.code, name: loc.name, type: loc.type })
    setFormErr(null); setModalOpen(true)
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.code.trim()) { setFormErr("Code is required"); return }
    if (!form.name.trim()) { setFormErr("Name is required"); return }
    setSaving(true); setFormErr(null)
    try {
      if (editing) {
        await apiFetch(`/api/stock-locations/${editing.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: form.name }),
        })
      } else {
        await apiFetch("/api/stock-locations", {
          method: "POST",
          body: JSON.stringify(form),
        })
      }
      setModalOpen(false)
      load()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Save failed"
      setFormErr(msg.includes("already exists") ? `Code '${form.code}' is already in use` : msg)
    } finally {
      setSaving(false)
    }
  }

  const toggleActive = async (loc: StockLocation) => {
    try {
      await apiFetch(`/api/stock-locations/${loc.id}`, {
        method: "PUT",
        body: JSON.stringify({ is_active: !loc.is_active }),
      })
      load()
    } catch {}
  }

  const activeLocations   = locations.filter(l => l.is_active)
  const inactiveLocations = locations.filter(l => !l.is_active)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-serif font-semibold text-[#1a1814]">Stock Locations</h1>
          <p className="text-sm text-[#1a1814]/60 mt-0.5">
            Warehouses, godowns, and WIP buckets. Click a location to view its stock.
          </p>
        </div>
        <button
          onClick={openAdd}
          className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors"
        >
          <Plus className="w-4 h-4" /> New Location
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-800 rounded-xl px-4 py-3 text-sm">{error}</div>
      )}

      {loading ? (
        <div className="text-sm text-[#1a1814]/50 py-8 text-center">Loading…</div>
      ) : locations.length === 0 ? (
        <div className="bg-white border border-[#ede9e2] rounded-xl px-6 py-12 text-center">
          <Warehouse className="w-10 h-10 text-[#b8943f]/40 mx-auto mb-3" />
          <p className="text-sm font-medium text-[#1a1814]">No stock locations yet</p>
          <p className="text-xs text-[#1a1814]/55 mt-1 mb-4">
            Create warehouses, customer godowns, and WIP buckets to track inventory by location.
          </p>
          <button
            onClick={openAdd}
            className="inline-flex items-center gap-2 bg-[#b8943f] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#a07c32] transition-colors"
          >
            <Plus className="w-4 h-4" /> Create first location
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <LocationGroup
            items={activeLocations}
            title={`Active (${activeLocations.length})`}
            expanded={expanded}
            fmt={fmt}
            onEdit={openEdit}
            onToggle={toggleActive}
            onExpand={toggleExpand}
          />
          {inactiveLocations.length > 0 && (
            <LocationGroup
              items={inactiveLocations}
              title={`Inactive (${inactiveLocations.length})`}
              dimmed
              expanded={expanded}
              fmt={fmt}
              onEdit={openEdit}
              onToggle={toggleActive}
              onExpand={toggleExpand}
            />
          )}
        </div>
      )}

      {/* Modal */}
      {modalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm">
            <div className="px-6 py-4 border-b border-[#ede9e2]">
              <h2 className="text-lg font-serif font-semibold text-[#1a1814]">
                {editing ? "Edit Location" : "New Stock Location"}
              </h2>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Code</label>
                  <input
                    value={form.code}
                    onChange={e => setForm(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                    disabled={!!editing}
                    placeholder="WH-01"
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f] disabled:bg-[#f5f2ed] font-mono"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Type</label>
                  <select
                    value={form.type}
                    onChange={e => setForm(f => ({ ...f, type: e.target.value }))}
                    disabled={!!editing}
                    className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f] disabled:bg-[#f5f2ed]"
                  >
                    <option value="own">Own</option>
                    <option value="customer_custodial">Customer Custodial</option>
                    <option value="wip">WIP</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#1a1814]/70 mb-1.5 uppercase tracking-wide">Name</label>
                <input
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. Main Warehouse"
                  className="w-full border border-[#d4cfc7] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#b8943f]"
                />
              </div>

              {formErr && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{formErr}</p>
              )}

              <div className="flex gap-3 pt-1">
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 bg-[#b8943f] text-white py-2.5 rounded-lg text-sm font-medium hover:bg-[#a07c32] disabled:opacity-50 transition-colors"
                >
                  {saving ? "Saving…" : editing ? "Save Changes" : "Create"}
                </button>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  className="px-4 py-2.5 border border-[#d4cfc7] rounded-lg text-sm text-[#1a1814]/70 hover:bg-[#f0ede6] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function LocationGroup({
  items, title, dimmed = false, expanded, fmt, onEdit, onToggle, onExpand,
}: {
  items: StockLocation[]
  title: string
  dimmed?: boolean
  expanded: Record<number, StockView | "loading" | null>
  fmt: (n: number) => string
  onEdit: (loc: StockLocation) => void
  onToggle: (loc: StockLocation) => void
  onExpand: (loc: StockLocation) => void
}) {
  return (
    <div>
      <h2 className="text-xs font-bold uppercase tracking-wider text-[#1a1814]/50 mb-2">{title}</h2>
      <div className={`bg-white border border-[#ede9e2] rounded-xl overflow-hidden ${dimmed ? "opacity-60" : ""}`}>
        {items.map((loc, idx) => {
          const sv = expanded[loc.id]
          const isOpen = sv !== undefined
          return (
            <div key={loc.id} className={idx > 0 ? "border-t border-[#ede9e2]" : ""}>
              {/* Location row */}
              <div
                className="flex items-center gap-3 px-4 py-3 hover:bg-[#faf8f4] cursor-pointer select-none"
                onClick={() => onExpand(loc)}
              >
                <div className="text-[#1a1814]/30">
                  {isOpen
                    ? <ChevronDown className="w-4 h-4" />
                    : <ChevronRight className="w-4 h-4" />
                  }
                </div>
                <span className="font-mono text-xs text-[#1a1814]/80 w-20 shrink-0">{loc.code}</span>
                <span className="flex-1 text-sm text-[#1a1814]">{loc.name}</span>
                <span className={`inline-block border rounded-full px-2.5 py-0.5 text-xs font-medium ${TYPE_TONE[loc.type] ?? "bg-slate-50 text-slate-700 border-slate-200"}`}>
                  {TYPE_LABELS[loc.type] ?? loc.type}
                </span>
                <div className="flex items-center gap-2 ml-2" onClick={e => e.stopPropagation()}>
                  <button
                    onClick={() => onEdit(loc)}
                    className="text-[#1a1814]/40 hover:text-[#b8943f] transition-colors"
                    title="Edit"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => onToggle(loc)}
                    className={`transition-colors ${loc.is_active ? "text-emerald-500 hover:text-red-400" : "text-[#1a1814]/30 hover:text-emerald-500"}`}
                    title={loc.is_active ? "Deactivate" : "Activate"}
                  >
                    {loc.is_active
                      ? <ToggleRight className="w-4 h-4" />
                      : <ToggleLeft  className="w-4 h-4" />
                    }
                  </button>
                </div>
              </div>

              {/* Stock drill-down */}
              {isOpen && (
                <div className="border-t border-[#ede9e2] bg-[#faf8f4]">
                  {sv === "loading" ? (
                    <p className="px-8 py-3 text-xs text-[#1a1814]/50">Loading stock…</p>
                  ) : sv === null ? (
                    <p className="px-8 py-3 text-xs text-red-600">Failed to load stock</p>
                  ) : sv.items.length === 0 ? (
                    <p className="px-8 py-3 text-xs text-[#1a1814]/50">No stock at this location</p>
                  ) : (
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-[#ede9e2]">
                          <th className="text-left px-8 py-2 font-semibold text-[#1a1814]/60">Product</th>
                          <th className="text-left px-4 py-2 font-semibold text-[#1a1814]/60">Lot</th>
                          <th className="text-right px-4 py-2 font-semibold text-[#1a1814]/60">Qty</th>
                          <th className="text-right px-4 py-2 font-semibold text-[#1a1814]/60">Value</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sv.items.map((item, i) => (
                          <tr key={i} className="border-b border-[#ede9e2] last:border-0">
                            <td className="px-8 py-1.5 text-[#1a1814]/80">
                              <span className="font-mono mr-1.5 text-[#1a1814]/50">{item.product_code}</span>
                              {item.product_name}
                            </td>
                            <td className="px-4 py-1.5 text-[#1a1814]/55">{item.lot_no || "—"}</td>
                            <td className="px-4 py-1.5 text-right tabular-nums">{Number(item.qty).toFixed(2)}</td>
                            <td className="px-4 py-1.5 text-right tabular-nums">{fmt(Number(item.value))}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-[#ede9e2] bg-[#f5f2ed]">
                          <td className="px-8 py-2 text-xs font-semibold text-[#1a1814]/60" colSpan={3}>
                            {sv.total_lines} line{sv.total_lines !== 1 ? "s" : ""}
                          </td>
                          <td className="px-4 py-2 text-right text-xs font-bold text-[#1a1814]">
                            {fmt(sv.items.reduce((s, i) => s + Number(i.value), 0))}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
