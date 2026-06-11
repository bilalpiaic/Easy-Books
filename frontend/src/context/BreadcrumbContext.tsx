'use client'

import { createContext, useContext, useEffect, useState } from 'react'

interface BreadcrumbCtx {
  leaf: string | null
  setLeaf: (v: string | null) => void
}

const Ctx = createContext<BreadcrumbCtx>({ leaf: null, setLeaf: () => {} })

export function BreadcrumbProvider({ children }: { children: React.ReactNode }) {
  const [leaf, setLeaf] = useState<string | null>(null)
  return <Ctx.Provider value={{ leaf, setLeaf }}>{children}</Ctx.Provider>
}

/**
 * Pages call useBreadcrumb('Some Label') to set the trailing breadcrumb
 * segment. Pass nothing to read the current leaf. The leaf is cleared on
 * unmount so it never bleeds into the next page.
 *
 * Call it UNCONDITIONALLY (React hook rules). For data that loads async,
 * pass a value that updates: useBreadcrumb(entity ? 'Edit ' + entity.number : 'Edit').
 */
export function useBreadcrumb(leaf?: string): string | null {
  const ctx = useContext(Ctx)
  useEffect(() => {
    if (leaf === undefined) return
    ctx.setLeaf(leaf)
    return () => ctx.setLeaf(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leaf])
  return ctx.leaf
}
