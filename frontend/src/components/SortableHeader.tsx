'use client'

import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'

interface Props {
  label: string
  field: string
  sortBy: string
  sortDir: 'asc' | 'desc'
  onSort: (field: string, dir: 'asc' | 'desc') => void
  className?: string
}

export default function SortableHeader({ label, field, sortBy, sortDir, onSort, className = '' }: Props) {
  const active = sortBy === field

  const toggle = () => {
    if (active) {
      onSort(field, sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      onSort(field, 'asc')
    }
  }

  return (
    <th
      onClick={toggle}
      className={`cursor-pointer select-none group ui-th text-xs font-bold uppercase tracking-widest text-[var(--text-muted)] ${className}`}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        <span className={`transition-colors print:hidden ${active ? 'text-[var(--primary)]' : 'text-[var(--border)] group-hover:text-[var(--text-muted)]'}`}>
          {active
            ? sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />
            : <ChevronsUpDown className="w-3 h-3" />
          }
        </span>
      </span>
    </th>
  )
}
