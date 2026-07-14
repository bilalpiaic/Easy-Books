"use client"

import { useState } from "react"
import { createPortal } from "react-dom"
import { X, Calculator as CalculatorIcon, Minus, Maximize2, Delete } from "lucide-react"
import { useDraggablePanel } from "@/hooks/useDraggablePanel"

interface CalculatorProps {
  open: boolean
  onClose: () => void
}

const MAX_DIGITS = 12

type Operator = "+" | "-" | "×" | "÷"

function compute(a: number, b: number, op: Operator): number {
  switch (op) {
    case "+": return a + b
    case "-": return a - b
    case "×": return a * b
    case "÷": return b === 0 ? NaN : a / b
  }
}

/** Render a result within the 12-digit display, falling back to
 * exponential notation for values too large/small to fit. */
function formatResult(n: number): string {
  if (!isFinite(n)) return "Error"
  if (Number.isInteger(n) && Math.abs(n).toString().length <= MAX_DIGITS) {
    return n.toString()
  }
  let s = parseFloat(n.toPrecision(MAX_DIGITS)).toString()
  if (s.replace("-", "").replace(".", "").length > MAX_DIGITS) {
    s = n.toExponential(6)
  }
  return s
}

export default function Calculator({ open, onClose }: CalculatorProps) {
  const [display, setDisplay] = useState("0")
  const [prevValue, setPrevValue] = useState<number | null>(null)
  const [operator, setOperator] = useState<Operator | null>(null)
  const [overwrite, setOverwrite] = useState(true)

  const { panelRef, pos, minimized, dragging, startDrag, toggleMinimized } =
    useDraggablePanel("eb.calculator")

  const inputDigit = (d: string) => {
    if (overwrite) {
      setDisplay(d === "." ? "0." : d)
      setOverwrite(false)
      return
    }
    if (d === "." && display.includes(".")) return
    if (display.replace("-", "").replace(".", "").length >= MAX_DIGITS) return
    setDisplay(display === "0" && d !== "." ? d : display + d)
  }

  const applyPendingOperator = (): number => {
    const current = parseFloat(display)
    if (operator && prevValue !== null) {
      return compute(prevValue, current, operator)
    }
    return current
  }

  const inputOperator = (op: Operator) => {
    const result = applyPendingOperator()
    setDisplay(formatResult(result))
    setPrevValue(result)
    setOperator(op)
    setOverwrite(true)
  }

  const equals = () => {
    if (operator === null || prevValue === null) return
    const result = applyPendingOperator()
    setDisplay(formatResult(result))
    setPrevValue(null)
    setOperator(null)
    setOverwrite(true)
  }

  const clear = () => {
    setDisplay("0")
    setPrevValue(null)
    setOperator(null)
    setOverwrite(true)
  }

  const backspace = () => {
    if (overwrite) return
    setDisplay(prev => (prev.length > 1 ? prev.slice(0, -1) : "0"))
  }

  const toggleSign = () => {
    if (display === "0") return
    setDisplay(prev => (prev.startsWith("-") ? prev.slice(1) : "-" + prev))
  }

  const percent = () => {
    setDisplay(formatResult(parseFloat(display) / 100))
    setOverwrite(true)
  }

  if (!open) return null

  const btnBase = "rounded-xl text-base font-medium py-3 transition-colors active:scale-95"
  const numBtn = `${btnBase} bg-[var(--bg-page)] hover:bg-[var(--text-primary)]/10 text-[var(--text-primary)]`
  const opBtn = `${btnBase} bg-[var(--primary)]/10 hover:bg-[var(--primary)]/20 text-[var(--primary)]`
  const fnBtn = `${btnBase} bg-[var(--text-primary)]/5 hover:bg-[var(--text-primary)]/10 text-[var(--text-primary)]/70`

  const panel = (
    <div
      ref={panelRef}
      className={`fixed z-[900] w-[calc(100vw-2rem)] max-w-xs flex flex-col bg-white rounded-3xl shadow-2xl border border-[var(--text-primary)]/10 overflow-hidden ${
        pos ? "" : "bottom-36 right-4 md:bottom-24 md:right-6"
      } ${dragging ? "select-none" : ""}`}
      style={pos ? { left: pos.x, top: pos.y } : undefined}
    >
      {/* Header — also the drag handle */}
      <div
        onPointerDown={startDrag}
        className={`flex items-center justify-between px-4 py-3 bg-[var(--primary)] text-white shrink-0 ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
      >
        <div className="flex items-center gap-2">
          <CalculatorIcon className="w-4 h-4" />
          <span className="font-semibold text-sm">Calculator</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={toggleMinimized}
            className="p-1 rounded-lg hover:bg-white/20 transition-colors"
            aria-label={minimized ? "Restore" : "Minimize"}
            title={minimized ? "Restore" : "Minimize"}
          >
            {minimized ? <Maximize2 className="w-4 h-4" /> : <Minus className="w-4 h-4" />}
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-white/20 transition-colors"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Body — collapsed (not unmounted) while minimized so the current
          calculation isn't lost. */}
      <div className={minimized ? "hidden" : "p-3 space-y-3"}>
        <div className="bg-[var(--bg-page)] rounded-2xl px-4 py-4 text-right">
          <div className="text-3xl font-mono font-semibold text-[var(--text-primary)] truncate" title={display}>
            {display}
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <button className={fnBtn} onClick={clear}>C</button>
          <button className={fnBtn} onClick={backspace} aria-label="Backspace">
            <Delete className="w-4 h-4 mx-auto" />
          </button>
          <button className={fnBtn} onClick={percent}>%</button>
          <button className={opBtn} onClick={() => inputOperator("÷")}>÷</button>

          <button className={numBtn} onClick={() => inputDigit("7")}>7</button>
          <button className={numBtn} onClick={() => inputDigit("8")}>8</button>
          <button className={numBtn} onClick={() => inputDigit("9")}>9</button>
          <button className={opBtn} onClick={() => inputOperator("×")}>×</button>

          <button className={numBtn} onClick={() => inputDigit("4")}>4</button>
          <button className={numBtn} onClick={() => inputDigit("5")}>5</button>
          <button className={numBtn} onClick={() => inputDigit("6")}>6</button>
          <button className={opBtn} onClick={() => inputOperator("-")}>−</button>

          <button className={numBtn} onClick={() => inputDigit("1")}>1</button>
          <button className={numBtn} onClick={() => inputDigit("2")}>2</button>
          <button className={numBtn} onClick={() => inputDigit("3")}>3</button>
          <button className={opBtn} onClick={() => inputOperator("+")}>+</button>

          <button className={fnBtn} onClick={toggleSign}>±</button>
          <button className={numBtn} onClick={() => inputDigit("0")}>0</button>
          <button className={numBtn} onClick={() => inputDigit(".")}>.</button>
          <button
            className={`${btnBase} bg-[var(--primary)] hover:opacity-90 text-white`}
            onClick={equals}
          >
            =
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
