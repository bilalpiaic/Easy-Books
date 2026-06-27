'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import BillForm, { BillFull } from '@/components/bills/BillForm'
import { apiFetch } from '@/lib/api'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

export default function EditBillPage({ params }: { params: Promise<{ id: string }> }) {
  const { t } = useTranslation()

  const { id } = use(params)
  const router = useRouter()
  const [bill, setBill] = useState<BillFull | null>(null)
  const [failed, setFailed] = useState(false)
  useBreadcrumb(bill ? `Edit ${bill.number}` : 'Edit')

  useEffect(() => {
    apiFetch<BillFull>(`/api/bills/${id}`)
      .then(setBill)
      .catch(() => setFailed(true))
  }, [id])

  useEffect(() => {
    if (failed) router.replace('/bills')
  }, [failed, router])

  if (failed) return null
  if (!bill) return <div className="p-8 text-sm text-[var(--text-muted)]">Loading bill…</div>

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/bills/${bill.id}`} className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-2">
          <ArrowLeft className="w-4 h-4" /> Bill {bill.number}
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold">Edit Bill {bill.number}</h1>
      </div>
      <BillForm
        mode="edit"
        bill={bill}
        onSaved={(savedId) => router.push(`/bills/${savedId}`)}
        onCancel={() => router.push('/bills')}
      />
    </div>
  )
}
