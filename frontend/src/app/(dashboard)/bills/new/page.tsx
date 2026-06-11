'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import BillForm from '@/components/bills/BillForm'

export default function NewBillPage() {
  const router = useRouter()
  return (
    <div className="space-y-6">
      <div>
        <Link href="/bills" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Bills
        </Link>
        <h1 className="text-3xl font-serif font-medium">New Bill</h1>
        <p className="text-sm text-black/75 mt-1">Record a vendor bill / purchase liability</p>
      </div>
      <BillForm
        mode="create"
        onSaved={(id) => router.push(`/bills/${id}`)}
        onCancel={() => router.push('/bills')}
      />
    </div>
  )
}
