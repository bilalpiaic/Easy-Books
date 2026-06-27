"use client"
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

export default function VersionBadge() {
  // Build-time version (set by prepare-resources.sh / install-and-run scripts).
  // Falls back to live API so dev mode and script installs both show correctly.
  const buildVersion = process.env.NEXT_PUBLIC_APP_VERSION
  const [liveVersion, setLiveVersion] = useState<string | null>(null)

  useEffect(() => {
    if (buildVersion) return  // already correct from build
    apiFetch<{ version: string }>("/api/version")
      .then(d => { if (d?.version) setLiveVersion(d.version) })
      .catch(() => {})
  }, [buildVersion])

  const v = buildVersion ?? liveVersion ?? "dev"
  return <span className="text-[11px] text-[var(--text-primary)]/40">Easy-Books v{v}</span>
}
