"use client"
import type { ReportConfig } from "@/lib/reportTypes"

interface Props { sourceKey: string; config: ReportConfig }

async function download(sourceKey: string, config: ReportConfig, format: "csv" | "xlsx") {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  const base = process.env.NEXT_PUBLIC_API_URL ?? ""
  const res = await fetch(`${base}/api/report-builder/export?format=${format}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ source_key: sourceKey, config }),
  })
  const blob = await res.blob()
  const a = document.createElement("a")
  a.href = URL.createObjectURL(blob)
  a.download = `${sourceKey}.${format}`
  a.click()
  URL.revokeObjectURL(a.href)
}

export default function ExportMenu({ sourceKey, config }: Props) {
  return (
    <details className="relative">
      <summary className="px-3 py-2 text-sm border border-[#ede9e2] rounded-lg cursor-pointer bg-white">Export ▾</summary>
      <div className="absolute z-10 mt-1 right-0 w-40 bg-white border border-[#ede9e2] rounded-lg shadow-lg p-2">
        <button onClick={() => download(sourceKey, config, "csv")} className="w-full text-left px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">CSV</button>
        <button onClick={() => download(sourceKey, config, "xlsx")} className="w-full text-left px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">Excel (XLSX)</button>
        <button onClick={() => window.print()} className="w-full text-left px-2 py-1 text-sm hover:bg-[#f6f3ee] rounded">Print</button>
      </div>
    </details>
  )
}
