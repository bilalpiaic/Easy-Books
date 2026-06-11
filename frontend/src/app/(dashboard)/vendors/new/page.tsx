'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import VendorForm from '@/components/vendors/VendorForm'

export default function NewVendorPage() {
  const router = useRouter()
  return (
    <div className="space-y-6">
      <div>
        <Link href="/vendors" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Vendors
        </Link>
        <h1 className="text-3xl font-serif font-medium">Add Vendor</h1>
        <p className="text-sm text-black/75 mt-1">Create a supplier account</p>
      </div>
      <VendorForm
        mode="create"
        onSaved={() => router.push('/vendors')}
        onCancel={() => router.push('/vendors')}
      />
    </div>
  )
}
