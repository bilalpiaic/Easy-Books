"use client"

import { ChevronLeft, ChevronRight } from "lucide-react"

interface PaginationProps {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
}

export default function Pagination({ page, pageSize, total, onPage }: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  if (totalPages <= 1) return null

  // SM: at most 3 page buttons around current; md+: up to 7 from the start
  const windowSize = 3
  let pageNums: number[]
  if (totalPages <= 7) {
    pageNums = Array.from({ length: totalPages }, (_, i) => i + 1)
  } else {
    const start = Math.max(1, Math.min(page - 1, totalPages - windowSize + 1))
    pageNums = Array.from({ length: windowSize }, (_, i) => start + i)
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-2 py-3 print:hidden">
      <span className="text-xs text-[var(--text-muted)] tabular-nums">
        <span className="sm:hidden">
          {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} / {total}
        </span>
        <span className="hidden sm:inline">
          Showing {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
        </span>
      </span>
      <div className="flex items-center gap-1 ml-auto">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="w-8 h-8 flex items-center justify-center rounded border border-[var(--border)] hover:bg-[var(--bg-page)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Previous page"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
        {/* Desktop: up to 7 numbered buttons */}
        <div className="hidden sm:flex items-center gap-1">
          {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
            const p = i + 1
            return (
              <button
                key={p}
                onClick={() => onPage(p)}
                className={`w-8 h-8 text-xs font-bold rounded border transition-colors ${
                  p === page
                    ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                    : "border-[var(--border)] hover:bg-[var(--bg-page)]"
                }`}
              >
                {p}
              </button>
            )
          })}
        </div>
        {/* SM: compact window + page indicator */}
        <div className="flex sm:hidden items-center gap-1">
          {pageNums.map((p) => (
            <button
              key={p}
              onClick={() => onPage(p)}
              className={`w-8 h-8 text-xs font-bold rounded border transition-colors ${
                p === page
                  ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                  : "border-[var(--border)] hover:bg-[var(--bg-page)]"
              }`}
            >
              {p}
            </button>
          ))}
          {totalPages > windowSize && (
            <span className="px-1 text-[11px] text-[var(--text-muted)] tabular-nums">
              / {totalPages}
            </span>
          )}
        </div>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className="w-8 h-8 flex items-center justify-center rounded border border-[var(--border)] hover:bg-[var(--bg-page)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="Next page"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
