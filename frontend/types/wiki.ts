/** Types for the wiki API (see backend/apps/content/api.py). */

import type { Paginated } from "~/types/catalog"

export type { Paginated }

export interface WikiEntityRef {
  slug: string
  title: string
  type: string
}

export interface WikiBlock {
  type:
    | "heading"
    | "paragraph"
    | "rich_text"
    | "list"
    | "quote"
    | "callout"
    | "spec_table"
    | "image"
    | "related_entity"
  level?: string
  text?: string
  id?: string
  html?: string
  style?: string
  items?: string[]
  source?: string
  kind?: string
  title?: string
  rows?: { label: string; value: string }[]
  url?: string
  caption?: string
  entity_slug?: string
  note?: string
}

export interface WikiLink {
  type: string
  text: string
  target_slug: string
  target_title: string
  target_exists: boolean
  section_path: string
}

export interface WikiPage {
  id: number
  title: string
  slug: string
  path: string
  page_type: string
  summary: string
  review_by: string | null
  is_stale: boolean
  tags: string[]
  language: string
  entity: WikiEntityRef | null
  last_updated: string | null
  /** The article image, when the editor uploaded one ("" otherwise). */
  hero_image?: string
  hero_thumbnail?: string
  body?: WikiBlock[]
  links?: WikiLink[]
  use_case?: string
  resolution?: string
  budget_max?: string | null
  recommended_products?: {
    sku: string
    title: string
    price: string
    currency: string
    in_stock: boolean
    stock: number
    entity_slug: string
  }[]
}

export interface HoverCard {
  entity: {
    slug: string
    title: string
    type: string
    brand: string | null
    summary: string
  }
  product: {
    sku: string
    price: string
    currency: string
    stock: number
    in_stock: boolean
    price_updated_at: string | null
  } | null
  specs: { key: string; label: string; value: string | number }[]
  has_page: boolean
  page_url: string | null
}
