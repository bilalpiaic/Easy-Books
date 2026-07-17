export type Operator = "+" | "-" | "×" | "÷"

export interface CalcState {
  display: string
  prevValue: number | null
  operator: Operator | null
  overwrite: boolean
}

export const MAX_DIGITS = 12

export const initialState: CalcState = {
  display: "0",
  prevValue: null,
  operator: null,
  overwrite: true,
}

export function compute(a: number, b: number, op: Operator): number {
  switch (op) {
    case "+": return a + b
    case "-": return a - b
    case "×": return a * b
    case "÷": return b === 0 ? NaN : a / b
  }
}

/** Render a result within the 12-digit display, falling back to
 * exponential notation for values too large/small to fit. */
export function formatResult(n: number): string {
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

export function inputDigit(state: CalcState, d: string): CalcState {
  if (state.overwrite) {
    return { ...state, display: d === "." ? "0." : d, overwrite: false }
  }
  if (d === "." && state.display.includes(".")) return state
  if (state.display.replace("-", "").replace(".", "").length >= MAX_DIGITS) return state
  return {
    ...state,
    display: state.display === "0" && d !== "." ? d : state.display + d,
  }
}

function applyPendingOperator(state: CalcState): number {
  const current = parseFloat(state.display)
  if (state.operator && state.prevValue !== null) {
    return compute(state.prevValue, current, state.operator)
  }
  return current
}

export function inputOperator(state: CalcState, op: Operator): CalcState {
  // Pressing an operator again before typing a new operand (e.g. "5 + ×")
  // must only swap the pending operator, not recompute using the same
  // operand twice.
  if (state.operator !== null && state.overwrite) {
    return { ...state, operator: op }
  }
  const result = applyPendingOperator(state)
  return {
    ...state,
    display: formatResult(result),
    prevValue: result,
    operator: op,
    overwrite: true,
  }
}

export function pressEquals(state: CalcState): CalcState {
  if (state.operator === null || state.prevValue === null) return state
  const result = applyPendingOperator(state)
  return {
    ...state,
    display: formatResult(result),
    prevValue: null,
    operator: null,
    overwrite: true,
  }
}

export function clear(): CalcState {
  return initialState
}

export function backspace(state: CalcState): CalcState {
  if (state.overwrite) return state
  const stripped = state.display.length > 1 ? state.display.slice(0, -1) : "0"
  return { ...state, display: stripped === "-" ? "0" : stripped }
}

export function toggleSign(state: CalcState): CalcState {
  if (state.display === "0") return state
  return {
    ...state,
    display: state.display.startsWith("-") ? state.display.slice(1) : "-" + state.display,
  }
}

/**
 * `+`/`-` treat the entered number as a percentage *of the pending operand*
 * (e.g. 200 + 10% -> operand becomes 20, so "=" yields 220). `×`/`÷` treat
 * it as a plain fraction of the entered number (200 × 10% -> operand 0.1).
 * With no pending operator, percent is just value/100.
 */
export function percent(state: CalcState): CalcState {
  const current = parseFloat(state.display)
  let result: number
  if (state.operator !== null && state.prevValue !== null) {
    result = state.operator === "+" || state.operator === "-"
      ? (state.prevValue * current) / 100
      : current / 100
  } else {
    result = current / 100
  }
  return { ...state, display: formatResult(result), overwrite: true }
}
