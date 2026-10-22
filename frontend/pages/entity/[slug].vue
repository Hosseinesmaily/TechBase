<script setup lang="ts">
import type { Entity } from "~/types/catalog"
import { formatPrice } from "~/utils/format"

const route = useRoute()
const slug = computed(() => String(route.params.slug))

const { data: entity, error } = await useFetch<Entity>(
  () => `/api/v1/catalog/entities/${slug.value}/`,
  {
    server: true,
    key: `entity-${slug.value}`,
    default: () => null,
  },
)

if (error.value) {
  throw createError({ statusCode: 404, statusMessage: "این موجودیت پیدا نشد" })
}

useSeoMeta({
  title: () => entity.value?.display_title ?? "قطعات",
  description: () => entity.value?.summary_fa ?? entity.value?.summary ?? "",
})

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
  <div v-if="entity" class="max-w-3xl">
    <nav class="mb-4 text-sm text-slate-500" aria-label="مسیر">
      <NuxtLink to="/" class="hover:text-slate-900">خانه</NuxtLink>
      <span class="mx-1">/</span>
      <NuxtLink to="/catalog" class="hover:text-slate-900">کاتالوگ</NuxtLink>
      <span class="mx-1">/</span>
      <span class="text-slate-700">{{ entity.display_title }}</span>
    </nav>

    <header class="mb-6">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h1 class="text-2xl font-bold">{{ entity.display_title }}</h1>
          <p class="mt-1 text-sm text-slate-500">
            {{ TYPE_LABELS[entity.type] ?? entity.type }}
            <template v-if="entity.brand_name"> — {{ entity.brand_name }}</template>
          </p>
        </div>
        <NuxtLink
          :to="`/wiki/${entity.slug}/`"
          class="shrink-0 rounded-lg border border-brand-200 bg-brand-50 px-3 py-1.5 text-sm text-brand-700 hover:bg-brand-100"
        >
          صفحهٔ ویکی
        </NuxtLink>
      </div>
      <p v-if="entity.summary_fa" class="mt-3 leading-8 text-slate-600">
        {{ entity.summary_fa }}
      </p>
    </header>

    <section
      v-if="entity.price_min"
      class="rounded-xl border border-slate-200 bg-white p-4"
    >
      <p class="text-xs text-slate-500">شروع قیمت</p>
      <p class="mt-1 text-xl font-bold">{{ formatPrice(entity.price_min) }}</p>
    </section>
  </div>
</template>
