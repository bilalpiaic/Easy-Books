export interface LowStockItem {
  name: string
  on_hand: number
  reorder_level: number
}

export interface LowStockBandProps {
  items: LowStockItem[]
}

export default function LowStockBand({ items }: LowStockBandProps) {
  if (items.length === 0) return null
  return (
    <div className="bg-white rounded-xl p-3">
      <div className="text-[9px] font-bold uppercase tracking-[0.12em] text-amber-600 mb-2">
        ⚠ Low Stock Alerts
      </div>
      <div className="flex flex-col gap-1.5">
        {items.slice(0, 3).map((item, i) => {
          const out = item.on_hand <= 0
          return (
            <div
              key={i}
              className={`flex justify-between items-center rounded-lg px-2.5 py-1.5 ${out ? "bg-red-50" : "bg-amber-50"}`}
            >
              <span className="text-xs text-[#1a1814] truncate">{item.name}</span>
              <span className={`text-xs font-bold ml-2 shrink-0 ${out ? "text-red-600" : "text-amber-600"}`}>
                {out ? "Out of stock" : `${item.on_hand} left`}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
