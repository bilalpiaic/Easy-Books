'use client'

import { Search, X } from 'lucide-react'

export interface FilterBarProps {
  search: string
  onSearch: (v: string) => void
  statuses?: string[]
  status?: string
  onStatus?: (v: string) => void
  dateFrom?: string
  dateTo?: string
  onDateFrom?: (v: string) => void
  onDateTo?: (v: string) => void
  placeholder?: string
}

export default function FilterBar({
  search, onSearch,
  statuses, status, onStatus,
  dateFrom, dateTo, onDateFrom, onDateTo,
  placeholder = 'Search…',
}: FilterBarProps) {
  const hasFilters = !!status || !!dateFrom || !!dateTo

  return (
    <div className="flex flex-wrap items-center gap-2 print:hidden">
      {/* Search */}
      <div className="relative flex-1 min-w-0 sm:min-w-48">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--border)] pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={e => onSearch(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-9 pr-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
        />
        {search && (
          <button onClick={() => onSearch('')} className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--border)] hover:text-[var(--text-muted)]">
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Status filter */}
      {statuses && onStatus && (
        <select
          value={status ?? ''}
          onChange={e => onStatus(e.target.value)}
          className="px-3 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] bg-white"
        >
          <option value="">All statuses</option>
          {statuses.map(s => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
      )}

      {/* Date range */}
      {onDateFrom && (
        <div className="flex items-center gap-1">
          <input
            type="date"
            value={dateFrom ?? ''}
            onChange={e => onDateFrom(e.target.value)}
            className="px-2 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
          />
          <span className="text-[var(--text-muted)] text-xs">–</span>
          <input
            type="date"
            value={dateTo ?? ''}
            onChange={e => onDateTo?.(e.target.value)}
            className="px-2 py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
          />
        </div>
      )}

      {/* Clear all */}
      {hasFilters && (
        <button
          onClick={() => { onStatus?.(''); onDateFrom?.(''); onDateTo?.('') }}
          className="flex items-center gap-1 text-xs text-[var(--primary)] hover:text-[#8a6d2e] font-medium"
        >
          <X className="w-3 h-3" /> Clear
        </button>
      )}
    </div>
  )
}
