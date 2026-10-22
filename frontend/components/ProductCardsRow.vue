<script setup lang="ts">
/** The product cards shown next to an answer. */
import type { ProductCardData } from "~/types/agent"
import { formatPrice } from "~/utils/format"

defineProps<{ cards: ProductCardData[] }>()
</script>

<template>
  <div v-if="cards.length" class="mt-4">
    <p class="mb-2 text-xs font-medium text-slate-500">پیشنهادها:</p>
    <div class="grid gap-2 sm:grid-cols-2">
      <NuxtLink
        v-for="card in cards"
        :key="card.sku"
        :to="`/catalog/product/${card.sku}/`"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 transition hover:border-brand-300"
      >
        <p class="text-sm font-medium leading-snug">{{ card.title }}</p>
        <div class="mt-1 flex items-center justify-between text-xs">
          <span class="font-bold text-slate-900">{{ formatPrice(card.price, card.currency) }}</span>
          <span :class="card.in_stock ? 'text-emerald-600' : 'text-rose-500'">
            {{ card.in_stock ? `موجود (${card.stock})` : "ناموجود" }}
          </span>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>
