'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import CustomerForm, { CustomerFull } from '@/components/customers/CustomerForm'
import { apiFetch } from '@/lib/api'

export default function EditCustomerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [customer, setCustomer] = useState<CustomerFull | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    apiFetch<CustomerFull>(`/api/customers/${id}`)
      .then(setCustomer)
      .catch(() => setFailed(true))
  }, [id])

  useEffect(() => {
    if (failed) router.replace('/customers')
  }, [failed, router])

  if (failed) return null
  if (!customer) return <div className="p-8 text-sm text-black/50">Loading customer…</div>

  return (
    <div className="space-y-6">
      <div>
        <Link href="/customers" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Customers
        </Link>
        <h1 className="text-3xl font-serif font-medium">Edit {customer.name}</h1>
      </div>
      <CustomerForm
        mode="edit"
        customer={customer}
        onSaved={() => router.push('/customers')}
        onCancel={() => router.push('/customers')}
      />
    </div>
  )
}
