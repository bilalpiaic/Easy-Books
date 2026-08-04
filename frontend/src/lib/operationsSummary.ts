/** Shape returned by GET /api/dashboard/operations-summary */

export interface WeightTriple {
  kg: number
  lbs: number
  bags: number
}

export interface OperationsSummary {
  modules: string[]
  business_model?: string | null
  production?: {
    pipeline: Record<string, number>
    totals: { wip_cost: string; finished_goods_cost: string; custodial_qty: string }
  }
  spinning?: {
    kpis: {
      open_lots: number
      bale_received: WeightTriple
      cone_output: WeightTriple
      dispatched: WeightTriple
      dispatch_value: number
      overall_yield_pct: number
      lot_count: number
      status_summary: Record<string, number>
    }
    wip_by_stage: Record<string, number>
  }
  weaving?: {
    kpis: {
      yarn_received: WeightTriple
      yarn_used: WeightTriple
      yarn_balance: WeightTriple
      grey_meters: number
      dispatch_meters: number
      weaving_revenue: number
      avg_efficiency_pct: number
      contract_count: number
      status_summary: Record<string, number>
    }
  }
  textile_processing?: {
    kpis: {
      lots_total: number
      lots_in_process: number
      lots_ready: number
      received_mtr: number
      ready_mtr: number
      rejection_pending_mtr: number
      visible_wastage_mtr: number
      invisible_wastage_mtr: number
    }
  }
  healthcare?: {
    date: string
    tokens_today: number
    visits_today: number
    currently_admitted: number
    total_beds: number
    occupied_beds: number
    bed_occupancy_pct: number
    pending_lab_results: number
    dialysis_sessions_today?: number
    dialysis_capacity?: number
  }
  telecom?: {
    as_of: string
    tracker: {
      deposit_balance: string
      load_float: string
      rso_load_receivable: string
      retail_load_receivable: string
    }
    commissions: { receivable: string }
    rso: { agent_count: number; stock_receivable: string }
    sim: {
      inventory_cost: string
      total_received: number
      total_activated: number
      available: number
    }
    fca: {
      month: string
      actual: number
      target: string | null
      achievement_pct: string | null
    }
  }
  purchase_store?: {
    open_demands: number
    open_pos: number
    open_gate_inwards: number
    low_stock_items: number
  }
  hrm?: {
    active_employees: number
    last_payroll_net: number
    pending_runs: number
    avg_attendance_pct: number
  }
}
