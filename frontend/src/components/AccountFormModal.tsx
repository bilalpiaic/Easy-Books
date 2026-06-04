"use client"

import { useState } from "react"
import { X, Save } from "lucide-react"
import { apiFetch } from "@/lib/api"

interface Account {
  id: number
  code: string
  name: string
  type: string
  parent_id?: number | null
}

interface AccountFormModalProps {
  account?: Account | null
  onClose: () => void
  onSaved: () => void
  allAccounts?: Account[]
}

const ACCOUNT_TYPES = ["Asset", "Liability", "Equity", "Revenue", "Expense"]

export default function AccountFormModal({ account, onClose, onSaved, allAccounts = [] }: AccountFormModalProps) {
  const [code, setCode] = useState(account?.code ?? "")
  const [name, setName] = useState(account?.name ?? "")
  const [type, setType] = useState(account?.type ?? "Asset")
  const [parentId, setParentId] = useState<string>(account?.parent_id ? String(account.parent_id) : "")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const handleSave = async () => {
    if (!code.trim() || !name.trim()) {
      setError("Code and name are required.")
      return
    }
    setSaving(true)
    setError("")
    try {
      if (account) {
        await apiFetch(`/api/accounts/${account.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, name, type, parent_id: parentId ? parseInt(parentId) : null }),
        })
      } else {
        await apiFetch("/api/accounts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code, name, type, parent_id: parentId ? parseInt(parentId) : null }),
        })
      }
      onSaved()
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8">
        <button onClick={onClose} className="absolute top-4 right-4 text-black/40 hover:text-black">
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-2xl font-serif text-[#1a1814] mb-6">
          {account ? "Edit Account" : "Add Account"}
        </h2>

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Account Code</label>
            <input
              value={code}
              onChange={e => setCode(e.target.value)}
              placeholder="e.g. 1010"
              className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            />
          </div>
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Account Name</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Cash in Hand"
              className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            />
          </div>
          {allAccounts.length > 0 && (
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Parent Account (optional)</label>
              <select
                value={parentId}
                onChange={e => setParentId(e.target.value)}
                className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
              >
                <option value="">— No parent (top-level) —</option>
                {allAccounts.filter(a => a.id !== account?.id).map(a => (
                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                ))}
              </select>
            </div>
          )}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">Account Type</label>
            <select
              value={type}
              onChange={e => setType(e.target.value)}
              className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            >
              {ACCOUNT_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>

          {error && <p className="text-red-600 text-sm">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              onClick={onClose}
              className="px-6 py-3 border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-3 bg-[#1a1814] text-white rounded-xl font-bold flex items-center gap-2 hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
