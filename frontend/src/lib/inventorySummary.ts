// Shape of an item from GET /api/reports/inventory-performance (subset we use).
// Money/Decimal fields may arrive as number or numeric-string → coerce with Number().
export interface InventoryPerfItem {
  id: number
  name: string
  code: string
  on_hand: number | string
  stock_value: number | string
  low_stock: boolean
  units_sold: number | string
}

export interface InventoryTotals { totalValue: number; itemCount: number; lowStock: number }

export function summarizeInventory(items: InventoryPerfItem[]): InventoryTotals {
  return {
    totalValue: items.reduce((sum, i) => sum + Number(i.stock_value), 0),
    itemCount: items.length,
    lowStock: items.filter(i => i.low_stock).length,
  }
}

export function topByUnitsSold(items: InventoryPerfItem[], n: number): InventoryPerfItem[] {
  return [...items].sort((a, b) => Number(b.units_sold) - Number(a.units_sold)).slice(0, n)
}
