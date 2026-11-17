<script setup lang="ts">
import type { Product } from "~/types/catalog"
import { formatDate, formatPrice, formatWarranty } from "~/utils/format"

const props = withDefaults(
  defineProps<{ product: Product; showActions?: boolean; linkToWiki?: boolean }>(),
  { showActions: true, linkToWiki: true },
)
const shelf = useCustomerShelf()

/**
 * The published article about this part, as an address — read from the API's
 * `wiki_slug`, which the backend takes from the entity↔page binding. An empty
 * string means there is no article, and then nothing navigates anywhere.
 */
const wikiPath = computed(() => {
  if (!props.linkToWiki || !props.product.wiki_slug) return ""
  return `/wiki/${props.product.wiki_slug}/`
})
const wikiTitle = computed(() =>
  wikiPath.value ? "دوبار کلیک: مقالهٔ ویکی این قطعه" : undefined,
)

/**
 * A double click on the card's main area opens the article. A single click keeps
 * the card's previous behaviour (it did nothing), and the action buttons sit
 * outside this area, so they can never navigate by accident.
 */
function openWiki() {
  if (!wikiPath.value) return
  void navigateTo(wikiPath.value)
}

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
    <!-- The card's main area: a double click opens the wiki article. -->
    <div
      class="flex flex-1 flex-col"
      :class="wikiPath ? 'cursor-pointer' : ''"
      :title="wikiTitle"
      @dblclick="openWiki"
    >
    <div v-if="props.product.image_thumbnail" class="mb-3 overflow-hidden rounded-lg bg-slate-100">
      <img
        :src="props.product.image_thumbnail"
        :alt="props.product.display_title"
        class="h-36 w-full object-cover"
        loading="lazy"
        width="400"
        height="300"
      />
    </div>
    <!--
      No image: a quiet default frame instead of a broken image or an empty gap.
      The alt text above is the product name, so the picture is never the only
      carrier of information.
    -->
    <div
      v-else
      class="mb-3 grid h-36 place-items-center rounded-lg border border-dashed border-slate-200 bg-slate-50"
      aria-hidden="true"
    >
      <svg viewBox="0 0 24 24" class="h-8 w-8 text-slate-300" fill="none" stroke="currentColor" stroke-width="1.6">
        <path d="M4 6.5h16v11H4zM8 20h8M9 10l2.2 2.4 1.8-1.4 3 3.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>

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
      <span v-if="props.product.warranty_months">
        {{ formatWarranty(props.product.warranty_months) }}
      </span>
    </div>

    <p class="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-400">
      آخرین به‌روزرسانی: {{ formatDate(props.product.price_updated_at ?? props.product.updated_at) }}
    </p>

    </div>

    <!--
      Mobile and keyboard: a real link, because a double click is not a gesture a
      phone can offer. It is the same address, so both paths agree.
    -->
    <NuxtLink
      v-if="wikiPath"
      :to="wikiPath"
      class="mt-3 inline-flex items-center gap-1.5 text-xs font-medium text-brand-700 hover:underline"
    >
      <svg viewBox="0 0 24 24" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
        <path d="M4 5.5h11.5L20 9v9.5H4z" stroke-linejoin="round" />
        <path d="M8 9h6M8 12.5h6M8 16h4" stroke-linecap="round" />
      </svg>
      مقالهٔ ویکی این قطعه
    </NuxtLink>

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
    <AddToCartButton v-if="props.showActions" :sku="props.product.sku" :in-stock="props.product.in_stock" class="mt-2" />
  </article>
</template>
