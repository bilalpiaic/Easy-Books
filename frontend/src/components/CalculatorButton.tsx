"use client"

import { useState } from "react"
import { Calculator as CalculatorIcon } from "lucide-react"
import Calculator from "./Calculator"

export default function CalculatorButton() {
  const [open, setOpen] = useState(false)

  return (
    <>
      {/* Stacked directly above AIChatButton on the same right edge — NOT
          bottom-left, which collides with Next.js's own dev-mode route
          indicator badge in that corner (dev builds only, but real). */}
      <button
        onClick={() => setOpen(prev => !prev)}
        aria-label="Open Calculator"
        className={`fixed bottom-52 right-4 md:bottom-24 md:right-20 z-[850] w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all duration-200
          ${open
            ? "bg-[var(--text-primary)] text-white scale-90"
            : "bg-[var(--primary)] text-white hover:scale-110 hover:shadow-xl"
          }`}
      >
        <CalculatorIcon className="w-5 h-5" />
      </button>

      <Calculator open={open} onClose={() => setOpen(false)} />
    </>
  )
}
