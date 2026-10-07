"use client"

import { useEffect, useRef, useState } from "react"
import { Check, Copy } from "lucide-react"
import { QRCodeSVG } from "qrcode.react"

export function TotpQrDisplay({
  otpauthUrl,
  secret,
}: {
  otpauthUrl: string
  secret: string
}) {
  const [copied, setCopied] = useState(false)
  const copiedTimer = useRef<number | null>(null)

  useEffect(() => () => {
    if (copiedTimer.current != null) window.clearTimeout(copiedTimer.current)
  }, [])

  async function copySecret() {
    try {
      await navigator.clipboard.writeText(secret)
      setCopied(true)
      if (copiedTimer.current != null) window.clearTimeout(copiedTimer.current)
      copiedTimer.current = window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }

  return (
    <div className="flex flex-col sm:flex-row gap-4 items-start bg-[var(--bg-page)] rounded-lg p-4">
      <div
        className="bg-white p-3 rounded-lg border border-[var(--border)] shrink-0"
        data-testid="totp-qr"
        role="img"
        aria-label="QR code to add Easy-Books to your authenticator app"
      >
        <QRCodeSVG
          value={otpauthUrl}
          size={168}
          level="M"
          bgColor="#ffffff"
          fgColor="#1a1814"
        />
      </div>
      <div className="space-y-2 min-w-0">
        <p className="text-sm text-[var(--text-primary)]">
          Scan this QR code with Google Authenticator, Authy, 1Password, or Microsoft Authenticator.
        </p>
        <p className="text-xs text-[var(--text-primary)]/60">
          Cannot scan? Enter this secret manually:
        </p>
        <div className="flex items-start gap-2">
          <code className="flex-1 text-xs break-all select-all bg-white border border-[var(--border)] rounded-md px-2 py-1.5">
            {secret}
          </code>
          <button
            type="button"
            onClick={copySecret}
            className="shrink-0 inline-flex items-center gap-1 px-2 py-1.5 rounded-md border border-[var(--border)] text-xs font-medium hover:bg-white"
            aria-label="Copy authenticator secret"
          >
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      </div>
    </div>
  )
}
