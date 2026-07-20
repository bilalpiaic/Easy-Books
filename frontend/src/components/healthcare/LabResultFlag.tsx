"use client"

import {
  ArrowDownCircle,
  ArrowUpCircle,
  CheckCircle2,
  CircleAlert,
  CircleMinus,
  CirclePlus,
  Minus,
} from "lucide-react"

export type LabFlagCode =
  | "high"
  | "low"
  | "positive"
  | "negative"
  | "normal"
  | "abnormal"
  | "pending"

export type LabFlag = {
  code: LabFlagCode
  label: string
  symbol: string
}

const FLAG_META: Record<
  LabFlagCode,
  { Icon: typeof CheckCircle2; className: string; printSymbol: string }
> = {
  high: {
    Icon: ArrowUpCircle,
    className: "bg-rose-100 text-rose-800 border-rose-200",
    printSymbol: "H ↑",
  },
  low: {
    Icon: ArrowDownCircle,
    className: "bg-amber-100 text-amber-900 border-amber-200",
    printSymbol: "L ↓",
  },
  positive: {
    Icon: CirclePlus,
    className: "bg-rose-100 text-rose-800 border-rose-200",
    printSymbol: "+",
  },
  negative: {
    Icon: CircleMinus,
    className: "bg-emerald-100 text-emerald-800 border-emerald-200",
    printSymbol: "−",
  },
  normal: {
    Icon: CheckCircle2,
    className: "bg-emerald-50 text-emerald-700 border-emerald-200",
    printSymbol: "N",
  },
  abnormal: {
    Icon: CircleAlert,
    className: "bg-rose-100 text-rose-800 border-rose-200",
    printSymbol: "!",
  },
  pending: {
    Icon: Minus,
    className: "bg-neutral-100 text-neutral-500 border-neutral-200",
    printSymbol: "…",
  },
}

const POSITIVE_RE =
  /\b(positive|reactive|detected|present|abnormal|elevated|high|growth)\b/i
const NEGATIVE_RE =
  /\b(negative|non[-\s]?reactive|not\s+detected|absent|nil|clear|normal\s+study|wnl|within\s+normal|desirable|sinus\s+rhythm|no\s+growth)\b/i

/** Mirror of backend `_parse_reference_interval` for live draft preview. */
export function parseReferenceInterval(ref?: string | null): { low?: number; high?: number } {
  if (!ref) return {}
  const text = String(ref).trim().replace(/[–—−]/g, "-")
  if (!text || /^(varies|negative|normal|n\/a|na)$/i.test(text)) return {}
  let m = text.match(/^<\s*([-+]?\d*\.?\d+)$/)
  if (m) return { high: Number(m[1]) }
  m = text.match(/^>\s*([-+]?\d*\.?\d+)$/)
  if (m) return { low: Number(m[1]) }
  m = text.match(/^([-+]?\d*\.?\d+)\s*-\s*([-+]?\d*\.?\d+)$/)
  if (m) {
    let lo = Number(m[1])
    let hi = Number(m[2])
    if (lo > hi) [lo, hi] = [hi, lo]
    return { low: lo, high: hi }
  }
  return {}
}

function parseLabNumeric(value?: string | null): number | null {
  if (value == null) return null
  const text = String(value).trim().replace(/,/g, "")
  if (!text) return null
  const m = text.match(/[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?/)
  if (!m) return null
  if (/[A-Za-z]{3,}/.test(text) && !/^[-+]?\d*\.?\d+$/.test(text)) return null
  const n = Number(m[0])
  return Number.isFinite(n) ? n : null
}

/** Client-side twin of backend `_classify_lab_flag` for draft preview. */
export function classifyLabFlag(
  resultValue?: string | null,
  opts?: {
    referenceInterval?: { low?: number; high?: number }
    referenceRange?: string | null
    isAbnormal?: boolean
  },
): LabFlag {
  if (resultValue == null || !String(resultValue).trim()) {
    return { code: "pending", label: "Pending", symbol: "…" }
  }
  const text = String(resultValue).trim()
  const interval =
    opts?.referenceInterval ?? parseReferenceInterval(opts?.referenceRange)
  const numeric = parseLabNumeric(text)

  if (numeric != null && (interval.low != null || interval.high != null)) {
    if (interval.high != null && numeric > interval.high) {
      return { code: "high", label: "Excess (High)", symbol: "H" }
    }
    if (interval.low != null && numeric < interval.low) {
      return { code: "low", label: "Reduced (Low)", symbol: "L" }
    }
    return { code: "normal", label: "Within range", symbol: "N" }
  }

  if (NEGATIVE_RE.test(text)) {
    return { code: "negative", label: "Negative", symbol: "−" }
  }
  if (POSITIVE_RE.test(text)) {
    return { code: "positive", label: "Positive", symbol: "+" }
  }
  if (opts?.isAbnormal) {
    return { code: "abnormal", label: "Abnormal", symbol: "!" }
  }
  if (numeric != null) {
    return { code: "normal", label: "Within range", symbol: "N" }
  }
  return { code: "normal", label: "Normal", symbol: "N" }
}

export function isAbnormalFlag(flag: LabFlag | null | undefined): boolean {
  return !!flag && ["high", "low", "positive", "abnormal"].includes(flag.code)
}

type Props = {
  flag?: LabFlag | null
  /** Compact: icon + symbol only (for dense tables). */
  compact?: boolean
}

/** Range-aware result flag with icons (H/L / Pos/Neg / Normal). */
export default function LabResultFlag({ flag, compact }: Props) {
  const f = flag ?? { code: "pending" as const, label: "Pending", symbol: "…" }
  const meta = FLAG_META[f.code] ?? FLAG_META.pending
  const { Icon, className, printSymbol } = meta

  return (
    <span
      title={f.label}
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-xs font-semibold whitespace-nowrap ${className}`}
    >
      <Icon className="w-3.5 h-3.5 shrink-0 print:hidden" aria-hidden />
      <span className="hidden print:inline font-bold">{printSymbol}</span>
      {!compact && <span>{f.label}</span>}
      {compact && <span className="print:hidden">{f.symbol}</span>}
    </span>
  )
}
