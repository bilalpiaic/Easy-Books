"use client"
import { useState } from "react"
import { ChevronRight, ChevronDown } from "lucide-react"

export interface TreeNode {
  id: number | null
  code: string
  name: string
  type: string
  is_group: boolean
  level: number
  children: TreeNode[]
  [field: string]: unknown   // numeric fields (debit/credit/balance/amount)
}

export function AccountTreeRows({
  nodes, columns, renderLeafLabel,
}: {
  nodes: TreeNode[]
  columns: { key: string; align?: "right" | "left" }[]
  renderLeafLabel?: (node: TreeNode) => React.ReactNode
}) {
  return (
    <>
      {nodes.map(n => (
        <TreeRow key={`${n.code}-${n.id ?? "syn"}`} node={n} columns={columns} renderLeafLabel={renderLeafLabel} />
      ))}
    </>
  )
}

function TreeRow({ node, columns, renderLeafLabel }: {
  node: TreeNode
  columns: { key: string; align?: "right" | "left" }[]
  renderLeafLabel?: (node: TreeNode) => React.ReactNode
}) {
  const [open, setOpen] = useState(true)
  const hasChildren = node.children && node.children.length > 0
  const isGroup = node.is_group || hasChildren
  return (
    <>
      <tr className={isGroup ? "font-semibold bg-[var(--bg-page)]/40" : ""}>
        <td className="py-2 pr-3">
          <span
            style={{ paddingLeft: `calc(${node.level} * var(--tree-indent, 20px))` }}
            className="inline-flex items-center gap-1 min-w-0 max-w-full [--tree-indent:12px] sm:[--tree-indent:20px]"
          >
            {hasChildren ? (
              <button onClick={() => setOpen(o => !o)} className="text-[var(--text-primary)]/50 hover:text-[var(--primary)]">
                {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </button>
            ) : <span className="inline-block w-[14px]" />}
            <span className="text-[var(--text-primary)]/50 text-xs tabular-nums">{node.code}</span>
            {!isGroup && renderLeafLabel ? renderLeafLabel(node) : <span>{node.name}</span>}
          </span>
        </td>
        {columns.map(col => (
          <td key={col.key} className={`py-2 px-3 tabular-nums ${col.align === "right" ? "text-right" : ""}`}>
            {fmtNum(node[col.key])}
          </td>
        ))}
      </tr>
      {hasChildren && open && (
        <AccountTreeRows nodes={node.children} columns={columns} renderLeafLabel={renderLeafLabel} />
      )}
    </>
  )
}

function fmtNum(v: unknown): string {
  const n = Number(v ?? 0)
  return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
