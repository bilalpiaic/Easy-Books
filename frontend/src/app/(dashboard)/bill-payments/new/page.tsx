'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import BillPaymentForm from '@/components/payments/BillPaymentForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

export default function NewBillPaymentPage() {
  const { t } = useTranslation()

  const router = useRouter()
  useBreadcrumb('Pay Bill')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/bill-payments" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-2">
          <ArrowLeft className="w-4 h-4" /> Bill Payments
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold">Pay Bill</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Record a vendor payment and apply it to open bills</p>
      </div>
      <BillPaymentForm
        onSaved={(id) => router.push(`/bill-payments/${id}`)}
        onCancel={() => router.push('/bill-payments')}
      />
    </div>
  )
}
