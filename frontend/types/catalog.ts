/** Types mirroring the Django API responses (see backend/apps/catalog/serializers.py). */

export interface Product {
  id: string
  sku: string
  title: string
  title_fa: string
  display_title: string
  entity_slug: string
  entity_type: string
  entity_title_fa: string
  price: string
  currency: string
  stock: number
  in_stock: boolean
  source: string
  is_active: boolean
  warranty_months: number
  image_url: string
  price_updated_at: string | null
  updated_at: string
}

export interface Entity {
  id: string
  type: string
  slug: string
  title: string
  title_fa: string
  display_title: string
  summary: string
  summary_fa: string
  status: string
  review_by: string | null
  brand_name: string | null
  category_slug: string | null
  price_min: string | null
  in_stock: boolean
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface Brand {
  id: string
  slug: string
  name: string
  name_fa: string
  country: string
  entity_count: number
}

export interface Category {
  id: string
  slug: string
  name: string
  name_fa: string
  parent: string | null
  parent_slug: string | null
  is_active: boolean
}
