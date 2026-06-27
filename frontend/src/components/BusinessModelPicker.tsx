"use client"

import { Briefcase, Building2, Package, Factory, Radio, Check } from "lucide-react"

export type BusinessModel = "simple" | "services" | "trader" | "manufacturing" | "telecom_franchise"

interface ModelOption {
  id: BusinessModel
  label: string
  icon: React.ElementType
  tagline: string
  bestFor: string
  includes: string[]
}

const OPTIONS: ModelOption[] = [
  {
    id: "simple",
    label: "Simple",
    icon: Briefcase,
    tagline: "Just invoices, bills, and bank entries",
    bestFor: "Freelancers, single-owner businesses, anyone who doesn't carry stock.",
    includes: ["Cash & bank", "Invoices to customers", "Bills from vendors", "Manual journal entries"],
  },
  {
    id: "services",
    label: "Services",
    icon: Building2,
    tagline: "Sell hours, projects, or recurring services",
    bestFor: "Consultancies, agencies, software firms — anyone billing for time or expertise.",
    includes: ["Everything in Simple", "Service catalogue & line items", "Deferred revenue tracking", "Subcontractor costs"],
  },
  {
    id: "trader",
    label: "Trader",
    icon: Package,
    tagline: "Buy goods, resell goods",
    bestFor: "Distributors, retailers, wholesalers — you hold finished-goods stock.",
    includes: ["Everything in Services", "Perpetual inventory (Weighted Avg)", "COGS at sale", "Freight In, storage costs"],
  },
  {
    id: "manufacturing",
    label: "Manufacturing",
    icon: Factory,
    tagline: "Make or value-add products",
    bestFor: "Factories, workshops, processors — including value-addition on customer-supplied goods.",
    includes: ["Everything in Trader", "Raw material + WIP + finished goods stores", "Bills of Material", "Customer-goods custody (memo accounts)", "Production orders"],
  },
  {
    id: "telecom_franchise",
    label: "Telecom Franchise",
    icon: Radio,
    tagline: "Operator franchise — Tracker, MSR load, RSO channel, FCA targets",
    bestFor: "Jazz / Telenor / Zong / Ufone franchisees — Tracker-based load distribution, SIM/IMSI stock, RSO field teams, mobile money agency, postpaid billing.",
    includes: ["Tracker deposit & load float (3% uplift)", "MSR → RSO → Retail load chain", "RSO daily cash + stock settlement", "Mobile money float (JazzCash/EasyPaisa)", "FCA target tracking + commission", "Postpaid billing & remittance", "Franchise fee amortisation"],
  },
]

interface BusinessModelPickerProps {
  value: BusinessModel
  onChange: (next: BusinessModel) => void
}

export function BusinessModelPicker({ value, onChange }: BusinessModelPickerProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {OPTIONS.map(opt => {
        const Icon = opt.icon
        const selected = value === opt.id
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => onChange(opt.id)}
            className={[
              "text-left rounded-2xl border-2 p-4 transition-all relative",
              selected
                ? "border-[var(--primary)] bg-[var(--bg-page)] shadow-sm"
                : "border-[var(--border)] bg-white hover:border-[var(--primary)]/40 hover:bg-[#faf8f4]",
            ].join(" ")}
            aria-pressed={selected}
          >
            {selected && (
              <span className="absolute top-3 right-3 w-5 h-5 rounded-full bg-[var(--primary)] text-white flex items-center justify-center">
                <Check className="w-3 h-3" />
              </span>
            )}
            <div className="flex items-center gap-2.5 mb-1.5">
              <div className={[
                "w-9 h-9 rounded-xl flex items-center justify-center",
                selected ? "bg-[var(--primary)] text-white" : "bg-[var(--bg-page)] text-[var(--text-primary)]/70",
              ].join(" ")}>
                <Icon className="w-4.5 h-4.5" />
              </div>
              <p className="text-sm font-bold text-[var(--text-primary)]">{opt.label}</p>
            </div>
            <p className="text-xs text-[var(--text-primary)]/70 leading-snug">{opt.tagline}</p>
            <p className="mt-2 text-[10.5px] text-[var(--text-primary)]/50 leading-relaxed">
              <span className="font-semibold text-[var(--text-primary)]/70">Best for: </span>
              {opt.bestFor}
            </p>
            <ul className="mt-2 space-y-1">
              {opt.includes.map(item => (
                <li key={item} className="flex items-start gap-1.5 text-[10.5px] text-[var(--text-primary)]/65">
                  <span className="text-[var(--primary)] mt-0.5">·</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </button>
        )
      })}
    </div>
  )
}
