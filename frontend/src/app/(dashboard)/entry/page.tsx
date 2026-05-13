"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2, Save, AlertCircle } from "lucide-react"
import { getAuthHeader } from "@/lib/auth"
import { useRouter } from "next/navigation"

interface Account {
  id: number
  code: string
  name: string
}

interface EntryRow {
  account_id: string
  debit: string
  credit: string
}

export default function NewEntryPage() {
  const router = useRouter()
  const [accounts, setAccounts] = useState<Account[]>([])
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])
  const [description, setDescription] = useState("")
  const [rows, setRows] = useState<EntryRow[]>([
    { account_id: "", debit: "", credit: "" },
    { account_id: "", debit: "", credit: "" }
  ])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState("")

  useEffect(() => {
    fetch("http://localhost:8000/api/accounts", {
      headers: getAuthHeader()
    })
      .then(res => res.json())
      .then(setAccounts)
      .catch(console.error)
  }, [])

  const addRow = () => {
    setRows([...rows, { account_id: "", debit: "", credit: "" }])
  }

  const removeRow = (index: number) => {
    if (rows.length <= 2) return
    setRows(rows.filter((_, i) => i !== index))
  }

  const updateRow = (index: number, field: keyof EntryRow, value: string) => {
    const newRows = [...rows]
    if (field === 'debit' && value !== "") newRows[index].credit = ""
    if (field === 'credit' && value !== "") newRows[index].debit = ""
    newRows[index][field] = value
    setRows(newRows)
  }

  const totalDebit = rows.reduce((sum, row) => sum + (parseFloat(row.debit) || 0), 0)
  const totalCredit = rows.reduce((sum, row) => sum + (parseFloat(row.credit) || 0), 0)
  const difference = Math.abs(totalDebit - totalCredit)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (difference > 0.01) {
      setError("Journal entry is not balanced. Debits must equal Credits.")
      return
    }
    
    setIsSubmitting(true)
    setError("")

    const payload = {
      date,
      description,
      entries: rows
        .filter(r => r.account_id && (parseFloat(r.debit) > 0 || parseFloat(r.credit) > 0))
        .map(r => ({
          account_id: parseInt(r.account_id),
          debit: parseFloat(r.debit) || 0,
          credit: parseFloat(r.credit) || 0
        }))
    }

    try {
      const res = await fetch("http://localhost:8000/api/transactions", {
        method: "POST",
        headers: {
          ...getAuthHeader(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || "Failed to save transaction")
      }

      router.push("/journal")
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-serif text-[#1a1814]">New Journal Entry</h1>
          <p className="text-[#1a1814]/60">Record a manual double-entry transaction</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="bg-white p-8 rounded-3xl shadow-xl shadow-black/5 border border-[#1a1814]/5 space-y-6">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-2">Transaction Date</label>
              <input 
                type="date" 
                value={date}
                onChange={e => setDate(e.target.value)}
                className="w-full px-4 py-3 bg-[#f6f3ee] border-none rounded-xl focus:ring-2 focus:ring-[#b8943f] outline-none"
                required
              />
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-widest text-[#1a1814]/40 mb-2">Description / Memo</label>
              <input 
                type="text" 
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder="e.g. Monthly Rent Payment"
                className="w-full px-4 py-3 bg-[#f6f3ee] border-none rounded-xl focus:ring-2 focus:ring-[#b8943f] outline-none"
                required
              />
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-left">
                  <th className="pb-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40">Account</th>
                  <th className="pb-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 w-32 text-right">Debit</th>
                  <th className="pb-4 text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 w-32 text-right">Credit</th>
                  <th className="pb-4 w-12"></th>
                </tr>
              </thead>
              <tbody className="space-y-2">
                {rows.map((row, idx) => (
                  <tr key={idx}>
                    <td className="pr-4 py-2">
                      <select 
                        value={row.account_id}
                        onChange={e => updateRow(idx, 'account_id', e.target.value)}
                        className="w-full px-4 py-3 bg-[#f6f3ee] border-none rounded-xl focus:ring-2 focus:ring-[#b8943f] outline-none text-sm"
                        required
                      >
                        <option value="">Select Account</option>
                        {accounts.map(acc => (
                          <option key={acc.id} value={acc.id}>{acc.code} - {acc.name}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-2 py-2">
                      <input 
                        type="number" 
                        step="0.01"
                        value={row.debit}
                        onChange={e => updateRow(idx, 'debit', e.target.value)}
                        placeholder="0.00"
                        className="w-full px-4 py-3 bg-[#f6f3ee] border-none rounded-xl focus:ring-2 focus:ring-[#b8943f] outline-none text-right text-sm"
                      />
                    </td>
                    <td className="pl-4 py-2">
                      <input 
                        type="number" 
                        step="0.01"
                        value={row.credit}
                        onChange={e => updateRow(idx, 'credit', e.target.value)}
                        placeholder="0.00"
                        className="w-full px-4 py-3 bg-[#f6f3ee] border-none rounded-xl focus:ring-2 focus:ring-[#b8943f] outline-none text-right text-sm"
                      />
                    </td>
                    <td className="pl-4 py-2">
                      <button 
                        type="button"
                        onClick={() => removeRow(idx)}
                        className="p-2 text-red-400 hover:text-red-600 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button 
            type="button"
            onClick={addRow}
            className="text-[#b8943f] text-sm font-bold flex items-center gap-2 hover:underline"
          >
            <Plus className="w-4 h-4" />
            Add Line Item
          </button>

          <div className="pt-6 border-t border-[#1a1814]/5 flex justify-end gap-12 text-sm font-mono">
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">Total Debit</div>
              <div className="text-lg font-bold text-[#1a1814]">{totalDebit.toFixed(2)}</div>
            </div>
            <div className="text-right">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">Total Credit</div>
              <div className="text-lg font-bold text-[#1a1814]">{totalCredit.toFixed(2)}</div>
            </div>
            <div className="text-right border-l border-[#1a1814]/5 pl-12">
              <div className="text-[10px] font-bold uppercase tracking-widest text-[#1a1814]/40 mb-1">Difference</div>
              <div className={`text-lg font-bold ${difference > 0.01 ? 'text-red-500' : 'text-green-600'}`}>
                {difference.toFixed(2)}
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-100 text-red-700 p-4 rounded-xl flex items-center gap-3 text-sm">
            <AlertCircle className="w-5 h-5" />
            {error}
          </div>
        )}

        <div className="flex justify-end gap-4">
          <button 
            type="button"
            onClick={() => router.back()}
            className="px-8 py-4 bg-white border border-[#1a1814]/10 rounded-xl font-bold hover:bg-[#f6f3ee] transition-colors"
          >
            Cancel
          </button>
          <button 
            type="submit"
            disabled={isSubmitting || difference > 0.01}
            className="px-8 py-4 bg-[#1a1814] text-white rounded-xl font-bold flex items-center gap-2 hover:bg-[#b8943f] hover:text-black transition-all disabled:opacity-50"
          >
            <Save className="w-5 h-5" />
            {isSubmitting ? "Saving..." : "Post Transaction"}
          </button>
        </div>
      </form>
    </div>
  )
}
