"use client"

import { useState } from "react"
import { X, Save, Wand2 } from "lucide-react"
import { apiFetch } from "@/lib/api"

interface Account {
  id: number
  code: string
  name: string
  type: string
  parent_id?: number | null
  is_group?: boolean
  is_active?: boolean
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
  const [isGroup, setIsGroup] = useState<boolean>(account?.is_group ?? false)
  const [isActive, setIsActive] = useState<boolean>(account?.is_active ?? true)
  const [saving, setSaving] = useState(false)
  const [suggesting, setSuggesting] = useState(false)
  const [error, setError] = useState("")

  // When parent changes, pre-fill type from parent's type
  const handleParentChange = (newParentId: string) => {
    setParentId(newParentId)
    if (newParentId) {
      const parent = allAccounts.find(a => String(a.id) === newParentId)
      if (parent) {
        setType(parent.type)
      }
    }
  }

  const handleSuggest = async () => {
    setSuggesting(true)
    setError("")
    try {
      const params = new URLSearchParams()
      if (parentId) params.set("parent_id", parentId)
      const res = await apiFetch<{ code: string }>(`/api/accounts/next-code?${params}`)
      setCode(res.code)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setSuggesting(false)
    }
  }

  const handleSave = async () => {
    if (!code.trim() || !name.trim()) {
      setError("Code and name are required.")
      return
    }
    setSaving(true)
    setError("")
    try {
      const payload = {
        code,
        name,
        type,
        parent_id: parentId ? parseInt(parentId) : null,
        is_group: isGroup,
        is_active: isActive,
      }
      if (account) {
        await apiFetch(`/api/accounts/${account.id}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
      } else {
        await apiFetch("/api/accounts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
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
      <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-8 max-h-[90vh] overflow-y-auto">
        <button onClick={onClose} className="absolute top-4 right-4 text-black/40 hover:text-black">
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-2xl font-serif text-[#1a1814] mb-6">
          {account ? "Edit Account" : "Add Account"}
        </h2>

        <div className="space-y-4">
          {/* Parent picker */}
          {allAccounts.length > 0 && (
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
                Parent Account
              </label>
              <select
                value={parentId}
                onChange={e => handleParentChange(e.target.value)}
                className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
              >
                <option value="">— None (top-level) —</option>
                {allAccounts.filter(a => a.id !== account?.id).map(a => (
                  <option key={a.id} value={a.id}>{a.code} — {a.name}</option>
                ))}
              </select>
            </div>
          )}

          {/* Account Code + Suggest */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
              Account Code
            </label>
            <div className="flex gap-2">
              <input
                value={code}
                onChange={e => setCode(e.target.value)}
                placeholder="e.g. 1010"
                className="flex-1 ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
              />
              <button
                type="button"
                onClick={handleSuggest}
                disabled={suggesting}
                title="Suggest next code"
                className="px-3 py-2 border border-[#b8943f] text-[#b8943f] rounded-xl hover:bg-[#b8943f] hover:text-black transition-colors disabled:opacity-50 flex items-center gap-1 text-xs font-bold whitespace-nowrap"
              >
                <Wand2 className="w-3.5 h-3.5" />
                {suggesting ? "…" : "Suggest"}
              </button>
            </div>
          </div>

          {/* Account Name */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
              Account Name
            </label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Cash in Hand"
              className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            />
          </div>

          {/* Account Type */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/75 mb-1">
              Account Type
            </label>
            <select
              value={type}
              onChange={e => setType(e.target.value)}
              className="w-full ui-field bg-[#f6f3ee] rounded-xl outline-none focus:ring-2 focus:ring-[#b8943f]"
            >
              {ACCOUNT_TYPES.map(t => <option key={t}>{t}</option>)}
            </select>
          </div>

          {/* Toggles */}
          <div className="space-y-3 pt-1">
            <label className="flex items-start gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={isGroup}
                onChange={e => setIsGroup(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-[#b8943f]"
              />
              <span>
                <span className="block text-sm font-semibold text-[#1a1814]">
                  Header / group account
                </span>
                <span className="block text-xs text-[#1a1814]/55">
                  Cannot be posted to directly — used for grouping only
                </span>
              </span>
            </label>
            <label className="flex items-start gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={isActive}
                onChange={e => setIsActive(e.target.checked)}
                className="mt-0.5 w-4 h-4 accent-[#b8943f]"
              />
              <span>
                <span className="block text-sm font-semibold text-[#1a1814]">Active</span>
                <span className="block text-xs text-[#1a1814]/55">
                  Inactive accounts cannot be posted to
                </span>
              </span>
            </label>
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
