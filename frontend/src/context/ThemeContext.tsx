"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { apiFetch } from "@/lib/api"

export type ThemeMode  = "light" | "dark" | "system"
export type ColorTheme = "gold" | "blue" | "green" | "rose" | "slate"

interface ThemeCtxValue {
  theme:         ThemeMode
  colorTheme:    ColorTheme
  resolvedTheme: "light" | "dark"
  setTheme:      (t: ThemeMode)  => void
  setColorTheme: (c: ColorTheme) => void
}

const ThemeCtx = createContext<ThemeCtxValue>({
  theme: "light", colorTheme: "gold", resolvedTheme: "light",
  setTheme: () => {}, setColorTheme: () => {},
})

export function useTheme() { return useContext(ThemeCtx) }

function resolveMode(theme: ThemeMode): "light" | "dark" {
  if (theme === "system")
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"
  return theme
}

function applyToDOM(theme: ThemeMode, color: ColorTheme) {
  const resolved = resolveMode(theme)
  document.documentElement.setAttribute("data-theme", resolved)
  document.documentElement.setAttribute("data-color", color)
  return resolved
}

function persistSettings(patch: Record<string, string>) {
  apiFetch("/api/settings", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  }).catch(() => {})
}

export function ThemeProvider({ children, initialTheme, initialColor }: {
  children: ReactNode
  initialTheme?: string
  initialColor?: string
}) {
  const [theme,         setThemeState]     = useState<ThemeMode>( (initialTheme as ThemeMode)  ?? "light")
  const [colorTheme,   setColorThemeState] = useState<ColorTheme>((initialColor as ColorTheme) ?? "gold")
  const [resolvedTheme, setResolved]       = useState<"light" | "dark">("light")

  useEffect(() => {
    const savedTheme = (localStorage.getItem("eb.theme") ?? initialTheme ?? "light") as ThemeMode
    const savedColor = (localStorage.getItem("eb.color") ?? initialColor ?? "gold")  as ColorTheme
    setThemeState(savedTheme)
    setColorThemeState(savedColor)
    const r = applyToDOM(savedTheme, savedColor)
    setResolved(r)

    if (savedTheme === "system") {
      const mq = window.matchMedia("(prefers-color-scheme: dark)")
      const onChange = () => {
        const r2 = mq.matches ? "dark" : "light"
        document.documentElement.setAttribute("data-theme", r2)
        setResolved(r2)
      }
      mq.addEventListener("change", onChange)
      return () => mq.removeEventListener("change", onChange)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const setTheme = (t: ThemeMode) => {
    setThemeState(t)
    localStorage.setItem("eb.theme", t)
    const r = applyToDOM(t, colorTheme)
    setResolved(r)
    persistSettings({ app_theme: t })
  }

  const setColorTheme = (c: ColorTheme) => {
    setColorThemeState(c)
    localStorage.setItem("eb.color", c)
    applyToDOM(theme, c)
    persistSettings({ color_theme: c })
  }

  return (
    <ThemeCtx.Provider value={{ theme, colorTheme, resolvedTheme, setTheme, setColorTheme }}>
      {children}
    </ThemeCtx.Provider>
  )
}
