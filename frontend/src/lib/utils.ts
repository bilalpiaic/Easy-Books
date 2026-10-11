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

/** English 3-letter months for `dd-mmm-yy` display (e.g. 11-Oct-26). */
export const MONTHS_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
] as const

const DISPLAY_DATE_RE = /^\d{2}-[A-Z][a-z]{2}-\d{2}$/

function pad2(n: number): string {
  return String(n).padStart(2, "0")
}

function fromYmd(y: string, m: string, d: string): string | null {
  const mi = Number(m)
  const di = Number(d)
  if (!Number.isInteger(mi) || mi < 1 || mi > 12) return null
  if (!Number.isInteger(di) || di < 1 || di > 31) return null
  if (!/^\d{2,4}$/.test(y)) return null
  return `${pad2(di)}-${MONTHS_SHORT[mi - 1]}-${y.slice(-2)}`
}

/** Convert ISO date string "YYYY-MM-DD" (or datetime) to "dd-mmm-yy" display format. */
export function fmtDate(dateStr: string | null | undefined): string {
  if (!dateStr) return ""
  const datePart = dateStr.split("T")[0].split(" ")[0]
  if (DISPLAY_DATE_RE.test(datePart)) return datePart
  const parts = datePart.split("-")
  if (parts.length !== 3) return dateStr
  const [y, m, d] = parts
  return fromYmd(y, m, d) ?? dateStr
}

/** Returns today's date as YYYY-MM-DD in the browser's local timezone.
 *  Use instead of new Date().toISOString().split("T")[0] which gives UTC. */
export function todayLocal(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/** Format a JS Date object as "dd-mmm-yy". */
export function fmtDateJs(date: Date): string {
  if (Number.isNaN(date.getTime())) return ""
  return `${pad2(date.getDate())}-${MONTHS_SHORT[date.getMonth()]}-${String(date.getFullYear()).slice(-2)}`
}

/** Format a JS Date as "dd-mmm-yy HH:mm" in local time. */
export function fmtDateTimeJs(date: Date): string {
  if (Number.isNaN(date.getTime())) return ""
  return `${fmtDateJs(date)} ${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

/** ISO datetime (or date) → "dd-mmm-yy HH:mm". Date-only values omit the time. */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return ""
  const hasClock = iso.includes("T") || /\d{2}:\d{2}/.test(iso)
  if (!hasClock) return fmtDate(iso)
  const normalised = iso.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(iso) ? iso : iso.includes("T") ? `${iso}Z` : iso
  const d = new Date(normalised)
  if (Number.isNaN(d.getTime())) return fmtDate(iso)
  return fmtDateTimeJs(d)
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
