import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const fmt = (n: number) => {
  const val = n || 0
  const abs = Math.round(Math.abs(val)).toLocaleString('en-PK')
  return val < 0 ? `(${abs})` : abs
}
/** For a standalone full-currency label (e.g. bank balance KPIs). */
export const fmtPKR = (n: number) => 'PKR ' + fmt(n)
/** Number-only amount — currency param kept for call-site compatibility but not emitted. */
export const fmtAmount = (n: number, _currency?: string) => fmt(n)

/** Convert ISO date string "YYYY-MM-DD" (or datetime) to "dd-mm-yy" display format. */
export function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return ""
  const datePart = dateStr.split("T")[0]
  const parts = datePart.split("-")
  if (parts.length !== 3) return dateStr
  const [y, m, d] = parts
  return `${d}-${m}-${y.slice(2)}`
}

/** Format a JS Date object as "dd-mm-yy". */
export function fmtDateJs(date: Date): string {
  const dd = String(date.getDate()).padStart(2, "0")
  const mm = String(date.getMonth() + 1).padStart(2, "0")
  const yy = String(date.getFullYear()).slice(2)
  return `${dd}-${mm}-${yy}`
}

export function downloadCSV(filename: string, rows: Record<string, unknown>[]) {
  if (rows.length === 0) return
  const headers = Object.keys(rows[0])
  const csvContent = [
    headers.join(","),
    ...rows.map(row =>
      headers.map(h => {
        const val = row[h] ?? ""
        const str = String(val)
        return str.includes(",") || str.includes('"') || str.includes("\n")
          ? `"${str.replace(/"/g, '""')}"`
          : str
      }).join(",")
    ),
  ].join("\n")

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
