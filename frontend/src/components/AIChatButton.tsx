"use client"

import { useState } from "react"
import { Sparkles } from "lucide-react"
import AIChat from "./AIChat"
import { useModules } from "@/context/ModuleContext"

export default function AIChatButton() {
  const { installedModules } = useModules()
  const [open, setOpen] = useState(false)

  if (!installedModules.has("ai_assistant")) return null

  return (
    <>
      <button
        onClick={() => setOpen(prev => !prev)}
        aria-label="Open AI Assistant"
        className={`fixed bottom-36 right-4 md:bottom-6 md:right-20 z-[850] w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all duration-200
          ${open
            ? "bg-[var(--text-primary)] text-white scale-90"
            : "bg-[var(--primary)] text-white hover:scale-110 hover:shadow-xl"
          }`}
      >
        <Sparkles className="w-5 h-5" />
      </button>

      <AIChat open={open} onClose={() => setOpen(false)} />
    </>
  )
}
