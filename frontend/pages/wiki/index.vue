<script setup lang="ts">
import type { Paginated, WikiPage } from "~/types/wiki"

useSeoMeta({
  title: "ویکی سخت‌افزار | تک‌بیس",
  description: "مقالات، راهنماهای خرید و توضیح مفاهیم سخت‌افزار.",
})

const type = ref("")
const page = ref(1)

const { data: pages, pending } = await useFetch<Paginated<WikiPage>>(
  "/api/v1/wiki/pages/",
  {
    server: true,
    query: computed(() => ({
      ...(type.value ? { type: type.value } : {}),
      page: String(page.value),
      page_size: "24",
    })),
    key: "wiki-pages",
    watch: [type],
    default: () => ({ count: 0, next: null, previous: null, results: [] }),
  },
)

watch(type, () => {
  page.value = 1
})

const TYPE_LABELS: Record<string, string> = {
  component: "قطعات",
  guide: "راهنمای خرید",
  concept: "مفاهیم",
}

const totalPages = computed(() => Math.max(1, Math.ceil((pages.value?.count ?? 0) / 24)))
</script>

<template>
  <div>
    <h1 class="mb-1 text-2xl font-bold">ویکی سخت‌افزار</h1>
    <p class="mb-6 text-sm text-slate-500">
      مقالات فنی، راهنماهای خرید و توضیح مفاهیم — همه با پیوندهای داخلی.
    </p>

    <div class="mb-6 flex flex-wrap gap-2">
      <button
        class="rounded-full px-3 py-1.5 text-sm transition"
        :class="type === '' ? 'bg-brand-600 text-white' : 'bg-white text-slate-600 border border-slate-200'"
        @click="type = ''"
      >
        همه
      </button>
      <button
        v-for="(label, key) in TYPE_LABELS"
        :key="key"
        class="rounded-full px-3 py-1.5 text-sm transition"
        :class="type === key ? 'bg-brand-600 text-white' : 'bg-white text-slate-600 border border-slate-200'"
        @click="type = key"
      >
        {{ label }}
      </button>
    </div>

    <p v-if="pending" class="py-8 text-center text-sm text-slate-500">در حال بارگذاری…</p>

    <template v-else>
      <p class="mb-3 text-sm text-slate-500">{{ pages?.count ?? 0 }} صفحه</p>

      <ul class="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <li v-for="item in pages?.results ?? []" :key="item.id">
          <NuxtLink
            :to="`/wiki/${item.slug}/`"
            class="block px-4 py-3 transition hover:bg-slate-50"
          >
            <p class="font-medium">{{ item.title }}</p>
            <p v-if="item.summary" class="mt-0.5 text-sm text-slate-500">
              {{ item.summary }}
            </p>
            <div class="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
              <span class="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                {{ TYPE_LABELS[item.page_type === "BuyerGuidePage" ? "guide" : item.page_type === "ConceptPage" ? "concept" : "component"] }}
              </span>
              <span v-if="item.entity" class="rounded-full bg-brand-50 px-2 py-0.5 text-brand-700">
                {{ item.entity.title }}
              </span>
              <span v-if="item.is_stale" class="rounded-full bg-amber-50 px-2 py-0.5 text-amber-700">
                نیازمند بازبینی
              </span>
            </div>
          </NuxtLink>
        </li>
      </ul>

      <p
        v-if="!pages?.results.length"
        class="rounded-lg border border-dashed border-slate-300 py-10 text-center text-slate-500"
      >
        صفحه‌ای یافت نشد.
      </p>

      <nav v-if="totalPages > 1" class="mt-8 flex justify-center gap-2">
        <button
          class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40"
          :disabled="page <= 1"
          @click="page--"
        >
          قبلی
        </button>
        <span class="px-3 py-1.5 text-sm text-slate-500">
          صفحهٔ {{ page }} از {{ totalPages }}
        </span>
        <button
          class="rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40"
          :disabled="page >= totalPages"
          @click="page++"
        >
          بعدی
        </button>
      </nav>
    </template>
  </div>
</template>
