'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import InvoiceForm from '@/components/invoices/InvoiceForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

function NewInvoiceContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const customerId = searchParams.get('customer_id')
  useBreadcrumb('New Invoice')
  const { t } = useTranslation()
  return (
    <div className="space-y-6">
      <div>
        <Link href="/invoices" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-muted)] mb-2">
          <ArrowLeft className="w-4 h-4" /> Invoices
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold">New Invoice</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Create a sales invoice to a customer</p>
      </div>
      <InvoiceForm
        mode="create"
        initialCustomerId={customerId ? parseInt(customerId) : undefined}
        onSaved={(id) => router.push(`/invoices/${id}`)}
        onCancel={() => router.push('/invoices')}
      />
    </div>
  )
}

export default function NewInvoicePage() {
  return (
    <Suspense>
      <NewInvoiceContent />
    </Suspense>
  )
}
