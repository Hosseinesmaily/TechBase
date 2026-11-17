<script setup lang="ts">
import type { ProductCardData } from "~/types/agent"
import { formatDate, formatPrice } from "~/utils/format"

defineProps<{ cards: ProductCardData[] }>()
const shelf = useCustomerShelf()

function snapshot(product: ProductCardData) {
  return {
    sku: product.sku,
    title: product.title,
    price: product.price,
    currency: product.currency,
    entity_type: product.entity_type,
    entity_slug: product.entity_slug,
    in_stock: product.in_stock,
    updated_at: product.updated_at,
  }
}
</script>

<template>
  <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    <div
      v-for="product in cards"
      :key="product.sku"
      class="rounded-xl border border-slate-200 bg-surface p-4"
    >
      <h3 class="mb-1 font-medium leading-snug">{{ product.title }}</h3>
      <p class="text-sm font-bold text-slate-900">
        {{ formatPrice(product.price, product.currency) }}
      </p>
      <p class="text-xs text-slate-500">
        {{ product.in_stock ? `موجود (${product.stock})` : "ناموجود" }}
      </p>
      <p class="mt-1 text-xs text-slate-400">به‌روزرسانی: {{ formatDate(product.updated_at) }}</p>
      <p v-if="product.recommendation_reason" class="mt-2 rounded-md bg-brand-50 px-2.5 py-2 text-xs leading-5 text-brand-800">{{ product.recommendation_reason }}</p>
      <div class="mt-3 flex gap-2 border-t border-slate-100 pt-3">
        <button type="button" class="flex-1 rounded-lg border px-2 py-2 text-xs hover:border-brand-300" @click="shelf.toggleFavorite(snapshot(product))">
          {{ shelf.isFavorite(product.sku) ? "ذخیره‌شده" : "علاقه‌مندی" }}
        </button>
        <button type="button" class="flex-1 rounded-lg border px-2 py-2 text-xs hover:border-brand-300" :disabled="shelf.compareItems.value.length >= 4 && !shelf.isCompared(product.sku)" @click="shelf.toggleCompare(snapshot(product))">
          {{ shelf.isCompared(product.sku) ? "حذف از مقایسه" : "مقایسه" }}
        </button>
      </div>
      <AddToCartButton :sku="product.sku" :in-stock="product.in_stock" class="mt-2" />
      <NuxtLink :to="`/entity/${product.entity_slug}/`" class="mt-3 text-xs font-medium text-brand-700 hover:underline">مشخصات قطعه و راهنمای مرتبط ←</NuxtLink>
    </div>
  </div>
</template>
