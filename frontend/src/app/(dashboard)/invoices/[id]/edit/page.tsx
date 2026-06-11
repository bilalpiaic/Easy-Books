'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import InvoiceForm, { InvoiceFull } from '@/components/invoices/InvoiceForm'
import { apiFetch } from '@/lib/api'
import { useBreadcrumb } from '@/context/BreadcrumbContext'

export default function EditInvoicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [invoice, setInvoice] = useState<InvoiceFull | null>(null)
  const [failed, setFailed] = useState(false)
  useBreadcrumb(invoice ? `Edit ${invoice.number}` : 'Edit')

  useEffect(() => {
    apiFetch<InvoiceFull>(`/api/invoices/${id}`)
      .then(setInvoice)
      .catch(() => setFailed(true))
  }, [id])

  useEffect(() => {
    if (failed) router.replace('/invoices')
  }, [failed, router])

  if (failed) return null
  if (!invoice) return <div className="p-8 text-sm text-black/50">Loading invoice…</div>

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/invoices/${invoice.id}`} className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Invoice {invoice.number}
        </Link>
        <h1 className="text-3xl font-serif font-medium">Edit Invoice {invoice.number}</h1>
      </div>
      <InvoiceForm
        mode="edit"
        invoice={invoice}
        onSaved={(savedId) => router.push(`/invoices/${savedId}`)}
        onCancel={() => router.push('/invoices')}
      />
    </div>
  )
}
