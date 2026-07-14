"use client"

import { useEffect, useRef, useState } from "react"

export type PanelPos = { x: number; y: number }

function clampToViewport(x: number, y: number, w: number, h: number): PanelPos {
  const maxX = Math.max(window.innerWidth - w, 0)
  const maxY = Math.max(window.innerHeight - h, 0)
  return { x: Math.min(Math.max(x, 0), maxX), y: Math.min(Math.max(y, 0), maxY) }
}

/**
 * Drag-anywhere + minimize state for a floating panel (AI Assistant,
 * Calculator, …). Position/minimized are per-browser UI preferences
 * (localStorage, not the Settings API) keyed by `storageKey`.
 *
 * Consumers attach `panelRef` to the panel's root div, spread
 * `dragHandleProps` onto whatever element should act as the drag handle
 * (a header bar), and render at `pos` via inline style once it's non-null —
 * until the user drags at least once, `pos` stays null and the panel should
 * use its own default CSS corner placement instead.
 */
export function useDraggablePanel(storageKey: string) {
  const posKey = `${storageKey}.pos`
  const minKey = `${storageKey}.minimized`

  const [pos, setPos] = useState<PanelPos | null>(null)
  const [minimized, setMinimized] = useState(false)
  const [dragging, setDragging] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)
  const dragOffset = useRef<PanelPos>({ x: 0, y: 0 })

  useEffect(() => {
    try {
      const raw = localStorage.getItem(posKey)
      if (raw) setPos(JSON.parse(raw))
      setMinimized(localStorage.getItem(minKey) === "1")
    } catch {
      // Corrupt/blocked localStorage — fall back to the default corner position.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const startDrag = (e: React.PointerEvent) => {
    // Don't start a drag when the pointer-down originated on a button inside
    // the handle (e.g. minimize/close) — those need their own click to fire.
    if ((e.target as HTMLElement).closest("button")) return
    const rect = panelRef.current?.getBoundingClientRect()
    if (!rect) return
    dragOffset.current = { x: e.clientX - rect.left, y: e.clientY - rect.top }
    setDragging(true)
  }

  useEffect(() => {
    if (!dragging) return
    const onMove = (e: PointerEvent) => {
      const rect = panelRef.current?.getBoundingClientRect()
      const w = rect?.width ?? 320
      const h = rect?.height ?? 400
      setPos(clampToViewport(e.clientX - dragOffset.current.x, e.clientY - dragOffset.current.y, w, h))
    }
    const onUp = () => {
      setDragging(false)
      setPos(prev => {
        if (prev) {
          try { localStorage.setItem(posKey, JSON.stringify(prev)) } catch { /* ignore */ }
        }
        return prev
      })
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
    }
  }, [dragging, posKey])

  // Keep the panel on-screen if the window shrinks (e.g. rotating a tablet)
  // after a position was dragged.
  useEffect(() => {
    if (!pos) return
    const onResize = () => {
      const rect = panelRef.current?.getBoundingClientRect()
      if (!rect) return
      setPos(p => (p ? clampToViewport(p.x, p.y, rect.width, rect.height) : p))
    }
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [pos])

  const toggleMinimized = () => {
    setMinimized(prev => {
      const next = !prev
      try { localStorage.setItem(minKey, next ? "1" : "0") } catch { /* ignore */ }
      return next
    })
  }

  return { panelRef, pos, minimized, dragging, startDrag, toggleMinimized }
}
