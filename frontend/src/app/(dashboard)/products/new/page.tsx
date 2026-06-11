'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import ProductForm from '@/components/products/ProductForm'
import { useBreadcrumb } from '@/context/BreadcrumbContext'

export default function NewProductPage() {
  const router = useRouter()
  useBreadcrumb('Add Product')
  return (
    <div className="space-y-6">
      <div>
        <Link href="/products" className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Products
        </Link>
        <h1 className="text-3xl font-serif font-medium">Add Product</h1>
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
