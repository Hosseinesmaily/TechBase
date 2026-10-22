/** Types for the agentic chat (see backend/apps/ai/orchestrator.py). */

export interface ProductCardData {
  sku: string
  title: string
  price: string
  currency: string
  in_stock: boolean
  stock: number
  entity_slug: string
  entity_type: string
  updated_at: string
}

export interface Understanding {
  use_case: string
  resolution: string
  fps_target: number
  budget_max: number
  language: string
  missing_info: string[]
  clarifying_question: string
  used_heuristics: boolean
}

export interface AgentCitation {
  index: number
  page_slug: string
  page_title: string
  section_path: string
  heading: string
  url: string
  entity_slug: string | null
  score: number
}

export interface AgentResponse {
  answer: string
  cards: ProductCardData[]
  citations: AgentCitation[]
  tool_calls: { tool: string; arguments: Record<string, unknown>; error: string }[]
  understanding: Understanding
  clarifying_question: string
  guardrails: { ok: boolean; [key: string]: unknown }
  latency_ms: number
  query_log_id: string
  language: string
}
