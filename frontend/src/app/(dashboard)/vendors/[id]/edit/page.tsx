'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import VendorForm, { VendorFull } from '@/components/vendors/VendorForm'
import { apiFetch } from '@/lib/api'
import { useBreadcrumb } from '@/context/BreadcrumbContext'

export default function EditVendorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [vendor, setVendor] = useState<VendorFull | null>(null)
  const [failed, setFailed] = useState(false)
  useBreadcrumb(vendor ? `Edit ${vendor.name}` : 'Edit')

  useEffect(() => {
    apiFetch<VendorFull>(`/api/vendors/${id}`)
      .then(setVendor)
      .catch(() => setFailed(true))
  }, [id])

  useEffect(() => {
    if (failed) router.replace('/vendors')
  }, [failed, router])

  if (failed) return null
  if (!vendor) return <div className="p-8 text-sm text-black/50">Loading vendor…</div>

  return (
    <div className="space-y-6">
      <div>
        <Link href="/vendors" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Vendors
        </Link>
        <h1 className="text-3xl font-serif font-medium">Edit {vendor.name}</h1>
      </div>
      <VendorForm
        mode="edit"
        vendor={vendor}
        onSaved={() => router.push('/vendors')}
        onCancel={() => router.push('/vendors')}
      />
    </div>
  )
}
