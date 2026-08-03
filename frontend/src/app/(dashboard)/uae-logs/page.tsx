"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

/** Legacy path — keep bookmarks working. */
export default function UaeLogsRedirect() {
  const router = useRouter()
  useEffect(() => { router.replace("/uae/logs") }, [router])
  return null
}
