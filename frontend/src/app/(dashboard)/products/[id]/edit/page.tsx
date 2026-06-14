'use client'

import { use, useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import ProductForm, { ProductFull } from '@/components/products/ProductForm'
import { apiFetch } from '@/lib/api'
import { useBreadcrumb } from '@/context/BreadcrumbContext'

export default function EditProductPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params)
  const router = useRouter()
  const [product, setProduct] = useState<ProductFull | null>(null)
  const [failed, setFailed] = useState(false)
  useBreadcrumb(product ? `Edit ${product.name}` : 'Edit')

  useEffect(() => {
    apiFetch<ProductFull>(`/api/products/${id}`)
      .then(setProduct)
      .catch(() => setFailed(true))
  }, [id])

  useEffect(() => {
    if (failed) router.replace('/products')
  }, [failed, router])

  if (failed) return null
  if (!product) return <div className="p-8 text-sm text-black/50">Loading product…</div>

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/products/${id}`} className="inline-flex items-center gap-1 text-sm text-black/60 hover:text-black/80 mb-2">
          <ArrowLeft className="w-4 h-4" /> Product
        </Link>
        <h1 className="text-3xl font-serif font-medium">Edit {product.name}</h1>
      </div>
      <ProductForm
        mode="edit"
        product={product}
        onSaved={() => router.push(`/products/${id}`)}
        onCancel={() => router.push(`/products/${id}`)}
      />
    </div>
  )
}
