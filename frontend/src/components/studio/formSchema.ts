'use client'

import { useEffect, useState } from 'react'
import { apiFetch } from '@/lib/api'

export type FormFieldConfig = {
  visible?: boolean
  required?: boolean
  readonly?: boolean
  order?: number
}

export type FormSchemaResponse = {
  entity: string
  role: string
  source_role: string
  schema: { version: number; fields: Record<string, FormFieldConfig> }
  locked: string[]
  field_access?: Record<string, 'edit' | 'view' | 'none'>
}

export function isFieldVisible(fields: Record<string, FormFieldConfig>, key: string): boolean {
  return fields[key]?.visible !== false
}

export function isFieldRequired(fields: Record<string, FormFieldConfig>, key: string): boolean {
  return fields[key]?.required === true
}

export function useFormSchema(entity: string) {
  const [fields, setFields] = useState<Record<string, FormFieldConfig>>({})
  const [fieldAccess, setFieldAccess] = useState<Record<string, 'edit' | 'view' | 'none'>>({})

  useEffect(() => {
    let cancelled = false
    apiFetch<FormSchemaResponse>(`/api/studio/forms/${entity}`)
      .then(res => {
        if (!cancelled) {
          setFields(res?.schema?.fields || {})
          setFieldAccess(res?.field_access || {})
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFields({})
          setFieldAccess({})
        }
      })
    return () => { cancelled = true }
  }, [entity])

  return {
    fields,
    fieldAccess,
    visible: (key: string) => isFieldVisible(fields, key),
    required: (key: string) => isFieldRequired(fields, key),
  }
}
