'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import BillForm from '@/components/bills/BillForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

function NewBillContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const vendorId = searchParams.get('vendor_id')
  useBreadcrumb('New Bill')
  const { t } = useTranslation()
  return (
    <div className="space-y-6">
      <div>
        <Link href="/bills" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-muted)] mb-2">
          <ArrowLeft className="w-4 h-4" /> Bills
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold">New Bill</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Record a vendor bill / purchase liability</p>
      </div>
      <BillForm
        mode="create"
        initialVendorId={vendorId ? parseInt(vendorId) : undefined}
        onSaved={(id) => router.push(`/bills/${id}`)}
        onCancel={() => router.push('/bills')}
      />
    </div>
  )
}

export default function NewBillPage() {
  return (
    <Suspense>
      <NewBillContent />
    </Suspense>
  )
}
