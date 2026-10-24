<script setup lang="ts">
import type { Product } from "~/types/catalog"
import { formatDate, formatPrice } from "~/utils/format"

const props = withDefaults(defineProps<{ product: Product; showActions?: boolean }>(), {
  showActions: true,
})
const shelf = useCustomerShelf()

const snapshot = computed(() => ({
  sku: props.product.sku,
  title: props.product.display_title,
  price: props.product.price,
  currency: props.product.currency,
  entity_type: props.product.entity_type,
  entity_slug: props.product.entity_slug,
  in_stock: props.product.in_stock,
  updated_at: props.product.price_updated_at ?? props.product.updated_at,
}))

const isFavorite = computed(() => shelf.isFavorite(props.product.sku))
const isCompared = computed(() => shelf.isCompared(props.product.sku))
const compareLimitReached = computed(
  () => shelf.compareItems.value.length >= 4 && !isCompared.value,
)

const TYPE_LABELS: Record<string, string> = {
  cpu: "پردازنده",
  gpu: "کارت گرافیک",
  ram: "حافظه",
  motherboard: "مادربرد",
  psu: "منبع تغذیه",
  case: "کیس",
  cooler: "خنک‌کننده",
  storage: "ذخیره‌سازی",
  prebuilt: "سیستم آماده",
}
</script>

<template>
  <article
    class="flex flex-col rounded-xl border border-slate-200 bg-surface p-4 transition hover:border-brand-300 hover:shadow-sm"
  >
    <div class="mb-2 flex items-start justify-between gap-2">
      <h3 class="font-semibold leading-snug">{{ props.product.display_title }}</h3>
      <span
        class="shrink-0 rounded-full px-2 py-0.5 text-xs"
        :class="props.product.entity_type === 'prebuilt' ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-600'"
      >
        {{ TYPE_LABELS[props.product.entity_type] ?? props.product.entity_type }}
      </span>
    </div>

    <p class="mb-3 text-lg font-bold text-slate-900">
      {{ formatPrice(props.product.price, props.product.currency) }}
    </p>

    <div class="mt-auto flex items-center justify-between text-xs text-slate-500">
      <span>
        <span
          class="inline-block w-2 h-2 rounded-full align-middle"
          :class="props.product.in_stock ? 'bg-emerald-500' : 'bg-rose-400'"
        />
        <span class="mr-1.5">
          {{ props.product.in_stock ? `موجود (${props.product.stock})` : "ناموجود" }}
        </span>
      </span>
      <span v-if="props.product.warranty_months" dir="ltr">
        {{ props.product.warranty_months }}m warranty
      </span>
    </div>

    <p class="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-400">
      آخرین به‌روزرسانی: {{ formatDate(props.product.price_updated_at ?? props.product.updated_at) }}
    </p>

    <div v-if="props.showActions" class="mt-3 flex gap-2 border-t border-slate-100 pt-3">
      <button
        type="button"
        class="min-h-10 flex-1 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-700"
        :aria-pressed="isFavorite"
        @click.stop="shelf.toggleFavorite(snapshot)"
      >
        {{ isFavorite ? "ذخیره شد" : "علاقه‌مندی" }}
      </button>
      <button
        type="button"
        class="min-h-10 flex-1 rounded-lg border border-slate-200 px-3 text-xs font-medium text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
        :aria-pressed="isCompared"
        :disabled="compareLimitReached"
        :title="compareLimitReached ? 'حداکثر چهار محصول را می‌توان مقایسه کرد.' : undefined"
        @click.stop="shelf.toggleCompare(snapshot)"
      >
        {{ isCompared ? "حذف از مقایسه" : "افزودن به مقایسه" }}
      </button>
    </div>
  </article>
</template>
