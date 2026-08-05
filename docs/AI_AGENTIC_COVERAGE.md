# AI Chat — Agentic Coverage Review

Living map of dedicated specialist agents vs installable modules / IFRS features.
Regenerate counts by importing `services.ai_agents.AGENTS` and `services.ai_tools.TOOL_REGISTRY`.

**Last updated:** 2026-08-05 (textile_proc + spinning finish + localization + IFRS agents)

## Pipeline (unchanged)

Triage → Specialist (`run_tool_loop`) → Reviewer → Drafting  
See `backend/routers/ai_chat.py`. Tool schemas/labels/dispatch derive from `TOOL_REGISTRY`.

## Roster summary

| Tier | Agents |
|------|--------|
| Base | receivables, payables, financial_reports, sales, banking, deferred_rev, staff_commissions, fixed_assets, **leases**, **consol**, general, data_entry |
| Module | inventory, payroll, healthcare, telecom, purchasing, store_ops, manufacturing, weaving, spinning, **textile_proc**, pra_status, **zatca_status**, **peppol_status**, **uae_einvoice**, **india_gst** |

## Coverage by module / feature

| Area | Status | Agent / notes |
|------|--------|----------------|
| Base AR/AP/FS/banking | Strong | Multiple specialists |
| inventory / hrm / healthcare / telecom | Strong | Full report wraps |
| purchase_store | Good | purchasing + store_ops |
| production | Good | + scrap_by_reason |
| weaving | Good | Dashboard/daily/contract/KPI |
| spinning | **Complete** | + waste, cost/kg, dispatch |
| textile_processing | **Complete** | textile_proc + 5 tools |
| pra | Good | pra_status |
| sa_zatca / eu_peppol / uae_vat / in_gst | **Added** | Dedicated compliance agents |
| IFRS 16 leases | **Added** | leases (settings-gated at runtime) |
| IFRS 10 consol + IC | **Added** | consol |
| Fixed assets rollforward | **Added** | on fixed_assets |
| Ops home bag | **Added** | get_operations_summary on general |

## Still open (P2+)

- WHT / CIT worksheet / dimensional P&L tools
- Bank reconciliation list/detail tools
- Purchase chain document list tools (PD/VQ/CS)
- Spinning/weaving calculators as read tools
- Deferred revenue remaining-balance summary

## Invariants

- Every `AgentDef.tools` name ∈ `TOOL_REGISTRY` (import-time assert)
- No agent key is a substring of another (triage fallback)
- Module agents only reference base tools or their own module’s tools
- Every `required_module != None` tool appears in `test_module_tools_smoke`
