"use client"
import { useEffect, useState } from "react"
import { apiFetch } from "@/lib/api"

export default function VersionBadge() {
  const buildVersion = process.env.NEXT_PUBLIC_APP_VERSION
  const buildCommit  = process.env.NEXT_PUBLIC_GIT_COMMIT ?? ""
  const [liveVersion, setLiveVersion] = useState<string | null>(null)

  useEffect(() => {
    if (buildVersion) return
    apiFetch<{ version: string }>("/api/version")
      .then(d => { if (d?.version) setLiveVersion(d.version) })
      .catch(() => {})
  }, [buildVersion])

  const v      = buildVersion ?? liveVersion ?? "dev"
  const commit = buildCommit.length >= 7 ? buildCommit.slice(0, 7) : buildCommit

  return (
    <span className="text-[11px] text-[var(--text-primary)]/40">
      Easy-Books v{v}
      {commit && commit !== "dev" && (
        <span className="ml-1 font-mono opacity-60">({commit})</span>
      )}
    </span>
  )
}
