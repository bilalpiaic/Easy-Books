"use client"

import { useEffect, useState } from "react"
import { getAuthHeader } from "@/lib/auth"
import { apiBase } from "@/lib/api"

/** Fetch a tenant file with the session token so logos work after /uploads went private. */
export function AuthFileImg({
  src,
  alt,
  className,
}: {
  src: string
  alt: string
  className?: string
}) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null)

  useEffect(() => {
    if (!src) return
    if (src.startsWith("blob:") || src.startsWith("data:")) {
      setBlobUrl(src)
      return
    }
    let objectUrl: string | null = null
    let cancelled = false
    const path = src.startsWith("http") ? src : `${apiBase}${src}`
    fetch(path, { headers: { ...getAuthHeader() } })
      .then(res => {
        if (!res.ok) throw new Error(String(res.status))
        return res.blob()
      })
      .then(blob => {
        if (cancelled) return
        objectUrl = URL.createObjectURL(blob)
        setBlobUrl(objectUrl)
      })
      .catch(() => {
        if (!cancelled) setBlobUrl(null)
      })
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [src])

  if (!blobUrl) return null
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={blobUrl} alt={alt} className={className} />
}
