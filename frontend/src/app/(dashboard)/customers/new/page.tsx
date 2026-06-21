'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import CustomerForm from '@/components/customers/CustomerForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

export default function NewCustomerPage() {
  const { t } = useTranslation()

  const router = useRouter()
  useBreadcrumb('Add Customer')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/customers" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Customers
        </Link>
        <h1 className="text-xl sm:text-3xl font-serif font-medium">Add Customer</h1>
        <p className="text-sm text-black/75 mt-1">Create a customer account</p>
      </div>
      <CustomerForm
        mode="create"
        onSaved={() => router.push('/customers')}
        onCancel={() => router.push('/customers')}
      />
    </div>
  )
}
