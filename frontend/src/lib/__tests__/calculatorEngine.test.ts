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
})
