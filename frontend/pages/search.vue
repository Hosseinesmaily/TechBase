<script setup lang="ts">
import type { Entity, Paginated, Product } from "~/types/catalog"
import { formatPrice } from "~/utils/format"

useSeoMeta({
  title: "جستجو | تک‌بیس",
  description: "جستجو در قطعات و محصولات فروشگاه.",
})

const route = useRoute()
const router = useRouter()

const q = ref(String(route.query.q ?? ""))
const submitted = ref(String(route.query.q ?? ""))

const { data, pending, error } = await useFetch<{
  products: Paginated<Product>
  entities: Paginated<Entity>
}>(
  "/api/v1/search/",
  {
    server: true,
    query: computed(() => ({ q: submitted.value, page_size: "24" })),
    key: "search",
    watch: [submitted],
    default: () => ({
      products: { count: 0, next: null, previous: null, results: [] },
      entities: { count: 0, next: null, previous: null, results: [] },
    }),
  },
)

function runSearch() {
  submitted.value = q.value.trim()
  router.replace({ path: "/search", query: submitted.value ? { q: submitted.value } : {} })
}

const total = computed(() => (data.value?.products.count ?? 0) + (data.value?.entities.count ?? 0))
</script>

<template>
  <div>
    <h1 class="mb-1 text-2xl font-bold">جستجو</h1>
    <p class="mb-6 text-sm text-slate-500">
      در نام فارسی یا انگلیسی قطعات و محصولات جستجو کنید.
    </p>

    <form class="mb-8 flex gap-2" @submit.prevent="runSearch">
      <input
        v-model="q"
        type="search"
        placeholder="مثلاً: رایزن ۷ ۸۰۰۰X3D یا RTX 4060"
        class="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
      />
      <button
        type="submit"
        class="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-500"
      >
        جستجو
      </button>
    </form>

    <p v-if="pending" class="py-8 text-center text-sm text-slate-500">در حال جستجو…</p>

    <div v-else-if="error" class="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">
      جستجو در حال حاضر در دسترس نیست. (جستجوی هیبریدی در فاز ۳ فعال می‌شود؛
      <code class="text-xs" dir="ltr">/api/v1/search/</code>)
    </div>

    <template v-else-if="submitted">
      <p class="mb-4 text-sm text-slate-500">{{ total }} نتیجه برای «{{ submitted }}»</p>

      <section v-if="data && data.products.results.length" class="mb-8">
        <h2 class="mb-3 font-semibold">محصولات</h2>
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="product in data.products.results"
            :key="product.id"
            class="rounded-xl border border-slate-200 bg-white p-4"
          >
            <h3 class="mb-1 font-medium leading-snug">{{ product.display_title }}</h3>
            <p class="text-sm font-bold text-slate-900">
              {{ formatPrice(product.price, product.currency) }}
            </p>
            <p class="mt-1 text-xs text-slate-500">
              {{ product.in_stock ? `موجود (${product.stock})` : "ناموجود" }}
            </p>
          </div>
        </div>
      </section>

      <section v-if="data && data.entities.results.length">
        <h2 class="mb-3 font-semibold">قطعات و مفاهیم</h2>
        <ul class="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white">
          <li v-for="entity in data.entities.results" :key="entity.id" class="px-4 py-3">
            <p class="font-medium">{{ entity.display_title }}</p>
            <p v-if="entity.summary_fa" class="mt-0.5 text-sm text-slate-500">
              {{ entity.summary_fa }}
            </p>
            <p v-if="entity.price_min" class="mt-1 text-xs text-slate-400">
              از {{ formatPrice(entity.price_min) }}
            </p>
          </li>
        </ul>
      </section>

      <p
        v-if="total === 0"
        class="rounded-lg border border-dashed border-slate-300 py-10 text-center text-slate-500"
      >
        نتیجه‌ای پیدا نشد. عبارت دیگری امتحان کنید.
      </p>
    </template>

    <div v-else class="rounded-xl border border-dashed border-slate-300 p-8 text-center">
      <p class="text-slate-500">عبارتی برای جستجو وارد کنید.</p>
    </div>
  </div>
</template>
