"use client"

import React, { useState } from "react"
import {
  DndContext, closestCenter, PointerSensor, KeyboardSensor,
  useSensor, useSensors, type DragEndEvent,
} from "@dnd-kit/core"
import {
  SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy,
  arrayMove, useSortable,
} from "@dnd-kit/sortable"
import { CSS } from "@dnd-kit/utilities"
import { GripVertical, Eye, EyeOff, Check, X, RotateCcw, Plus } from "lucide-react"
import type { WidgetContext } from "@/lib/dashboardWidgets"
import type { UseDashboardLayout } from "@/hooks/useDashboardLayout"

function SortableRow({ id, title, conditional, visible, onToggle, children }: {
  id: string; title: string; conditional?: boolean; visible: boolean
  onToggle: () => void; children: React.ReactNode
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }
  return (
    <div ref={setNodeRef} style={style} className="border border-dashed border-[#b8943f]/40 rounded-xl bg-white/60">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[#ede9e2]">
        <button {...attributes} {...listeners} className="cursor-grab text-[#1a1814]/40 hover:text-[#1a1814]/70" aria-label={`Drag ${title}`}>
          <GripVertical className="w-4 h-4" />
        </button>
        <span className="text-sm font-semibold text-[#1a1814]/80">{title}</span>
        {conditional && <span className="text-[10px] text-[#1a1814]/40">(shows only when relevant)</span>}
        <button onClick={onToggle} className="ml-auto text-[#1a1814]/50 hover:text-[#b8943f]" aria-label={visible ? `Hide ${title}` : `Show ${title}`}>
          {visible ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
        </button>
      </div>
      <div className="p-3 pointer-events-none select-none opacity-90">{children}</div>
    </div>
  )
}

export default function CustomizeBar({ layout, onDone, ctx }: {
  layout: UseDashboardLayout
  onDone: () => void
  ctx: WidgetContext
}) {
  const { widgets, setOrder, toggle, reset, reload, save } = layout
  const [saving, setSaving] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const visibleIds = widgets.filter(w => w.visible).map(w => w.def.id)
  const hidden = widgets.filter(w => !w.visible)

  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const oldIndex = visibleIds.indexOf(active.id as string)
    const newIndex = visibleIds.indexOf(over.id as string)
    const reorderedVisible = arrayMove(visibleIds, oldIndex, newIndex)
    setOrder([...reorderedVisible, ...hidden.map(w => w.def.id)])
  }

  const handleDone = async () => {
    setSaving(true); setErr(null)
    try { await save(); onDone() }
    catch { setErr("Couldn't save layout. Please try again.") }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 bg-[#faf6ec] border border-[#b8943f]/30 rounded-xl px-3 py-2 sticky top-2 z-10">
        <span className="text-xs font-bold uppercase tracking-[0.12em] text-[#1a1814]/55">Customizing dashboard</span>
        <span className="text-[11px] text-[#1a1814]/45">Drag to reorder · toggle the eye to show/hide</span>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={reset} className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
          <button onClick={() => { reload(); onDone() }} className="inline-flex items-center gap-1 text-xs text-[#1a1814]/60 hover:text-[#1a1814] px-2 py-1">
            <X className="w-3.5 h-3.5" /> Cancel
          </button>
          <button onClick={handleDone} disabled={saving} className="inline-flex items-center gap-1 text-xs font-semibold text-white bg-[#b8943f] hover:bg-[#a07f33] rounded-lg px-3 py-1.5 disabled:opacity-60">
            <Check className="w-3.5 h-3.5" /> {saving ? "Saving…" : "Done"}
          </button>
        </div>
      </div>

      {err && <div className="bg-red-50 border border-red-200 rounded-xl px-4 py-2 text-sm text-red-700">{err}</div>}

      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={visibleIds} strategy={verticalListSortingStrategy}>
          <div className="space-y-3">
            {widgets.filter(w => w.visible).map(w => (
              <SortableRow
                key={w.def.id} id={w.def.id} title={w.def.title}
                conditional={w.def.conditional} visible={true}
                onToggle={() => toggle(w.def.id)}
              >
                {w.def.render(ctx)}
              </SortableRow>
            ))}
          </div>
        </SortableContext>
      </DndContext>

      {hidden.length > 0 && (
        <div className="bg-white border border-[#ede9e2] rounded-xl p-3">
          <p className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#1a1814]/45 mb-2">Hidden widgets</p>
          <div className="flex flex-wrap gap-2">
            {hidden.map(w => (
              <button key={w.def.id} onClick={() => toggle(w.def.id)}
                className="inline-flex items-center gap-1 text-xs border border-[#ede9e2] rounded-lg px-2.5 py-1.5 hover:border-[#b8943f]/40 text-[#1a1814]/70">
                <Plus className="w-3.5 h-3.5 text-[#b8943f]" /> {w.def.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
