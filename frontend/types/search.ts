/** Types for the hybrid search API (see backend/apps/search/views.py). */

export interface SearchHit {
  id: string
  slug: string
  title: string
  subtitle: string
  kind: "entity" | "product" | "page"
  score: number
  price: string | null
  in_stock: boolean | null
  entity_type?: string
  entity_slug?: string
  brand?: string
  page_type?: string
  sku?: string
  currency?: string
  stock?: number
  updated_at?: string
  recommendation_reason?: string
}

export interface SearchResponse {
  query: string
  total: number
  hits: SearchHit[]
  facets: Record<string, Record<string, number>>
  took_ms: number
  backend: "hybrid" | "meilisearch" | "postgres"
  intent?: { entity_type?: string; use_case?: string; resolution?: string; recommendations?: string }
}

export interface Suggestion {
  id: string
  text: string
  slug: string
  kind: string
}

export interface Facets {
  brands: { slug: string; name: string; name_fa: string; count: number }[]
  types: { value: string; label: string; count: number }[]
  in_stock: { yes: number; no: number }
}
