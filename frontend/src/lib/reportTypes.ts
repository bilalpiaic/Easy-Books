export type FieldType = "text" | "number" | "money" | "date" | "enum" | "bool"

export interface FieldMeta {
  key: string; label: string; type: FieldType
  enum_values: string[] | null; aggregatable: boolean; groupable: boolean
}
export interface SourceMeta {
  key: string; label: string; date_field: string | null
  default_columns: string[]; fields: FieldMeta[]
}
export interface FilterClause { field: string; op: string; value: unknown }
export interface SortClause { field: string; dir: "asc" | "desc" }
export interface Aggregate { field: string; fn: "sum" | "avg" | "count" | "min" | "max" }
export interface DateRange { preset?: string; start?: string; end?: string }
export interface ReportConfig {
  columns: string[]; filters: FilterClause[]; sort: SortClause[]
  group_by: string[]; aggregates: Aggregate[]; date_range?: DateRange | null
}
export interface ColumnMeta { key: string; label: string; type: string; aggregatable: boolean }
export interface RunResult {
  columns: ColumnMeta[]; rows: Record<string, string>[]; group_by: string[]
  footers: Record<string, string> | null; page: number; page_size: number; total_count: number
}
export interface SavedReport {
  id: number; name: string; source_key: string; visibility: string
  owner_id: number; config: ReportConfig
}
export const OPS_BY_TYPE: Record<FieldType, string[]> = {
  text: ["equals", "contains", "starts_with", "in"],
  number: ["equals", "gt", "gte", "lt", "lte", "between"],
  money: ["equals", "gt", "gte", "lt", "lte", "between"],
  date: ["equals", "before", "after", "between"],
  enum: ["equals", "in"],
  bool: ["equals"],
}
export const emptyConfig = (cols: string[] = []): ReportConfig =>
  ({ columns: cols, filters: [], sort: [], group_by: [], aggregates: [], date_range: null })
