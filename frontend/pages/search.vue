<script setup lang="ts">
import type { Facets, SearchResponse, Suggestion } from "~/types/search"
import { formatPrice } from "~/utils/format"

useSeoMeta({
  title: "جستجو | تک‌بیس",
  description: "جستجو در قطعات، محصولات و مقالات ویکی.",
})

const route = useRoute()
const router = useRouter()
const shelf = useCustomerShelf()

const q = ref(String(route.query.q ?? ""))
const submitted = ref(String(route.query.q ?? ""))
const type = ref(String(route.query.type ?? ""))
const brand = ref(String(route.query.brand ?? ""))
const inStockOnly = ref(route.query.in_stock === "true")
const kind = ref(String(route.query.kind ?? ""))

const { data: facets } = await useFetch<Facets>("/api/v1/search/facets/", {
  server: true,
  default: () => ({ brands: [], types: [], in_stock: { yes: 0, no: 0 } }),
})

const searchQuery = computed(() => ({
  ...(submitted.value ? { q: submitted.value } : {}),
  ...(type.value ? { type: type.value } : {}),
  ...(brand.value ? { brand: brand.value } : {}),
  ...(inStockOnly.value ? { in_stock: "true" } : {}),
  ...(kind.value ? { kind: kind.value } : {}),
  page_size: "30",
}))

// `useAsyncData` with an explicit watcher: `useFetch` cannot type a computed
// `query` reliably, and the filters need to trigger a re-fetch.
const { data: results, pending, error } = await useAsyncData<SearchResponse>(
  "search-results",
  () => $fetch<SearchResponse>("/api/v1/search/", { query: searchQuery.value }),
  {
    server: true,
    watch: [searchQuery],
    default: (): SearchResponse => ({
      query: "",
      total: 0,
      hits: [],
      facets: {},
      took_ms: 0,
      backend: "postgres",
    }),
  },
)

/** Autocomplete suggestions, fetched while the user types. */
const { data: suggestions } = await useFetch<{ suggestions: Suggestion[] }>(
  "/api/v1/search/autocomplete/",
  {
    server: false,
    lazy: true,
    query: computed(() => ({ q: q.value })),
    watch: [q],
    default: () => ({ suggestions: [] }),
  },
)

const showSuggestions = ref(false)

/** Close the suggestion list a moment after the input loses focus, so a
 *  click on a suggestion still registers. */
function closeSuggestionsLater() {
  window.setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}

function runSearch() {
  submitted.value = q.value.trim()
  shelf.saveSearch(submitted.value)
  showSuggestions.value = false
  syncUrl()
}

function pickSuggestion(suggestion: Suggestion) {
  q.value = suggestion.text
  runSearch()
}

function syncUrl() {
  const query: Record<string, string> = {}
  if (submitted.value) query.q = submitted.value
  if (type.value) query.type = type.value
  if (brand.value) query.brand = brand.value
  if (inStockOnly.value) query.in_stock = "true"
  if (kind.value) query.kind = kind.value
  router.replace({ path: "/search", query })
}

watch([type, brand, inStockOnly, kind], () => {
  syncUrl()
})

const KIND_LABELS: Record<string, string> = {
  entity: "قطعات",
  product: "محصولات",
  page: "مقالات",
}

const hits = computed(() => results.value?.hits ?? [])
const searchIntent = computed(() => results.value?.intent)
const comparedCount = computed(() => shelf.compareItems.value.length)

const TYPE_LABELS: Record<string, string> = {
  gpu: "کارت گرافیک", cpu: "پردازنده", ram: "حافظهٔ رم", motherboard: "مادربرد",
  psu: "منبع تغذیه", case: "کیس", cooler: "خنک‌کننده", storage: "ذخیره‌سازی", prebuilt: "سیستم آماده",
}

function productSnapshot(hit: (typeof hits.value)[number]) {
  if (!hit.sku) return null
  return {
    sku: hit.sku,
    title: hit.title,
    price: hit.price ?? "",
    currency: hit.currency ?? "IRT",
    entity_type: hit.entity_type ?? "",
    entity_slug: hit.entity_slug ?? hit.slug,
    in_stock: hit.in_stock === true,
    updated_at: hit.updated_at ?? "",
  }
}

function toggleCompare(hit: (typeof hits.value)[number]) {
  const product = productSnapshot(hit)
  if (product) shelf.toggleCompare(product)
}
const total = computed(() => results.value?.total ?? 0)
const tookMs = computed(() => results.value?.took_ms ?? 0)
const backendLabel = computed(() => {
  switch (results.value?.backend) {
    case "hybrid":
      return "جستجوی ترکیبی"
    case "meilisearch":
      return "مکانیکی"
    default:
      return "پستگرس"
  }
})
</script>

<template>
  <div>
    <h1 class="mb-1 text-2xl font-bold">جستجو</h1>
    <p class="mb-6 text-sm text-slate-500">
      در نام فارسی یا انگلیسی قطعات، محصولات و مقالات ویکی جستجو کنید.
    </p>

    <div class="relative mb-6">
      <form class="search-shell flex items-center gap-2 p-2" @submit.prevent="runSearch">
        <div class="relative min-w-0 flex-1">
          <svg class="pointer-events-none absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <circle cx="10.8" cy="10.8" r="6.3" />
            <path d="m16 16 4.2 4.2" stroke-linecap="round" />
          </svg>
          <input
            v-model="q"
            type="search"
            placeholder="مثلاً: رایزن ۷ ۸۰۰۰X3D یا RTX 4060"
            class="search-field w-full rounded-xl py-3 pl-4 pr-11 text-base"
            @focus="showSuggestions = true"
            @blur="closeSuggestionsLater"
          />
          <ul
            v-if="showSuggestions && suggestions.suggestions.length"
            class="absolute inset-x-0 top-full z-20 mt-2 overflow-hidden rounded-xl border border-slate-200 bg-surface shadow-lg"
          >
            <li v-for="s in suggestions.suggestions" :key="s.id">
              <button
                type="button"
                class="block w-full px-3 py-2 text-start text-sm hover:bg-slate-50"
                @mousedown.prevent="pickSuggestion(s)"
              >
                {{ s.text }}
              </button>
            </li>
          </ul>
        </div>
        <button
          type="submit"
          class="search-submit rounded-xl px-5 py-3 text-sm font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300"
        >
          جستجو
        </button>
      </form>
    </div>

    <div class="mb-6 grid gap-3 sm:grid-cols-4">
      <select
        v-model="kind"
        class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
      >
        <option value="">همهٔ نتایج</option>
        <option value="entity">قطعات</option>
        <option value="product">محصولات</option>
        <option value="page">مقالات</option>
      </select>

      <select
        v-model="type"
        class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
      >
        <option value="">همهٔ انواع</option>
        <option v-for="t in facets.types" :key="t.value" :value="t.value">
          {{ t.label }} ({{ t.count }})
        </option>
      </select>

      <select
        v-model="brand"
        class="rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
      >
        <option value="">همهٔ برندها</option>
        <option v-for="b in facets.brands" :key="b.slug" :value="b.slug">
          {{ b.name_fa || b.name }} ({{ b.count }})
        </option>
      </select>

      <label class="flex items-center gap-2 text-sm">
        <input v-model="inStockOnly" type="checkbox" class="h-4 w-4 rounded" />
        فقط موجود
      </label>
    </div>

    <p v-if="pending" class="py-8 text-center text-sm text-slate-500">در حال جستجو…</p>

    <div v-else-if="error" class="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">
      جستجو در حال حاضر در دسترس نیست.
    </div>

    <template v-else-if="submitted">
      <p class="mb-4 text-sm text-slate-500">
        {{ total }} نتیجه برای «{{ submitted }}»
        <span class="text-xs text-slate-400">
          — {{ tookMs }} میلی‌ثانیه ({{ backendLabel }})
        </span>
      </p>

      <div v-if="searchIntent?.entity_type" class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-100 bg-brand-50/60 px-4 py-3 text-sm">
        <p class="text-slate-700">
          نتایج بر اساس <strong>{{ TYPE_LABELS[searchIntent.entity_type] ?? searchIntent.entity_type }}</strong>
          <span v-if="searchIntent.use_case === 'gaming'"> برای بازی</span>
          <span v-if="searchIntent.resolution"> در {{ searchIntent.resolution }}</span>
          مرتب شده‌اند. رتبه‌بندی با موجودی و دادهٔ بنچمارک انجام می‌شود.
        </p>
        <NuxtLink v-if="comparedCount >= 2" to="/compare" class="shrink-0 rounded-lg bg-brand-600 px-3 py-2 text-xs font-semibold text-white hover:bg-brand-500">
          مقایسهٔ {{ comparedCount }} انتخاب
        </NuxtLink>
      </div>

      <ul v-if="hits.length" class="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-surface">
        <li v-for="hit in hits" :key="`${hit.kind}-${hit.id}`">
          <div class="flex flex-col gap-3 px-4 py-3 transition hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between">
            <NuxtLink :to="hit.kind === 'page' ? `/wiki/${hit.slug}/` : `/entity/${hit.entity_slug || hit.slug}/`" class="min-w-0 flex-1">
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="font-medium">{{ hit.title }}</p>
                  <p v-if="hit.subtitle" class="mt-0.5 truncate text-sm text-slate-500">{{ hit.subtitle }}</p>
                  <p v-if="hit.recommendation_reason" class="mt-1 text-xs text-brand-700">{{ hit.recommendation_reason }}</p>
                </div>
                <span class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">{{ KIND_LABELS[hit.kind] ?? hit.kind }}</span>
              </div>
              <p class="mt-1 flex flex-wrap gap-x-3 text-xs text-slate-500">
                <span v-if="hit.price" class="font-bold text-slate-800">{{ formatPrice(hit.price, hit.currency) }}</span>
                <span v-if="hit.in_stock !== null">{{ hit.in_stock ? `موجود (${hit.stock ?? 0})` : "ناموجود" }}</span>
              </p>
            </NuxtLink>
            <div v-if="hit.kind === 'product' && productSnapshot(hit)" class="flex shrink-0 gap-2">
              <button type="button" class="rounded-lg border px-3 py-2 text-xs hover:border-brand-300" @click="shelf.toggleFavorite(productSnapshot(hit)!)">
                {{ shelf.isFavorite(hit.sku ?? "") ? "ذخیره‌شده" : "علاقه‌مندی" }}
              </button>
              <button type="button" class="rounded-lg border px-3 py-2 text-xs hover:border-brand-300" @click="toggleCompare(hit)">
                {{ shelf.isCompared(hit.sku ?? "") ? "حذف از مقایسه" : "افزودن به مقایسه" }}
              </button>
            </div>
          </div>
        </li>
      </ul>

      <p
        v-else
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
