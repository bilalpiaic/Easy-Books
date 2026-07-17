import { describe, expect, it } from "vitest"
import {
  type CalcState,
  initialState,
  compute,
  formatResult,
  inputDigit,
  inputOperator,
  pressEquals,
  clear,
  backspace,
  toggleSign,
  percent,
  sqrt,
  inputDoubleZero,
} from "../calculatorEngine"

const digits = (state: CalcState, s: string) =>
  [...s].reduce((st, d) => inputDigit(st, d), state)

describe("compute", () => {
  it("does the four basic operations", () => {
    expect(compute(2, 3, "+")).toBe(5)
    expect(compute(2, 3, "-")).toBe(-1)
    expect(compute(2, 3, "×")).toBe(6)
    expect(compute(6, 3, "÷")).toBe(2)
  })
  it("division by zero yields NaN (rendered as Error)", () => {
    expect(compute(5, 0, "÷")).toBeNaN()
  })
})

describe("formatResult", () => {
  it("renders plain integers", () => {
    expect(formatResult(42)).toBe("42")
    expect(formatResult(-7)).toBe("-7")
  })
  it("renders Error for non-finite values", () => {
    expect(formatResult(NaN)).toBe("Error")
    expect(formatResult(Infinity)).toBe("Error")
  })
  it("falls back to exponential notation beyond 12 significant digits", () => {
    const huge = 123456789012345
    expect(formatResult(huge)).toBe(huge.toExponential(6))
  })
})

describe("inputDigit", () => {
  it("starts a fresh number when overwrite is set (initial state)", () => {
    const s = inputDigit(initialState, "5")
    expect(s.display).toBe("5")
    expect(s.overwrite).toBe(false)
  })
  it("appends subsequent digits", () => {
    const s = digits(initialState, "123")
    expect(s.display).toBe("123")
  })
  it("replaces a lone leading zero", () => {
    const s = digits(initialState, "05")
    expect(s.display).toBe("5")
  })
  it("only allows one decimal point", () => {
    const s = digits(initialState, "1.2.3")
    expect(s.display).toBe("1.23")
  })
  it("typing '.' first produces '0.'", () => {
    const s = inputDigit(initialState, ".")
    expect(s.display).toBe("0.")
  })
  it("caps entry at 12 significant digits", () => {
    const s = digits(initialState, "1234567890123")
    expect(s.display).toBe("123456789012")
  })
})

describe("inputOperator", () => {
  it("stages the current value as the pending operand", () => {
    const s = inputOperator(digits(initialState, "5"), "+")
    expect(s.display).toBe("5")
    expect(s.prevValue).toBe(5)
    expect(s.operator).toBe("+")
    expect(s.overwrite).toBe(true)
  })

  it("chains: 2 + 3 + 4 = 9 (each operator commits the pending one)", () => {
    let s = digits(initialState, "2")
    s = inputOperator(s, "+")
    s = digits(s, "3")
    s = inputOperator(s, "+")
    s = digits(s, "4")
    s = pressEquals(s)
    expect(s.display).toBe("9")
  })

  it("pressing an operator twice in a row swaps the operator instead of recomputing (5 + × 3 = 15, not 25)", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")   // prevValue = 5, operator = +
    s = inputOperator(s, "×")   // operator change only, no digit typed yet
    expect(s.prevValue).toBe(5)
    expect(s.operator).toBe("×")
    s = digits(s, "3")
    s = pressEquals(s)
    expect(s.display).toBe("15")
  })
})

describe("pressEquals", () => {
  it("computes the pending operation", () => {
    let s = digits(initialState, "7")
    s = inputOperator(s, "-")
    s = digits(s, "2")
    s = pressEquals(s)
    expect(s.display).toBe("5")
    expect(s.operator).toBeNull()
    expect(s.prevValue).toBeNull()
  })
  it("is a no-op with no pending operator", () => {
    const s = digits(initialState, "9")
    expect(pressEquals(s)).toEqual(s)
  })
  it("repeats the current operand when pressed with no second entry (5 + = -> 10)", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = pressEquals(s)
    expect(s.display).toBe("10")
  })
  it("shows Error on divide by zero", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "÷")
    s = digits(s, "0")
    s = pressEquals(s)
    expect(s.display).toBe("Error")
  })
})

describe("clear", () => {
  it("resets to the initial state", () => {
    expect(clear()).toEqual(initialState)
  })
})

describe("backspace", () => {
  it("removes the last character", () => {
    const s = backspace(digits(initialState, "123"))
    expect(s.display).toBe("12")
  })
  it("is a no-op right after an operator (overwrite pending)", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    expect(backspace(s)).toEqual(s)
  })
  it("bottoms out at 0, never at a lone minus sign", () => {
    let s = digits(initialState, "5")
    s = toggleSign(s)
    expect(s.display).toBe("-5")
    s = backspace(s)
    expect(s.display).toBe("0")
  })
})

describe("toggleSign", () => {
  it("flips positive to negative and back", () => {
    let s = digits(initialState, "5")
    s = toggleSign(s)
    expect(s.display).toBe("-5")
    s = toggleSign(s)
    expect(s.display).toBe("5")
  })
  it("does nothing to zero", () => {
    expect(toggleSign(initialState)).toEqual(initialState)
  })
})

describe("percent", () => {
  it("standalone: divides by 100", () => {
    const s = percent(digits(initialState, "50"))
    expect(s.display).toBe("0.5")
  })

  it("200 + 10% -> 220 (percentage of the pending operand for +)", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "+")
    s = digits(s, "10")
    s = percent(s)
    s = pressEquals(s)
    expect(s.display).toBe("220")
  })

  it("200 - 10% -> 180 (percentage of the pending operand for -)", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "-")
    s = digits(s, "10")
    s = percent(s)
    s = pressEquals(s)
    expect(s.display).toBe("180")
  })

  it("200 × 10% -> 20 (plain fraction for ×)", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "×")
    s = digits(s, "10")
    s = percent(s)
    s = pressEquals(s)
    expect(s.display).toBe("20")
  })

  it("200 ÷ 10% -> 2000 (plain fraction for ÷: 200 / 0.1)", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "÷")
    s = digits(s, "10")
    s = percent(s)
    s = pressEquals(s)
    expect(s.display).toBe("2000")
  })

  it("percent pressed with no second entry yet reuses the pending operand (5 + % -> 0.25, then = -> 5.25)", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")   // overwrite=true, display still shows "5"
    s = percent(s)
    expect(s.display).toBe("0.25")
    s = pressEquals(s)
    expect(s.display).toBe("5.25")
  })

  it("percent compounds when pressed twice in a row", () => {
    let s = percent(digits(initialState, "50"))
    expect(s.display).toBe("0.5")
    s = percent(s)
    expect(s.display).toBe("0.005")
  })

  it("percent of a decimal operand", () => {
    const s = percent(digits(initialState, "12.5"))
    expect(s.display).toBe("0.125")
  })

  it("negative pending operand: -200 + 10% -> -20, then = -> -220", () => {
    let s = digits(initialState, "200")
    s = toggleSign(s)          // -200
    s = inputOperator(s, "+")
    s = digits(s, "10")
    s = percent(s)
    expect(s.display).toBe("-20")
    s = pressEquals(s)
    expect(s.display).toBe("-220")
  })

  it("does not disturb prevValue/operator (stays composable, doesn't auto-finalize)", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "+")
    s = digits(s, "10")
    s = percent(s)
    expect(s.operator).toBe("+")
    expect(s.prevValue).toBe(200)
    expect(s.overwrite).toBe(true)
  })
})

describe("sqrt", () => {
  it("computes a perfect square", () => {
    const s = sqrt(digits(initialState, "16"))
    expect(s.display).toBe("4")
  })
  it("computes an irrational root within the 12-digit display", () => {
    const s = sqrt(digits(initialState, "2"))
    expect(s.display).toBe(formatResult(Math.sqrt(2)))
  })
  it("sqrt of 0 is 0", () => {
    const s = sqrt(initialState)
    expect(s.display).toBe("0")
  })
  it("sqrt of a negative number is an Error", () => {
    let s = digits(initialState, "4")
    s = toggleSign(s)
    s = sqrt(s)
    expect(s.display).toBe("Error")
  })
  it("composes with a pending operator: 16 √ + 4 = -> 8", () => {
    let s = digits(initialState, "16")
    s = sqrt(s)
    s = inputOperator(s, "+")
    s = digits(s, "4")
    s = pressEquals(s)
    expect(s.display).toBe("8")
  })
  it("starts a fresh entry afterward (overwrite set)", () => {
    const s = sqrt(digits(initialState, "16"))
    expect(s.overwrite).toBe(true)
  })
})

describe("expression history line", () => {
  it("starts empty", () => {
    expect(initialState.expression).toBe("")
  })

  it("builds a chained expression: 123+456+789+ with running subtotals (matches a 2-line business calculator)", () => {
    let s = digits(initialState, "123")
    s = inputOperator(s, "+")
    expect(s.expression).toBe("123+")
    expect(s.display).toBe("123")

    s = digits(s, "456")
    s = inputOperator(s, "+")
    expect(s.expression).toBe("123+456+")
    expect(s.display).toBe("579")

    s = digits(s, "789")
    s = inputOperator(s, "+")
    expect(s.expression).toBe("123+456+789+")
    expect(s.display).toBe("1368")
  })

  it("finalizes with '=' and the result: 200+300=500", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "+")
    s = digits(s, "300")
    s = pressEquals(s)
    expect(s.expression).toBe("200+300=")
    expect(s.display).toBe("500")
  })

  it("shows the nicer minus glyph, not the internal ASCII operator key", () => {
    let s = digits(initialState, "9")
    s = inputOperator(s, "-")
    s = digits(s, "4")
    s = pressEquals(s)
    expect(s.expression).toBe("9−4=")
  })

  it("swapping an operator before typing the next digit replaces the trailing symbol, not duplicates it", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = inputOperator(s, "×")
    expect(s.expression).toBe("5×")
    s = digits(s, "3")
    s = pressEquals(s)
    expect(s.expression).toBe("5×3=")
    expect(s.display).toBe("15")
  })

  it("continuing from a finished result via an operator restarts the line from that result", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = digits(s, "3")
    s = pressEquals(s)
    expect(s.expression).toBe("5+3=")
    s = inputOperator(s, "+")
    expect(s.expression).toBe("8+")
    s = digits(s, "2")
    s = pressEquals(s)
    expect(s.expression).toBe("8+2=")
    expect(s.display).toBe("10")
  })

  it("typing a fresh digit after a finished result clears the line instead of leaving it stale", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = digits(s, "3")
    s = pressEquals(s)
    expect(s.expression).toBe("5+3=")
    s = inputDigit(s, "9")
    expect(s.expression).toBe("")
    expect(s.display).toBe("9")
  })

  it("clear() resets the line", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = clear()
    expect(s.expression).toBe("")
  })

  it("repeat-operand equals (5 + =) still finalizes the line", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = pressEquals(s)
    expect(s.expression).toBe("5+5=")
    expect(s.display).toBe("10")
  })

  it("percent doesn't disturb the pending trailing operator, and equals reflects the percent-adjusted operand", () => {
    let s = digits(initialState, "200")
    s = inputOperator(s, "+")
    s = digits(s, "10")
    s = percent(s)
    expect(s.expression).toBe("200+")
    s = pressEquals(s)
    expect(s.expression).toBe("200+20=")
    expect(s.display).toBe("220")
  })
})

describe("inputDoubleZero", () => {
  it("pressed first (fresh state) yields a plain 0", () => {
    const s = inputDoubleZero(initialState)
    expect(s.display).toBe("0")
  })
  it("appends '00' mid-entry", () => {
    const s = inputDoubleZero(digits(initialState, "5"))
    expect(s.display).toBe("500")
  })
  it("right after an operator (fresh operand) yields a plain 0, same as a single 0 press", () => {
    let s = digits(initialState, "5")
    s = inputOperator(s, "+")
    s = inputDoubleZero(s)
    expect(s.display).toBe("0")
  })
  it("respects the 12-digit cap, appending only what fits", () => {
    const eleven9s = digits(initialState, "9".repeat(11))
    const s = inputDoubleZero(eleven9s)
    expect(s.display).toBe("9".repeat(11) + "0")
  })
  it("does nothing after a decimal point beyond making it '0.00'", () => {
    let s = digits(initialState, "1.")
    s = inputDoubleZero(s)
    expect(s.display).toBe("1.00")
  })
})
