'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import VendorForm from '@/components/vendors/VendorForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

export default function NewVendorPage() {
  const { t } = useTranslation()

  const router = useRouter()
  useBreadcrumb('Add Vendor')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/vendors" className="inline-flex items-center gap-1 text-sm text-[var(--text-muted)] hover:text-[var(--text-primary)] mb-2">
          <ArrowLeft className="w-4 h-4" /> Vendors
        </Link>
        <h1 className="text-xl sm:text-3xl font-bold">Add Vendor</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">Create a supplier account</p>
      </div>
      <VendorForm
        mode="create"
        onSaved={() => router.push('/vendors')}
        onCancel={() => router.push('/vendors')}
      />
    </div>
  )
}
