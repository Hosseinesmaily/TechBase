<script setup lang="ts">
import type { Paginated, WikiPage } from "~/types/wiki"

const PAGE_SIZE = 24

useSeoMeta({
  title: "ویکی سخت‌افزار | تک‌بیس",
  description: "مقالات، راهنماهای خرید و توضیح مفاهیم سخت‌افزار.",
})

const route = useRoute()
const router = useRouter()

/**
 * The filter and the page number live in the URL: a filtered list or a page-three
 * view is shareable, survives a reload, and works with browser back/forward.
 */
const type = ref(String(route.query.type ?? ""))
const page = ref(Math.max(1, Number(route.query.page ?? 1) || 1))

/** The HTTP status of a failed `$fetch`, or 0 when it is not an HTTP error. */
function statusOf(cause: unknown): number {
  const failure = cause as { statusCode?: number; response?: { status?: number } }
  return failure?.statusCode ?? failure?.response?.status ?? 0
}

/**
 * The page list.
 *
 * An out-of-range page (an old bookmark, or a filter that shrank the list) must not
 * look like an outage: the request falls back to the first page and the state
 * follows, so a stale link still lands on a readable list.
 */
const { data: pages, pending, error, refresh } = await useAsyncData<Paginated<WikiPage>>(
  "wiki-pages",
  async () => {
    const query = {
      ...(type.value ? { type: type.value } : {}),
      page: String(page.value),
      page_size: String(PAGE_SIZE),
    }
    try {
      return await $fetch<Paginated<WikiPage>>("/api/v1/wiki/pages/", { query })
    } catch (cause) {
      if (page.value > 1 && statusOf(cause) === 404) {
        page.value = 1
        return await $fetch<Paginated<WikiPage>>("/api/v1/wiki/pages/", {
          query: { ...query, page: "1" },
        })
      }
      throw cause
    }
  },
  {
    server: true,
    watch: [type, page],
    default: () => ({ count: 0, next: null, previous: null, results: [] }),
  },
)

const results = computed(() => pages.value?.results ?? [])
const totalPages = computed(() => Math.max(1, Math.ceil((pages.value?.count ?? 0) / PAGE_SIZE)))
const isEmpty = computed(() => !pending.value && !error.value && results.value.length === 0)

/**
 * The animation key changes when *new content* arrives, not when a request starts,
 * so the list cross-fades with the new articles instead of flashing the old ones.
 */
const panelKey = computed(
  () => `${type.value}-${page.value}-${pages.value?.count ?? 0}-${results.value[0]?.id ?? "-"}`,
)

const filters = [
  { value: "", label: "همه" },
  { value: "component", label: "قطعات" },
  { value: "guide", label: "راهنمای خرید" },
  { value: "concept", label: "مفاهیم" },
]

const TYPE_LABELS: Record<string, string> = {
  component: "قطعات",
  guide: "راهنمای خرید",
  concept: "مفاهیم",
}

/** Keep the URL in step with the filter/page state. */
function syncUrl() {
  const query: Record<string, string> = {}
  if (type.value) query.type = type.value
  if (page.value > 1) query.page = String(page.value)
  void router.replace({ path: "/wiki", query })
}

function selectType(next: string) {
  if (type.value === next) return
  type.value = next
  // A new filter starts at page 1, so the result is never empty by accident.
  page.value = 1
  syncUrl()
}

function goToPage(next: number) {
  const target = Math.min(Math.max(1, next), totalPages.value)
  if (target === page.value) return
  page.value = target
  syncUrl()
  if (import.meta.client) window.scrollTo({ top: 0, behavior: "smooth" })
}

/** Back/forward changes the query without touching our refs, so mirror it. */
watch(
  () => route.query,
  (query) => {
    const nextType = String(query.type ?? "")
    const nextPage = Math.max(1, Number(query.page ?? 1) || 1)
    if (nextType !== type.value) type.value = nextType
    if (nextPage !== page.value) page.value = nextPage
  },
)
</script>

<template>
  <div>
    <h1 class="mb-1 text-2xl font-bold">ویکی سخت‌افزار</h1>
    <p class="mb-6 text-sm text-slate-500">
      مقالات فنی، راهنماهای خرید و توضیح مفاهیم — همه با پیوندهای داخلی.
    </p>

    <div class="mb-6 flex flex-wrap gap-2">
      <button
        v-for="filter in filters"
        :key="filter.value || 'all'"
        type="button"
        class="rounded-full px-3 py-1.5 text-sm transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
        :class="
          type === filter.value
            ? 'bg-brand-600 text-white'
            : 'border border-slate-200 bg-surface text-slate-600 hover:border-brand-300 hover:text-brand-700'
        "
        :aria-pressed="type === filter.value"
        @click="selectType(filter.value)"
      >
        {{ filter.label }}
      </button>
    </div>

    <ApiErrorNotice
      v-if="error"
      class="mb-4"
      title="فهرست مقالات دریافت نشد"
      message="ارتباط با سرور برقرار نشد. ممکن است سرویس موقتاً در دسترس نباشد؛ می‌توانید دوباره تلاش کنید."
      @retry="refresh"
    />

    <Transition v-else name="wiki-panel" mode="out-in">
      <div :key="panelKey" class="min-h-[18rem]" :aria-busy="pending">
        <p class="mb-3 text-sm text-slate-500">{{ pages?.count ?? 0 }} صفحه</p>

        <p
          v-if="pending && !results.length"
          class="py-8 text-center text-sm text-slate-500"
          role="status"
          aria-live="polite"
        >
          در حال بارگذاری...
        </p>

        <ul
          v-else-if="results.length"
          class="divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200 bg-surface"
        >
          <li v-for="item in results" :key="item.id">
            <NuxtLink
              :to="`/wiki/${item.slug}/`"
              class="block px-4 py-3 transition hover:bg-slate-50"
            >
              <p class="font-medium"><BidiText :text="item.title" /></p>
              <p v-if="item.summary" class="mt-0.5 line-clamp-2 text-sm text-slate-500">
                <BidiText :text="item.summary" />
              </p>
              <div class="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                <span class="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
                  {{ TYPE_LABELS[item.page_type === "BuyerGuidePage" ? "guide" : item.page_type === "ConceptPage" ? "concept" : "component"] }}
                </span>
                <span
                  v-if="item.is_stale"
                  class="rounded-full bg-amber-50 px-2 py-0.5 text-amber-700"
                >
                  نیازمند بازبینی
                </span>
              </div>
            </NuxtLink>
          </li>
        </ul>

        <div
          v-else-if="isEmpty"
          class="rounded-lg border border-dashed border-slate-300 py-10 text-center text-slate-500"
        >
          <p>صفحه‌ای با این فیلتر یافت نشد.</p>
          <button
            v-if="type"
            type="button"
            class="mt-3 text-sm font-medium text-brand-700 underline"
            @click="selectType('')"
          >
            نمایش همهٔ مقالات
          </button>
        </div>

        <PaginationNav class="mt-8" :page="page" :total-pages="totalPages" @change="goToPage" />
      </div>
    </Transition>

  </div>
</template>

<style scoped>
/*
 * A short, quiet cross-fade for the list. Only opacity and transform animate, so
 * the layout never jumps; the min-height on the panel stops the page from
 * collapsing between the two halves of the transition.
 */
.wiki-panel-enter-active,
.wiki-panel-leave-active {
  transition: opacity 150ms ease, transform 190ms cubic-bezier(0.2, 0.75, 0.25, 1);
}

.wiki-panel-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.wiki-panel-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (prefers-reduced-motion: reduce) {
  .wiki-panel-enter-active,
  .wiki-panel-leave-active {
    transition-duration: 0.01ms;
  }

  .wiki-panel-enter-from,
  .wiki-panel-leave-to {
    transform: none;
  }
}
</style>

