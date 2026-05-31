'use client'
import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

interface Cat { id: number; name: string; parent_id: number | null; is_active: boolean; children?: Cat[] }

export default function CategoriesPage() {
  const [tree, setTree] = useState<Cat[]>([])
  const load = () => apiFetch<Cat[]>('/api/product-categories').then(setTree).catch(() => {})
  useEffect(() => { load() }, [])

  const add = async (parent_id: number | null) => {
    const name = prompt(parent_id ? 'New sub-category name' : 'New parent category name')?.trim()
    if (!name) return
    try {
      await apiFetch('/api/product-categories', { method: 'POST', body: JSON.stringify({ name, parent_id }) })
      load()
    } catch (e) { alert((e as Error).message) }
  }
  const remove = async (id: number) => {
    try { await apiFetch(`/api/product-categories/${id}`, { method: 'DELETE' }); load() }
    catch (e) { alert((e as Error).message) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-serif font-semibold text-[#1a1814]">Product Categories</h1>
        <button onClick={() => add(null)} className="px-3 py-2 rounded-lg bg-[#b8943f] text-white text-sm font-medium hover:bg-[#a07f33]">+ Parent category</button>
      </div>
      {tree.length === 0 && <p className="text-sm text-[#1a1814]/50">No categories yet. Add a parent category to begin.</p>}
      <div className="space-y-2">
        {tree.map(parent => (
          <div key={parent.id} className="bg-white border border-[#ede9e2] rounded-xl p-3">
            <div className="flex items-center justify-between">
              <span className="font-medium text-[#1a1814]">{parent.name}</span>
              <div className="flex gap-3 text-sm">
                <button onClick={() => add(parent.id)} className="text-[#b8943f] hover:underline">+ Sub</button>
                <button onClick={() => remove(parent.id)} className="text-red-600 hover:underline">Delete</button>
              </div>
            </div>
            {(parent.children ?? []).length > 0 && (
              <div className="mt-2 ml-4 flex flex-wrap gap-2">
                {(parent.children ?? []).map(sub => (
                  <span key={sub.id} className="inline-flex items-center gap-2 px-2 py-1 rounded-lg bg-[#faf8f4] border border-[#ede9e2] text-xs text-[#1a1814]/80">
                    {sub.name}
                    <button onClick={() => remove(sub.id)} className="text-red-500 hover:text-red-700" title="Delete sub-category">×</button>
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
