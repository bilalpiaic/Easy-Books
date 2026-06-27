'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import PaymentReceivedForm from '@/components/payments/PaymentReceivedForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

export default function NewPaymentReceivedPage() {
  const { t } = useTranslation()

  const router = useRouter()
  useBreadcrumb('Record Payment')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/payments-received" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-2">
          <ArrowLeft className="w-4 h-4" /> Payments Received
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold">Record Payment</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Record a customer payment and apply it to open invoices</p>
      </div>
      <PaymentReceivedForm
        onSaved={(id) => router.push(`/payments-received/${id}`)}
        onCancel={() => router.push('/payments-received')}
      />
    </div>
  )
}
