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
    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 print:hidden">
      {/* Search */}
      <div className="relative flex-1 min-w-0 sm:min-w-48">
        <Search className="absolute left-2.5 sm:left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--border)] pointer-events-none" />
        <input
          type="text"
          value={search}
          onChange={e => onSearch(e.target.value)}
          placeholder={placeholder}
          className="w-full pl-8 sm:pl-9 pr-3 py-1.5 sm:py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)]"
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
          className="w-full sm:w-auto px-2 sm:px-3 py-1.5 sm:py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] bg-white sm:max-w-none"
        >
          <option value="">All statuses</option>
          {statuses.map(s => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
      )}

      {/* Date range — stack tighter on sm */}
      {onDateFrom && (
        <div className="flex items-center gap-1 w-full sm:w-auto">
          <input
            type="date"
            value={dateFrom ?? ''}
            onChange={e => onDateFrom(e.target.value)}
            className="flex-1 sm:flex-none px-2 py-1.5 sm:py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] min-w-0"
          />
          <span className="text-[var(--text-muted)] text-xs shrink-0">–</span>
          <input
            type="date"
            value={dateTo ?? ''}
            onChange={e => onDateTo?.(e.target.value)}
            className="flex-1 sm:flex-none px-2 py-1.5 sm:py-2 border border-[var(--border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary)] min-w-0"
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
