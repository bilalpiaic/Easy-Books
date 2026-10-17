"use client"

export const LICENSE_PLAN_CHOICES = [
  { id: "starter", label: "Basic", hint: "Books, stock, POS, weighbridge" },
  { id: "pro", label: "Pro", hint: "Operations, payroll, AI, country packs" },
  { id: "enterprise", label: "Enterprise", hint: "All add-ons including industry verticals" },
] as const

export type LicensePlanId = (typeof LICENSE_PLAN_CHOICES)[number]["id"]

export function licensePlanLabel(id: string | null | undefined): string {
  if (!id) return ""
  const key = id.trim().toLowerCase()
  if (key === "basic") return "Basic"
  const found = LICENSE_PLAN_CHOICES.find((c) => c.id === key)
  return found?.label || id
}

export function LicensePlanPicker({
  value,
  onChange,
  disabled,
}: {
  value: string
  onChange: (id: LicensePlanId) => void
  disabled?: boolean
}) {
  return (
    <fieldset className="space-y-2" disabled={disabled}>
      <legend className="text-xs uppercase tracking-wide text-[var(--text-primary)]/50 mb-1">
        Client category
      </legend>
      <p className="text-xs text-[var(--text-primary)]/60">
        Select Basic, Pro, or Enterprise. It must match the token Easy-Books issued.
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        {LICENSE_PLAN_CHOICES.map((choice) => {
          const on = value === choice.id
          return (
            <label
              key={choice.id}
              className={`rounded-lg border px-3 py-2 text-left cursor-pointer ${
                on
                  ? "border-[#b8943f] bg-[#b8943f]/10"
                  : "border-[var(--border)] hover:border-[#b8943f]/50"
              }`}
            >
              <input
                type="radio"
                name="license-plan"
                className="sr-only"
                checked={on}
                required={!value}
                onChange={() => onChange(choice.id)}
              />
              <div className="text-sm font-medium text-[var(--text-primary)]">{choice.label}</div>
              <div className="text-[11px] text-[var(--text-primary)]/55">{choice.hint}</div>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}
