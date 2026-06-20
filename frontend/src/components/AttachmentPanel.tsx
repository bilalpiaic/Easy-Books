"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  Paperclip, Upload, Eye, Download, Trash2, FileText, Image as ImageIcon,
  FileSpreadsheet, File as FileIcon, AlertCircle,
} from "lucide-react"
import { apiFetch, apiBase } from "@/lib/api"
import { getAuthToken } from "@/lib/auth"
import { fmtDate } from "@/lib/utils"

export type ParentType =
  | "invoice" | "bill" | "transaction" | "payment_received"
  | "bill_payment" | "grn" | "production_order"

export interface Attachment {
  id: number
  parent_type: ParentType
  parent_id: number
  file_name: string
  original_name: string
  mime_type: string
  size_bytes: number
  uploaded_at: string
}

interface Props {
  parentType: ParentType
  parentId: number
  /** When true, the panel renders compactly (list + dropzone) and emits the
   *  currently selected attachment via `onSelect` so the parent page can host
   *  the preview pane in its own split layout. */
  embedded?: boolean
  onSelect?: (att: Attachment | null) => void
}

const MAX_BYTES = 25 * 1024 * 1024
const ACCEPT = [
  "application/pdf",
  "image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-powerpoint",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  "text/csv", "text/plain",
].join(",")

function fileIcon(mime: string) {
  if (mime.startsWith("image/")) return ImageIcon
  if (mime === "application/pdf") return FileText
  if (mime.includes("sheet") || mime === "text/csv" || mime.includes("excel")) return FileSpreadsheet
  return FileIcon
}

function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export default function AttachmentPanel({ parentType, parentId, embedded = false, onSelect }: Props) {
  const [items, setItems] = useState<Attachment[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const reload = useCallback(async () => {
    setLoading(true)
    setErr(null)
    try {
      const list = await apiFetch<Attachment[]>(
        `/api/attachments?parent_type=${parentType}&parent_id=${parentId}`
      )
      setItems(list)
      // Auto-select the most recent attachment so the preview pane shows
      // something on first load. The companion useEffect below pushes the
      // selection to the parent — keep that flow single-sourced.
      if (list.length > 0) {
        setSelectedId((prev) => (prev != null && list.some(a => a.id === prev) ? prev : list[0].id))
      } else {
        setSelectedId(null)
      }
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load attachments")
    } finally {
      setLoading(false)
    }
  }, [parentType, parentId])

  useEffect(() => { reload() }, [reload])

  useEffect(() => {
    if (selectedId == null) { onSelect?.(null); return }
    const cur = items.find(a => a.id === selectedId) ?? null
    onSelect?.(cur)
  }, [selectedId, items, onSelect])

  async function handleFiles(files: FileList | null) {
    if (!files || files.length === 0) return
    setErr(null)
    setUploading(true)
    try {
      for (const file of Array.from(files)) {
        if (file.size > MAX_BYTES) {
          throw new Error(`"${file.name}" exceeds 25 MB limit`)
        }
        const fd = new FormData()
        fd.append("parent_type", parentType)
        fd.append("parent_id", String(parentId))
        fd.append("file", file)
        const token = getAuthToken()
        const res = await fetch(`${apiBase}/api/attachments`, {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
          body: fd,
        })
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          throw new Error(body?.detail ?? `Upload failed (${res.status})`)
        }
      }
      await reload()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Upload failed")
    } finally {
      setUploading(false)
      if (inputRef.current) inputRef.current.value = ""
    }
  }

  async function handleDelete(att: Attachment) {
    if (!confirm(`Delete "${att.original_name}"?`)) return
    setErr(null)
    try {
      const token = getAuthToken()
      const res = await fetch(`${apiBase}/api/attachments/${att.id}`, {
        method: "DELETE",
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      })
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail ?? `Delete failed (${res.status})`)
      }
      if (selectedId === att.id) setSelectedId(null)
      await reload()
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Delete failed")
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <section
      className={
        embedded
          ? "rounded-xl border border-[#ede9e2] bg-white print:hidden"
          : "rounded-2xl border border-[#ede9e2] bg-white shadow-sm print:hidden"
      }
    >
      <header className="flex items-center justify-between gap-2 px-4 py-3 border-b border-[#ede9e2]">
        <div className="flex items-center gap-2 text-sm font-semibold text-[#1a1814]">
          <Paperclip className="w-4 h-4 text-[#b8943f]" />
          Attachments
          <span className="text-xs font-normal text-[#1a1814]/55">({items.length})</span>
        </div>
      </header>

      {/* Drop zone */}
      <div
        className={
          "m-4 rounded-xl border-2 border-dashed px-4 py-5 text-center transition-colors cursor-pointer " +
          (dragOver ? "border-[#b8943f] bg-[#faf6ec]" : "border-[#ede9e2] hover:bg-[#faf8f4]")
        }
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <Upload className="w-5 h-5 text-[#b8943f] mx-auto mb-1.5" />
        <p className="text-xs text-[#1a1814]/70">
          {uploading ? "Uploading…" : "Drop file here or click to browse"}
        </p>
        <p className="text-[10px] text-[#1a1814]/50 mt-0.5">
          PDF · images · Office docs · CSV — max 25 MB
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          className="hidden"
          multiple
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {err && (
        <div className="mx-4 mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 flex items-start gap-2 text-xs text-red-800">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>{err}</span>
        </div>
      )}

      {/* List */}
      <div className="px-4 pb-4">
        {loading ? (
          <p className="text-xs text-[#1a1814]/50 text-center py-3">Loading…</p>
        ) : items.length === 0 ? (
          <p className="text-xs text-[#1a1814]/50 text-center py-3">No attachments yet.</p>
        ) : (
          <ul className="space-y-1.5">
            {items.map((att) => {
              const Icon = fileIcon(att.mime_type)
              const active = selectedId === att.id
              return (
                <li
                  key={att.id}
                  className={
                    "group flex items-center gap-2 px-2.5 py-2 rounded-lg border transition-colors cursor-pointer " +
                    (active
                      ? "bg-[#faf6ec] border-[#b8943f]/40"
                      : "bg-white border-[#ede9e2] hover:bg-[#faf8f4]")
                  }
                  onClick={() => setSelectedId(att.id)}
                >
                  <Icon className="w-4 h-4 flex-shrink-0 text-[#b8943f]" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-[#1a1814] truncate" title={att.original_name}>
                      {att.original_name}
                    </p>
                    <p className="text-[10px] text-[#1a1814]/50">
                      {fmtBytes(att.size_bytes)} · {fmtDate(att.uploaded_at)}
                    </p>
                  </div>
                  <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      title="Preview"
                      onClick={(e) => { e.stopPropagation(); setSelectedId(att.id) }}
                      className="p-1.5 rounded hover:bg-white"
                    >
                      <Eye className="w-3.5 h-3.5 text-[#1a1814]/70" />
                    </button>
                    <a
                      title="Download"
                      href={`${apiBase}/api/attachments/${att.id}/download`}
                      onClick={(e) => { e.stopPropagation(); attachAuthToken(e) }}
                      className="p-1.5 rounded hover:bg-white"
                    >
                      <Download className="w-3.5 h-3.5 text-[#1a1814]/70" />
                    </a>
                    <button
                      title="Delete"
                      onClick={(e) => { e.stopPropagation(); handleDelete(att) }}
                      className="p-1.5 rounded hover:bg-red-50"
                    >
                      <Trash2 className="w-3.5 h-3.5 text-red-600" />
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </section>
  )
}

/** Inline preview pane for use alongside `<AttachmentPanel embedded onSelect />`.
 *  Renders an iframe (PDFs) or `<img>` (images). Office docs fall through to
 *  a download link since browsers don't preview them natively.
 */
export function AttachmentPreviewPane({ att }: { att: Attachment | null }) {
  if (!att) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-center px-6 text-[#1a1814]/55">
        <Paperclip className="w-8 h-8 mb-2 text-[#b8943f]/60" />
        <p className="text-sm">No attachment selected</p>
        <p className="text-xs mt-1">Upload a document on the left, then it appears here.</p>
      </div>
    )
  }

  const url = `${apiBase}/api/attachments/${att.id}/preview`
  // The /preview endpoint requires Authorization. To make a viewable URL we
  // append the token as a query param-free fetch is tricky from inside an
  // <iframe>. Easiest: use a blob URL via a one-shot authenticated fetch.
  return <AuthedViewer url={url} att={att} />
}

function AuthedViewer({ url, att }: { url: string; att: Attachment }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let live = true
    let createdBlob: string | null = null
    setErr(null)
    setBlobUrl(null)
    const token = getAuthToken()
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : undefined })
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        if (!live) return
        createdBlob = URL.createObjectURL(blob)
        setBlobUrl(createdBlob)
      })
      .catch((e: unknown) => {
        if (!live) return
        setErr(e instanceof Error ? e.message : "Preview failed")
      })
    return () => {
      live = false
      if (createdBlob) URL.revokeObjectURL(createdBlob)
    }
  }, [url])

  if (err) return <div className="p-4 text-xs text-red-700">Preview failed: {err}</div>
  if (!blobUrl) return <div className="p-4 text-xs text-[#1a1814]/55">Loading preview…</div>

  if (att.mime_type.startsWith("image/")) {
    return (
      <div className="h-full overflow-auto bg-[#f6f3ee] flex items-start justify-center p-4">
        {/* eslint-disable-next-line @next/next/no-img-element -- blob URL; Next.js Image cannot optimize it */}
        <img src={blobUrl} alt={att.original_name} className="max-w-full h-auto rounded shadow" />
      </div>
    )
  }
  if (att.mime_type === "application/pdf") {
    return <iframe src={blobUrl} className="w-full h-full border-0" title={att.original_name} />
  }
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-6">
      <FileIcon className="w-10 h-10 text-[#b8943f]/60 mb-2" />
      <p className="text-sm font-medium text-[#1a1814]">{att.original_name}</p>
      <p className="text-xs text-[#1a1814]/55 mt-1">
        This file type can&apos;t be previewed in the browser.
      </p>
      <a
        href={blobUrl}
        download={att.original_name}
        className="mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#1a1814] text-white text-xs font-semibold hover:bg-[#b8943f] hover:text-[#1a1814] transition-colors"
      >
        <Download className="w-3.5 h-3.5" /> Download
      </a>
    </div>
  )
}

/** Click-time auth-token injection for the download anchor. Browser anchors
 *  can't carry custom headers, so we hijack the click, fetch with auth,
 *  generate a blob URL, and open/download via a synthetic anchor. */
async function attachAuthToken(e: React.MouseEvent<HTMLAnchorElement>) {
  e.preventDefault()
  const href = e.currentTarget.getAttribute("href")
  if (!href) return
  const token = getAuthToken()
  const res = await fetch(href, { headers: token ? { Authorization: `Bearer ${token}` } : undefined })
  if (!res.ok) return
  const blob = await res.blob()
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = blobUrl
  a.download = ""
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 5000)
}
