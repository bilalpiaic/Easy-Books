import { ShieldOff } from "lucide-react"

export function NoAccessBanner({ resource }: { resource: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <ShieldOff className="w-12 h-12 text-[var(--text-primary)]/20 mb-4" />
      <h2 className="text-xl font-bold text-[var(--text-primary)]">Access Restricted</h2>
      <p className="text-sm text-[var(--text-primary)]/60 mt-2 max-w-sm">
        You don&apos;t have permission to view {resource}. Contact your administrator.
      </p>
    </div>
  )
}
