'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import InvoiceForm from '@/components/invoices/InvoiceForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'

export default function NewInvoicePage() {
  const router = useRouter()
  useBreadcrumb('New Invoice')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/invoices" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Invoices
        </Link>
        <h1 className="text-3xl font-serif font-medium">New Invoice</h1>
        <p className="text-sm text-black/75 mt-1">Create a sales invoice to a customer</p>
      </div>
      <InvoiceForm
        mode="create"
        onSaved={(id) => router.push(`/invoices/${id}`)}
        onCancel={() => router.push('/invoices')}
      />
    </div>
  )
}
