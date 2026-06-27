"use client"

import { Printer } from "lucide-react"

interface PrintButtonProps {
  label?: string
  className?: string
}

export default function PrintButton({ label = "Print", className = "" }: PrintButtonProps) {
  return (
    <button
      onClick={() => window.print()}
      className={`flex items-center gap-2 px-4 py-2 border border-[var(--border)] rounded-xl text-sm font-bold hover:bg-[var(--bg-page)] transition-colors print:hidden ${className}`}
    >
      <Printer className="w-4 h-4" />
      {label}
    </button>
  )
}
