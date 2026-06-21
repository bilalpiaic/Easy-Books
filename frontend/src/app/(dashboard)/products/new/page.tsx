'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import ProductForm from '@/components/products/ProductForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'
import { useTranslation } from "react-i18next"

export default function NewProductPage() {
  const { t } = useTranslation()

  const router = useRouter()
  useBreadcrumb('Add Product')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/products" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Products
        </Link>
        <h1 className="text-xl sm:text-3xl font-serif font-medium">Add Product</h1>
        <p className="text-sm text-black/75 mt-1">Add an item to the product catalog</p>
      </div>
      <ProductForm
        mode="create"
        onSaved={() => router.push('/products')}
        onCancel={() => router.push('/products')}
      />
    </div>
  )
}
