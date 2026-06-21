"use client"

import { Tablet, Download, Printer } from "lucide-react"
import { HelpCallout } from "@/components/guidance/HelpCallout"
import { ActionForm, FieldDef, SelectOption } from "@/components/telecom/ActionForm"
import {
  PageHeader, Section, Tabs, DataTable, Column, ErrorBanner, useTelecomList,
} from "@/components/telecom/primitives"
import { downloadCSV } from "@/lib/utils"
import PrintHeader from "@/components/PrintHeader"
import { useTranslation } from "react-i18next"

interface Product { id: number; code: string; name: string; product_type: string }
interface DeviceImei { id: number; imei_number: string; serial_number: string | null; status: string; product_id: number }

export default function DevicesPage() {
  const { t } = useTranslation()

  const products = useTelecomList<Product>("/api/products?limit=500")
  const imeis = useTelecomList<DeviceImei>("/api/telecom/imei")

  const deviceProducts = products.items.filter(p => p.product_type !== "service")
  const productOptions: SelectOption[] = deviceProducts.map(p => ({ value: String(p.id), label: `${p.code} — ${p.name}` }))
  const productById = new Map(products.items.map(p => [p.id, p]))

  const imeiFields: FieldDef[] = [
    { kind: "select", name: "product_id", label: "Device model", required: true, options: productOptions },
    { kind: "text", name: "imei_number", label: "IMEI", required: true },
    { kind: "text", name: "serial_number", label: "Serial number" },
    { kind: "select", name: "status", label: "Status", default: "in_stock",
      options: [
        { value: "in_stock", label: "In stock" },
        { value: "sold", label: "Sold" },
        { value: "returned", label: "Returned" },
        { value: "defective", label: "Defective" },
      ] },
  ]

  const imeiCols: Column<DeviceImei>[] = [
    { header: "IMEI", cell: d => d.imei_number, mono: true },
    { header: "Model", cell: d => productById.get(d.product_id)?.name ?? `#${d.product_id}` },
    { header: "Serial", cell: d => d.serial_number ?? "—" },
    { header: "Status", cell: d => (
      <span className={d.status === "in_stock" ? "text-emerald-700" : d.status === "sold" ? "text-[#1a1814]/60" : "text-amber-700"}>
        {d.status}
      </span>
    )},
  ]

  return (
    <div className="space-y-6">
      <PrintHeader title="Devices (IMEI)" orientation="landscape" />
      <div className="flex items-center justify-between">
        <PageHeader icon={Tablet} title="Devices (IMEI)" subtitle="Track handset & router stock by IMEI for warranty and resale." />
        <button
          onClick={() => window.print()}
          className="flex items-center gap-2 px-4 py-2 border border-[#ede9e2] rounded-lg text-sm font-bold hover:bg-[#f6f3ee] transition-colors print:hidden"
        >
          <Printer className="w-4 h-4" />{t('common.print', 'Print')}</button>
      </div>

      <HelpCallout title="IMEI is serial-level tracking" tone="tip">
        Devices are valued in inventory (Acct 1202) like any product, but each unit is also tracked by its unique
        <b> IMEI</b> so you can trace warranty claims and sales. Register IMEIs as stock arrives.
      </HelpCallout>

      <ErrorBanner error={products.error ?? imeis.error} />

      <Tabs tabs={[
        { id: "register", label: "Register IMEI", content: (
          <Section title="Register a device IMEI">
            <ActionForm endpoint="/api/telecom/imei" fields={imeiFields} submitLabel="Register" successText={() => "IMEI registered."} onSuccess={imeis.refetch} />
          </Section>
        )},
        { id: "inventory", label: "Inventory", content: (
          <Section title="Device inventory" action={
            <button onClick={() => downloadCSV('devices.csv', imeis.items.map(d => ({ IMEI: d.imei_number, Model: productById.get(d.product_id)?.name ?? `#${d.product_id}`, Serial: d.serial_number ?? '', Status: d.status })))} disabled={imeis.items.length === 0} className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-[#ede9e2] rounded-lg text-xs font-bold hover:bg-[#f6f3ee] disabled:opacity-40"><Download className="w-3.5 h-3.5" /> CSV</button>
          }>
            <DataTable columns={imeiCols} rows={imeis.items} empty="No devices registered yet." />
          </Section>
        )},
      ]} />
    </div>
  )
}
