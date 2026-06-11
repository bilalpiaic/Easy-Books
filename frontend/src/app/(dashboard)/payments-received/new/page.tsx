'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import PaymentReceivedForm from '@/components/payments/PaymentReceivedForm'

export default function NewPaymentReceivedPage() {
  const router = useRouter()
  return (
    <div className="space-y-6">
      <div>
        <Link href="/payments-received" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Payments Received
        </Link>
        <h1 className="text-3xl font-serif font-medium">Record Payment</h1>
        <p className="text-sm text-black/75 mt-1">Record a customer payment and apply it to open invoices</p>
      </div>
      <PaymentReceivedForm
        onSaved={(id) => router.push(`/payments-received/${id}`)}
        onCancel={() => router.push('/payments-received')}
      />
    </div>
  )
}
