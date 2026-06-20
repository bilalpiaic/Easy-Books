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
