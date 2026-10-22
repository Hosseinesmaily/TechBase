<script setup lang="ts">
import type { Facets, SearchResponse, Suggestion } from "~/types/search"
import { formatPrice } from "~/utils/format"

useSeoMeta({
  title: "جستجو | تک‌بیس",
  description: "جستجو در قطعات، محصولات و مقالات ویکی.",
})

const route = useRoute()
const router = useRouter()

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
      <form class="flex gap-2" @submit.prevent="runSearch">
        <div class="relative flex-1">
          <input
            v-model="q"
            type="search"
            placeholder="مثلاً: رایزن ۷ ۸۰۰۰X3D یا RTX 4060"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            @focus="showSuggestions = true"
            @blur="closeSuggestionsLater"
          />
          <ul
            v-if="showSuggestions && suggestions.suggestions.length"
            class="absolute inset-x-0 top-full z-20 mt-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg"
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
          class="rounded-lg bg-brand-600 px-5 py-2 text-sm font-medium text-white hover:bg-brand-500"
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

      <ul v-if="hits.length" class="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <li v-for="hit in hits" :key="`${hit.kind}-${hit.id}`">
          <component
            :is="hit.kind === 'page' ? 'NuxtLink' : 'NuxtLink'"
            :to="hit.kind === 'page' ? `/wiki/${hit.slug}/` : hit.kind === 'product' ? `/catalog/product/${hit.slug}/` : `/entity/${hit.slug}/`"
            class="block px-4 py-3 transition hover:bg-slate-50"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="font-medium">{{ hit.title }}</p>
                <p v-if="hit.subtitle" class="mt-0.5 truncate text-sm text-slate-500">
                  {{ hit.subtitle }}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <span
                  class="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                >
                  {{ KIND_LABELS[hit.kind] ?? hit.kind }}
                </span>
                <span v-if="hit.price" class="text-sm font-bold">
                  {{ formatPrice(hit.price) }}
                </span>
              </div>
            </div>
            <p
              v-if="hit.in_stock === false"
              class="mt-1 text-xs text-rose-500"
            >
              ناموجود
            </p>
          </component>
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
