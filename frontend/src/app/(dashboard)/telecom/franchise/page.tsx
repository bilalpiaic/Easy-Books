"use client"

import { ScrollText } from "lucide-react"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, money, useTelecomList,
} from "@/components/telecom/primitives"

interface Operator { id: number; name: string; operator_code: string }
interface Agreement {
  id: number; agreement_number: string; start_date: string; end_date: string | null
  franchise_fee_paid: string; royalty_rate_pct: string; min_monthly_target: string; amortisation_months: number
}

export default function FranchisePage() {
  const operators = useTelecomList<Operator>("/api/telecom/operators")
  const agreements = useTelecomList<Agreement>("/api/telecom/franchise/agreements")

  const opOptions: SelectOption[] = operators.items.map(o => ({ value: String(o.id), label: `${o.name} (${o.operator_code})` }))
  const agOptions: SelectOption[] = agreements.items.map(a => ({ value: String(a.id), label: a.agreement_number }))

  const agFields: FieldDef[] = [
    { kind: "select", name: "operator_id", label: "Operator", required: true, options: opOptions },
    { kind: "text", name: "agreement_number", label: "Agreement number", required: true },
    { kind: "date", name: "start_date", label: "Start date", required: true },
    { kind: "date", name: "end_date", label: "End date" },
    { kind: "number", name: "franchise_fee_paid", label: "Franchise fee", default: "0" },
    { kind: "number", name: "royalty_rate_pct", label: "Royalty rate %", default: "0" },
    { kind: "number", name: "min_monthly_target", label: "Min monthly target", default: "0" },
    { kind: "number", name: "penalty_rate_pct", label: "Penalty rate %", default: "0" },
    { kind: "number", name: "amortisation_months", label: "Amortisation months", default: "60", step: "1" },
  ]
  const capFields: FieldDef[] = [
    { kind: "select", name: "agreement_id", label: "Agreement", required: true, options: agOptions },
    { kind: "number", name: "fee", label: "Fee to capitalise", required: true, help: "Dr 1300 Franchise Intangible / Cr Bank" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const amortFields: FieldDef[] = [
    { kind: "select", name: "agreement_id", label: "Agreement", required: true, options: agOptions },
    { kind: "date", name: "date", label: "Period date", help: "Posts one month: fee ÷ amortisation months" },
  ]
  const royaltyAccrueFields: FieldDef[] = [
    { kind: "select", name: "agreement_id", label: "Agreement", required: true, options: agOptions },
    { kind: "number", name: "gross_revenue", label: "Gross revenue base", required: true, help: "Royalty = base × royalty rate %" },
    { kind: "date", name: "date", label: "Date" },
  ]
  const royaltyPayFields: FieldDef[] = [
    { kind: "number", name: "amount", label: "Amount to pay", required: true, help: "Dr 2120 Royalty Payable / Cr Bank" },
    { kind: "date", name: "date", label: "Date" },
  ]

  const agCols: Column<Agreement>[] = [
    { header: "Agreement #", cell: a => a.agreement_number, mono: true },
    { header: "Start", cell: a => a.start_date, mono: true },
    { header: "Fee", cell: a => money(a.franchise_fee_paid) },
    { header: "Royalty %", cell: a => a.royalty_rate_pct },
    { header: "Amort. months", cell: a => String(a.amortisation_months) },
  ]

  return (
    <div className="space-y-6">
      <PageHeader icon={ScrollText} title="Franchise Admin" subtitle="Franchise fee amortisation and operator royalty." />

      <HelpCallout title="Fee is an asset, royalty is an expense" tone="tip">
        The up-front <b>franchise fee</b> is capitalised as an intangible (Acct 1300) and amortised monthly over
        the agreement term (Acct 5030). <b>Royalty</b> is a recurring expense accrued on gross revenue
        (Acct 5040 / payable 2120) and cleared when you pay the operator.
      </HelpCallout>

      <ErrorBanner error={operators.error ?? agreements.error} />

      <Tabs tabs={[
        { id: "amortise", label: "Amortise", content: (
          <Section title="Post monthly amortisation">
            <ActionForm endpoint="/api/telecom/franchise/amortise" fields={amortFields} submitLabel="Post amortisation" />
          </Section>
        )},
        { id: "capitalise", label: "Capitalise fee", content: (
          <Section title="Capitalise the franchise fee">
            <ActionForm endpoint="/api/telecom/franchise/capitalise-fee" fields={capFields} submitLabel="Capitalise" />
          </Section>
        )},
        { id: "royalty-accrue", label: "Accrue royalty", content: (
          <Section title="Accrue royalty on revenue">
            <ActionForm endpoint="/api/telecom/franchise/royalty/accrue" fields={royaltyAccrueFields} submitLabel="Accrue royalty" />
          </Section>
        )},
        { id: "royalty-pay", label: "Pay royalty", content: (
          <Section title="Pay royalty to operator">
            <ActionForm endpoint="/api/telecom/franchise/royalty/pay" fields={royaltyPayFields} submitLabel="Pay royalty" />
          </Section>
        )},
        { id: "agreements", label: "Agreements", content: (
          <div className="space-y-4">
            <Section title="Agreements"><DataTable columns={agCols} rows={agreements.items} empty="No agreements yet." /></Section>
            <Section title="Add a franchise agreement">
              <ActionForm endpoint="/api/telecom/franchise/agreements" fields={agFields} submitLabel="Add agreement" successText={() => "Agreement added."} onSuccess={agreements.refetch} />
            </Section>
          </div>
        )},
      ]} />
    </div>
  )
}
