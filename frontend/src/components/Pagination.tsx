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

  return (
    <div className="flex items-center justify-between px-2 py-3 print:hidden">
      <span className="text-xs text-[var(--text-muted)]">
        Showing {Math.min((page - 1) * pageSize + 1, total)}–{Math.min(page * pageSize, total)} of {total}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="w-8 h-8 flex items-center justify-center rounded border border-[var(--border)] hover:bg-[var(--bg-page)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
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
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className="w-8 h-8 flex items-center justify-center rounded border border-[var(--border)] hover:bg-[var(--bg-page)] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
