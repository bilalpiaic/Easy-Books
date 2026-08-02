import { apiBase, networkErrorMessage } from "./api"

function httpDetail(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail
    if (typeof d === "string" && d.trim()) return d
    if (Array.isArray(d)) {
      return d.map((x) => (typeof x === "object" && x && "msg" in x ? String((x as { msg: unknown }).msg) : String(x))).join(", ") || fallback
    }
  }
  return fallback
}

async function triggerDownload(blob: Blob, filename: string): Promise<void> {
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** Download a PDF from an authenticated API path as a file. */
export async function downloadPdf(path: string, filename: string): Promise<void> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  const url = `${apiBase}${path.startsWith("/") ? path : `/${path}`}`
  let res: Response
  try {
    res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  } catch (err: unknown) {
    throw new Error(networkErrorMessage(err, "PDF download failed"))
  }
  if (!res.ok) {
    let detail = "PDF download failed"
    try {
      detail = httpDetail(await res.json(), detail)
    } catch { /* ignore non-JSON error bodies */ }
    throw new Error(detail)
  }
  await triggerDownload(await res.blob(), filename)
}

/** Download a PDF from a public portal URL (no auth header). */
export async function downloadPublicPdf(url: string, filename: string): Promise<void> {
  let res: Response
  try {
    res = await fetch(url)
  } catch (err: unknown) {
    throw new Error(networkErrorMessage(err, "PDF download failed"))
  }
  if (!res.ok) {
    let detail = "PDF download failed"
    try {
      detail = httpDetail(await res.json(), detail)
    } catch { /* ignore */ }
    throw new Error(detail)
  }
  await triggerDownload(await res.blob(), filename)
}
