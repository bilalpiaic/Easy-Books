"use client"

import { useState } from "react"
import { createPortal } from "react-dom"
import { X, Calculator as CalculatorIcon, Minus, Maximize2, Delete } from "lucide-react"
import { useDraggablePanel } from "@/hooks/useDraggablePanel"
import {
  type CalcState,
  type Operator,
  initialState,
  MAX_DIGITS,
  inputDigit as engineInputDigit,
  inputOperator as engineInputOperator,
  pressEquals,
  clear as engineClear,
  backspace as engineBackspace,
  toggleSign as engineToggleSign,
  percent as enginePercent,
} from "@/lib/calculatorEngine"

interface CalculatorProps {
  open: boolean
  onClose: () => void
}

export default function Calculator({ open, onClose }: CalculatorProps) {
  const [state, setState] = useState<CalcState>(initialState)
  const { display } = state

  const { panelRef, pos, minimized, dragging, startDrag, toggleMinimized } =
    useDraggablePanel("eb.calculator")

  const inputDigit = (d: string) => setState(s => engineInputDigit(s, d))
  const inputOperator = (op: Operator) => setState(s => engineInputOperator(s, op))
  const equals = () => setState(pressEquals)
  const clear = () => setState(engineClear())
  const backspace = () => setState(engineBackspace)
  const toggleSign = () => setState(engineToggleSign)
  const percent = () => setState(enginePercent)

  if (!open) return null

  // Casio HL-122-style skin: silver chassis, black LCD bezel over a
  // green-tinted display, navy keys with a maroon clear key and teal
  // secondary-function keys. Each key gets a small drop "ledge" shadow that
  // disappears on press for a tactile, embossed feel.
  const keyBase =
    "rounded-2xl text-lg font-semibold py-3 transition-all duration-75 active:translate-y-[3px] active:shadow-none"
  const numKey = `${keyBase} bg-[#31334a] hover:bg-[#3b3d57] text-white shadow-[0_3px_0_0_#1b1c29]`
  const opKey = `${keyBase} bg-[#31334a] hover:bg-[#3b3d57] text-[#c9cdf0] shadow-[0_3px_0_0_#1b1c29]`
  const clearKey = `${keyBase} bg-[#7c3548] hover:bg-[#8f4058] text-white shadow-[0_3px_0_0_#4a1e2b]`
  const fnKey = `${keyBase} bg-[#3f7d74] hover:bg-[#4a9086] text-white shadow-[0_3px_0_0_#274f48]`

  const panel = (
    <div
      ref={panelRef}
      className={`fixed z-[900] w-[calc(100vw-2rem)] max-w-[300px] flex flex-col bg-gradient-to-b from-[#eceef0] via-[#dcdee1] to-[#c7c9cd] rounded-[28px] shadow-2xl border border-[#9a9da3] overflow-hidden ${
        pos ? "" : "bottom-36 right-4 md:bottom-24 md:right-6"
      } ${dragging ? "select-none" : ""}`}
      style={pos ? { left: pos.x, top: pos.y } : undefined}
    >
      {/* Header — also the drag handle */}
      <div
        onPointerDown={startDrag}
        className={`flex items-center justify-between px-4 pt-3 pb-2 shrink-0 ${dragging ? "cursor-grabbing" : "cursor-grab"}`}
      >
        <div className="flex items-center gap-1.5">
          <CalculatorIcon className="w-3.5 h-3.5 text-[#4a4c52]" />
          <div className="leading-none">
            <div className="font-bold text-[13px] tracking-wide text-[#2b2c30]">Calculator</div>
            <div className="text-[8px] tracking-[0.18em] text-[#6b6d73] uppercase">Electronic Calculator</div>
          </div>
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={toggleMinimized}
            className="p-1 rounded-lg hover:bg-black/10 text-[#4a4c52] transition-colors"
            aria-label={minimized ? "Restore" : "Minimize"}
            title={minimized ? "Restore" : "Minimize"}
          >
            {minimized ? <Maximize2 className="w-3.5 h-3.5" /> : <Minus className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-black/10 text-[#4a4c52] transition-colors"
            aria-label="Close"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Body — collapsed (not unmounted) while minimized so the current
          calculation isn't lost. */}
      <div className={minimized ? "hidden" : "px-3 pb-3 space-y-3"}>
        {/* LCD bezel */}
        <div className="bg-[#26282c] rounded-2xl p-2.5 shadow-inner">
          <div className="bg-gradient-to-b from-[#dfe8d0] to-[#ccd9bc] rounded-lg px-3 py-3 shadow-inner">
            <div className="flex items-center justify-between text-[9px] font-semibold tracking-widest text-[#5b6b4f] uppercase h-3">
              <span>{state.operator ?? ""}</span>
              <span>{MAX_DIGITS} digit</span>
            </div>
            <div
              className="text-right text-4xl font-mono font-semibold tracking-wider tabular-nums text-[#1d2b1a] truncate [text-shadow:0_0_1px_rgba(29,43,26,0.25)]"
              title={display}
            >
              {display}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <button className={clearKey} onClick={clear}>C</button>
          <button className={fnKey} onClick={backspace} aria-label="Backspace">
            <Delete className="w-4 h-4 mx-auto" />
          </button>
          <button className={fnKey} onClick={percent}>%</button>
          <button className={opKey} onClick={() => inputOperator("÷")}>÷</button>

          <button className={numKey} onClick={() => inputDigit("7")}>7</button>
          <button className={numKey} onClick={() => inputDigit("8")}>8</button>
          <button className={numKey} onClick={() => inputDigit("9")}>9</button>
          <button className={opKey} onClick={() => inputOperator("×")}>×</button>

          <button className={numKey} onClick={() => inputDigit("4")}>4</button>
          <button className={numKey} onClick={() => inputDigit("5")}>5</button>
          <button className={numKey} onClick={() => inputDigit("6")}>6</button>
          <button className={opKey} onClick={() => inputOperator("-")}>−</button>

          <button className={numKey} onClick={() => inputDigit("1")}>1</button>
          <button className={numKey} onClick={() => inputDigit("2")}>2</button>
          <button className={numKey} onClick={() => inputDigit("3")}>3</button>
          <button className={opKey} onClick={() => inputOperator("+")}>+</button>

          <button className={fnKey} onClick={toggleSign}>±</button>
          <button className={numKey} onClick={() => inputDigit("0")}>0</button>
          <button className={numKey} onClick={() => inputDigit(".")}>.</button>
          <button className={numKey} onClick={equals}>=</button>
        </div>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
