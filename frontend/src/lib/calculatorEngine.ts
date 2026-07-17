export type Operator = "+" | "-" | "×" | "÷"

export interface CalcState {
  display: string
  prevValue: number | null
  operator: Operator | null
  overwrite: boolean
  /** Human-readable running history, e.g. "123+456+789+" while composing,
   * finalized to "200+300=" once "=" is pressed — the top line of a
   * 2-line business-calculator display. */
  expression: string
}

export const MAX_DIGITS = 12

export const initialState: CalcState = {
  display: "0",
  prevValue: null,
  operator: null,
  overwrite: true,
  expression: "",
}

/** Display glyph per operator — the internal Operator type uses a plain
 * ASCII hyphen for "-" (matching what buttons pass in), but the expression
 * line should show the nicer minus sign the UI already renders on that key. */
const OP_SYMBOL: Record<Operator, string> = { "+": "+", "-": "−", "×": "×", "÷": "÷" }

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
  // A fresh digit right after a finished "=" (no pending operator/operand)
  // starts an unrelated new calculation — the old history line is stale.
  const freshStart = state.overwrite && state.operator === null && state.prevValue === null
  const base = freshStart ? { ...state, expression: "" } : state
  if (base.overwrite) {
    return { ...base, display: d === "." ? "0." : d, overwrite: false }
  }
  if (d === "." && base.display.includes(".")) return base
  if (base.display.replace("-", "").replace(".", "").length >= MAX_DIGITS) return base
  return {
    ...base,
    display: base.display === "0" && d !== "." ? d : base.display + d,
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
  // operand twice — and the history line's trailing symbol swaps with it
  // rather than gaining a duplicate.
  if (state.operator !== null && state.overwrite) {
    return { ...state, operator: op, expression: state.expression.slice(0, -1) + OP_SYMBOL[op] }
  }
  const result = applyPendingOperator(state)
  // No operator/operand pending means this is either a truly fresh start or
  // a continuation from a just-finished "=" — either way the history line
  // restarts from the current value rather than keeping the old one.
  const startingFresh = state.operator === null && state.prevValue === null
  const expression = startingFresh
    ? `${state.display}${OP_SYMBOL[op]}`
    : `${state.expression}${state.display}${OP_SYMBOL[op]}`
  return {
    ...state,
    display: formatResult(result),
    prevValue: result,
    operator: op,
    overwrite: true,
    expression,
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
    expression: `${state.expression}${state.display}=`,
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

export function sqrt(state: CalcState): CalcState {
  const result = Math.sqrt(parseFloat(state.display))
  return { ...state, display: formatResult(result), overwrite: true }
}

export function inputDoubleZero(state: CalcState): CalcState {
  return inputDigit(inputDigit(state, "0"), "0")
}

/**
 * With a pending operator, the entered number is always treated as a
 * percentage *of the pending operand* — same rule for every operator, so
 * "200 × 10%" shows 20 (10% of 200), not a bare fraction (0.1) that
 * discards the base and looks identical no matter what "200" was. With no
 * pending operator, percent is just value/100.
 */
export function percent(state: CalcState): CalcState {
  const current = parseFloat(state.display)
  const result = state.operator !== null && state.prevValue !== null
    ? (state.prevValue * current) / 100
    : current / 100
  return { ...state, display: formatResult(result), overwrite: true }
}
