"use client"

interface SkeletonRowProps {
  cols: number
  rows?: number
}

function SkeletonCell() {
  return (
    <td className="px-6 py-4">
      <div className="h-4 bg-[#f0ece4] rounded animate-pulse" />
    </td>
  )
}

export default function SkeletonRow({ cols, rows = 5 }: SkeletonRowProps) {
  return (
    <>
      {Array.from({ length: rows }).map((_, i) => (
        <tr key={i} className="border-b border-[#1a1814]/5">
          {Array.from({ length: cols }).map((__, j) => (
            <SkeletonCell key={j} />
          ))}
        </tr>
      ))}
    </>
  )
}
