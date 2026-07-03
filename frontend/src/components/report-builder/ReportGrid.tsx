"use client"
import SortableHeader from "@/components/SortableHeader"
import type { RunResult, SortClause } from "@/lib/reportTypes"

interface Props {
  result: RunResult | null
  sort: SortClause[]
  onSort: (field: string, dir: "asc" | "desc") => void
  onCellFilter: (field: string, value: string) => void
}

export default function ReportGrid({ result, sort, onSort, onCellFilter }: Props) {
  if (!result) return <div className="p-8 text-[var(--text-muted)]">Configure a report to begin.</div>
  const sb = sort[0]?.field ?? ""
  const sd = sort[0]?.dir ?? "asc"
  return (
    <div className="table-freeze freeze-col border border-[var(--border)] rounded-xl bg-white">
      <table className="w-full text-sm">
        <thead className="bg-[var(--bg-page)] border-b border-[var(--border)]">
          <tr>{result.columns.map(c => (
            <SortableHeader key={c.key} label={c.label} field={c.key}
              sortBy={sb} sortDir={sd} onSort={onSort}
              className={c.type === "money" || c.type === "number" ? "text-right" : ""} />
          ))}</tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i} className="border-b border-[#f1ede6] hover:bg-[#faf8f4]">
              {result.columns.map(c => (
                <td key={c.key}
                  onClick={() => onCellFilter(c.key, String(row[c.key] ?? ""))}
                  className={`px-6 py-3 cursor-pointer ${c.type === "money" || c.type === "number" ? "text-right tabular-nums" : ""}`}
                  title="Filter by this value">
                  {row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        {result.footers && (
          <tfoot className="bg-[var(--bg-page)] font-bold border-t-2 border-[var(--primary)]">
            <tr>{result.columns.map((c, i) => (
              <td key={c.key} className={`px-6 py-3 ${c.type === "money" ? "text-right tabular-nums" : ""}`}>
                {i === 0 ? "TOTAL" : (result.footers?.[c.key] ?? "")}
              </td>
            ))}</tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
