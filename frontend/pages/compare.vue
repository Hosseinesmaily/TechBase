<script setup lang="ts">
import type { Product } from "~/types/catalog"
import { formatDate, formatPrice } from "~/utils/format"

interface ComparisonRow {
  key: string
  values: (string | number | null)[]
}

interface CompareResponse {
  products: (Product & { brand: string })[]
  specs: ComparisonRow[]
  benchmarks: {
    component: string
    game: string
    game_fa: string
    resolution: string
    preset?: string
    avg_fps: number
    p1_low: number | null
    tested_at?: string
    source?: string
  }[]
}

const route = useRoute()
const router = useRouter()
const shelf = useCustomerShelf()
const account = useAccount()

/** The SKUs named in the URL, normalised to strings (never null, never blank). */
const skus = computed<string[]>(() => {
  const raw = route.query.skus
  const values =
    typeof raw === "string"
      ? raw.split(",")
      : Array.isArray(raw)
        ? raw.map((item) => String(item ?? ""))
        : []
  return values.map((item) => item.trim()).filter(Boolean)
})

const EMPTY_COMPARISON = (): CompareResponse => ({ products: [], specs: [], benchmarks: [] })
/** SKUs the API reported as gone; they are pruned so the page heals itself. */
const droppedSkus = ref<string[]>([])

/**
 * Read the SKUs named in the URL from the API.
 *
 * The shelf lives in this browser, so it can hold a product the catalog no longer
 * sells. The API refuses the whole request in that case, which used to blank the
 * page («مقایسه ممکن نشد»); now the missing SKUs are dropped from the shelf and
 * from the URL, and the products that do exist are compared.
 */
const { data, pending, error } = await useAsyncData<CompareResponse>(
  "compare",
  async () => {
    const wanted = skus.value
    if (wanted.length < 2) return EMPTY_COMPARISON()

    try {
      // `account.request` carries the CSRF token: a POST to Django works for a
      // guest, but DRF enforces CSRF once the visitor is signed in, so a plain
      // `$fetch` here answered 403 the moment the user logged in.
      return await account.request<CompareResponse>("/api/v1/ai/compare/", {
        method: "POST",
        body: JSON.stringify({ skus: wanted }),
      })
    } catch (cause) {
      const missing = unknownSkusFrom(cause)
      const remaining = wanted.filter((sku) => !missing.includes(sku))
      if (!missing.length || remaining.length < 2) throw cause

      for (const sku of missing) shelf.removeCompare(sku)
      droppedSkus.value = missing
      const comparison = await account.request<CompareResponse>("/api/v1/ai/compare/", {
        method: "POST",
        body: JSON.stringify({ skus: remaining }),
      })
      if (import.meta.client) {
        await router.replace({ path: "/compare", query: { skus: remaining.join(",") } })
      }
      return comparison
    }
  },
  {
    // Client-side only: this page POSTs to Django, and an SSR POST goes through
    // Nitro's own internal call, where the request body does not survive the
    // proxy hop — the API then answers 400 and the page showed "مقایسه ممکن نشد"
    // even for two valid products. In the browser the same POST works (the proxy
    // forwards it), so the table is filled right after hydration.
    server: false,
    watch: [skus],
    default: EMPTY_COMPARISON,
  },
)

/** The SKUs the API named as unknown in its 404 message. */
function unknownSkusFrom(cause: unknown): string[] {
  const failure = cause as {
    data?: { error?: string }
    statusMessage?: string
    message?: string
  }
  const message = failure?.data?.error ?? failure?.statusMessage ?? failure?.message ?? ""
  if (!/unknown skus/i.test(message)) return []
  return message
    .split(":")
    .slice(1)
    .join(":")
    .split(",")
    .map((sku) => sku.trim())
    .filter(Boolean)
}

const selectedProducts = computed(() => shelf.compareItems.value)

function beginComparison() {
  if (selectedProducts.value.length < 2) return
  router.push({ path: "/compare", query: { skus: selectedProducts.value.map((item) => item.sku).join(",") } })
}

function removeFromComparison(sku: string) {
  shelf.removeCompare(sku)
  if (skus.value.length >= 2) {
    const remaining = skus.value.filter((item) => item !== sku)
    router.replace(remaining.length >= 2 ? { path: "/compare", query: { skus: remaining.join(",") } } : { path: "/compare" })
  }
}

const SPEC_LABELS: Record<string, string> = {
  socket: "سوکت",
  memory_type: "نوع حافظه",
  cores: "هسته",
  threads: "رشته",
  tdp: "توان (وات)",
  wattage: "توان منبع (وات)",
  vram_gb: "حافظهٔ گرافیک (GB)",
  length_mm: "طول (میلی‌متر)",
  capacity_gb: "ظرفیت (GB)",
  speed_mhz: "سرعت (MHz)",
  recommended_psu: "منبع پیشنهادی (وات)",
  power_connectors: "کانکتور برق",
  memory_slots: "اسلات حافظه",
  max_memory_gb: "حداکثر حافظه",
  m2_slots: "اسلات M.2",
  form_factor: "فرمت",
  max_gpu_length_mm: "حداکثر طول گرافیک",
  max_cooler_height_mm: "حداکثر ارتفاع خنک‌کننده",
}

function label(key: string) {
  return SPEC_LABELS[key] ?? key
}

// --- measured frame rates ---------------------------------------------------
// `data.benchmarks` is a *flat* list of per-component measurements, so printing it
// row by row made a two-product comparison unreadable: nothing said which card a
// number belonged to. The table groups by game + resolution and gives every
// product its own column, with the quality preset and the test date attached.

const PRESET_LABELS: Record<string, string> = {
  low: "پایین",
  medium: "متوسط",
  high: "بالا",
  ultra: "حداکثر",
}

const RESOLUTION_ORDER = ["720p", "1080p", "1440p", "4k"]

interface FpsCell {
  avg_fps: number | null
  p1_low: number | null
}

interface FpsRow {
  key: string
  game: string
  resolution: string
  preset: string
  testedAt: string
  cells: Record<string, FpsCell>
}

const fpsNumber = new Intl.NumberFormat("fa-IR")

function formatFps(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—"
  return fpsNumber.format(value)
}

const fpsRows = computed<FpsRow[]>(() => {
  const groups = new Map<string, FpsRow>()
  for (const row of data.value?.benchmarks ?? []) {
    const key = `${row.game}|${row.resolution}`
    const entry: FpsRow = groups.get(key) ?? {
      key,
      game: row.game_fa || row.game,
      resolution: row.resolution,
      preset: row.preset ?? "",
      testedAt: row.tested_at ?? "",
      cells: {},
    }
    entry.cells[row.component] = { avg_fps: row.avg_fps, p1_low: row.p1_low }
    if (row.preset) entry.preset = row.preset
    if (row.tested_at && row.tested_at > entry.testedAt) entry.testedAt = row.tested_at
    groups.set(key, entry)
  }
  return [...groups.values()].sort((a, b) => {
    const byResolution =
      RESOLUTION_ORDER.indexOf(a.resolution) - RESOLUTION_ORDER.indexOf(b.resolution)
    return byResolution !== 0 ? byResolution : a.game.localeCompare(b.game, "fa")
  })
})

/** One column per compared product that actually has a measurement. */
const fpsColumns = computed(() => {
  const benchmarks = data.value?.benchmarks ?? []
  return (data.value?.products ?? [])
    .filter((product) => benchmarks.some((row) => row.component === product.entity_slug))
    .map((product) => ({ slug: product.entity_slug, title: product.display_title }))
})

// --- the frame-rate chart ---------------------------------------------------
// The same measurements as the table above, drawn as bars: one block per
// game + resolution, one bar per product. The chart is the at-a-glance view; the
// table below keeps the exact numbers (and the 1% low provenance). A part with no
// measured frame rate (a cooler, a case) simply has no bars — the section falls
// back to a plain "no measurement" note instead of an empty chart.
const chartSeries = computed(() => fpsColumns.value)

const chartGroups = computed(() =>
  fpsRows.value.map((row) => ({
    key: row.key,
    label: row.game,
    meta: [row.resolution, PRESET_LABELS[row.preset] ?? row.preset].filter(Boolean).join(" · "),
    bars: fpsColumns.value.map((column) => ({
      slug: column.slug,
      avg: row.cells[column.slug]?.avg_fps ?? null,
      low: row.cells[column.slug]?.p1_low ?? null,
    })),
  })),
)

useSeoMeta({
  title: "مقایسهٔ محصولات | تک‌بیس",
  description: "مقایسهٔ قیمت، موجودی، مشخصات و بنچمارک دو محصول.",
})
</script>

<template>
  <div>
    <h1 class="mb-1 text-2xl font-bold">مقایسهٔ محصولات</h1>
    <p class="mb-6 text-sm text-slate-500">
      قیمت، موجودی، مشخصات فنی و فریم‌ریت اندازه‌گیری‌شده — همه از دادهٔ فروشگاه.
    </p>

    <section v-if="skus.length < 2" class="rounded-xl border border-slate-200 bg-surface p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="font-semibold">محصول‌ها را برای مقایسه انتخاب کنید</h2>
          <p class="mt-1 text-sm text-slate-500">از کاتالوگ یا جست‌وجو «افزودن به مقایسه» را بزنید؛ انتخاب‌ها تا ۴ محصول در همین مرورگر می‌مانند.</p>
        </div>
        <button type="button" class="btn-primary" :disabled="selectedProducts.length < 2" @click="beginComparison">
          مقایسهٔ {{ selectedProducts.length }} محصول
        </button>
      </div>
      <ul v-if="selectedProducts.length" class="mt-4 divide-y divide-slate-100 rounded-lg border border-slate-200">
        <li v-for="product in selectedProducts" :key="product.sku" class="flex items-center justify-between gap-3 p-3">
          <div class="min-w-0">
            <NuxtLink :to="`/entity/${product.entity_slug}/`" class="truncate font-medium text-brand-700 hover:underline">{{ product.title }}</NuxtLink>
            <p class="text-sm text-slate-500">{{ formatPrice(product.price, product.currency) }}</p>
          </div>
          <button type="button" class="shrink-0 text-xs text-rose-700 hover:underline" @click="removeFromComparison(product.sku)">حذف</button>
        </li>
      </ul>
      <div v-else class="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center">
        <p class="text-sm text-slate-500">هنوز محصولی انتخاب نکرده‌اید.</p>
        <div class="mt-3 flex justify-center gap-3 text-sm">
          <NuxtLink to="/catalog" class="text-brand-700 underline">رفتن به کاتالوگ</NuxtLink>
          <NuxtLink to="/search" class="text-brand-700 underline">جست‌وجوی محصول</NuxtLink>
        </div>
      </div>
      <p v-if="selectedProducts.length === 1" class="mt-3 text-xs text-amber-700">برای شروع مقایسه یک محصول دیگر هم اضافه کنید.</p>
    </section>

    <p v-else-if="pending" class="py-8 text-center text-sm text-slate-500">در حال مقایسه…</p>

    <div v-else-if="error" class="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-700">
      <p>مقایسه انجام نشد.</p>
      <p class="mt-1 text-xs">ممکن است یکی از محصول‌ها دیگر در فروشگاه نباشد.</p>
      <button type="button" class="btn-secondary mt-3" @click="router.push('/compare')">
        انتخاب دوبارهٔ محصول‌ها
      </button>
    </div>

    <template v-else-if="data">
      <p
        v-if="droppedSkus.length"
        class="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-700"
      >
        این محصول‌ها دیگر در فروشگاه نیستند و از مقایسه حذف شدند:
        <span dir="ltr" class="font-medium">{{ droppedSkus.join(", ") }}</span>
      </p>

      <div class="mb-4 flex justify-end">
        <button type="button" class="text-sm text-brand-700 underline" @click="router.push('/compare')">ویرایش محصولات مقایسه</button>
      </div>
      <div class="mb-6 grid gap-3 sm:grid-cols-2">
        <div
          v-for="product in data.products"
          :key="product.sku"
          class="rounded-xl border border-slate-200 bg-surface p-4"
        >
          <h2 class="mb-1 font-semibold leading-snug">{{ product.display_title }}</h2>
          <p v-if="product.brand" class="text-xs text-slate-500">{{ product.brand }}</p>
          <p class="mt-2 text-lg font-bold">{{ formatPrice(product.price, product.currency) }}</p>
          <p class="text-xs" :class="product.in_stock ? 'text-emerald-600' : 'text-rose-500'">
            {{ product.in_stock ? `موجود (${product.stock})` : "ناموجود" }}
          </p>
          <p class="mt-1 text-xs text-slate-400">
            به‌روزرسانی: {{ formatDate(product.updated_at) }}
          </p>
        </div>
      </div>

      <section v-if="data.specs.length" class="mb-8">
        <h2 class="mb-3 text-lg font-semibold">مشخصات فنی</h2>
        <div class="overflow-x-auto rounded-xl border border-slate-200 bg-surface">
          <table class="w-full text-sm">
            <tbody>
              <tr
                v-for="row in data.specs"
                :key="row.key"
                class="border-b border-slate-100 last:border-0 even:bg-slate-50/60"
              >
                <th scope="row" class="w-1/3 px-4 py-2.5 text-start font-medium text-slate-600">
                  {{ label(row.key) }}
                </th>
                <td
                  v-for="(value, index) in row.values"
                  :key="index"
                  class="px-4 py-2.5 text-slate-900"
                  dir="ltr"
                >
                  {{ value ?? "—" }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

<!-- Frame rates: a chart for the glance, a table for the exact numbers. A part that
           produces no frames (a cooler, a case) has no benchmark and falls back to the
           note below — it is never shown as an empty chart. -->
<section v-if="fpsRows.length" class="mb-8">
        <div class="mb-3">
          <h2 class="text-lg font-semibold">فریمریت اندازه‌گیری‌شده</h2>
          <p class="mt-1 text-xs leading-6 text-slate-500">
            هر خانه دو عدد دارد: <span class="font-medium text-slate-700">میانگین</span> فریمریت و
            <span class="font-medium text-slate-700">۱٪ کمینه</span> (کندترین یک درصد فریم‌ها).
            هرچه این دو به هم نزدیک‌تر باشند، تجربه یکنواخت‌تر است. همهٔ اعداد بر حسب
            «فریم بر ثانیه» و برای همان رزولوشن و کیفیتی هستند که در ستون دوم آمده؛
            «—» یعنی برای آن محصول در آن بازی اندازه‌گیری ثبت نشده است.
          </p>
        </div>
        <!-- The at-a-glance view: the same numbers as the table, drawn as bars. -->
        <FpsChart class="mb-4" :series="chartSeries" :groups="chartGroups" />

        <div class="overflow-x-auto rounded-xl border border-slate-200 bg-surface">
          <table class="w-full text-sm">
            <caption class="sr-only">
              میانگین و ۱٪ کمینهٔ فریمریت هر محصول، به تفکیک بازی، رزولوشن و کیفیت
            </caption>
            <thead class="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th scope="col" class="px-4 py-2 text-start font-medium">بازی</th>
                <th scope="col" class="px-4 py-2 text-start font-medium">رزولوشن و کیفیت</th>
                <th
                  v-for="column in fpsColumns"
                  :key="column.slug"
                  scope="col"
                  class="px-4 py-2 text-start font-medium"
                >
                  <span class="block max-w-56 truncate text-slate-700" :title="column.title">
                    {{ column.title }}
                  </span>
                  <span class="mt-0.5 block text-[10px] font-normal text-slate-400">
                    میانگین · ۱٪ کمینه
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in fpsRows" :key="row.key" class="border-t border-slate-100">
                <th scope="row" class="px-4 py-2 text-start font-medium text-slate-700">
                  {{ row.game }}
                </th>
                <td class="px-4 py-2 text-slate-600">
                  <span dir="ltr" class="font-medium">{{ row.resolution }}</span>
                  <span v-if="row.preset" class="ms-1 text-xs">
                    · {{ PRESET_LABELS[row.preset] ?? row.preset }}
                  </span>
                  <span v-if="row.testedAt" class="mt-0.5 block text-[10px] text-slate-400">
                    آزمون: {{ formatDate(row.testedAt) }}
                  </span>
                </td>
                <td
                  v-for="column in fpsColumns"
                  :key="column.slug"
                  class="whitespace-nowrap px-4 py-2"
                >
                  <template v-if="row.cells[column.slug]">
                    <span class="font-semibold text-slate-900">
                      {{ formatFps(row.cells[column.slug]?.avg_fps) }}
                    </span>
                    <span class="text-slate-400"> · </span>
                    <span class="text-xs text-slate-500">
                      {{ formatFps(row.cells[column.slug]?.p1_low) }}
                    </span>
                  </template>
                  <span v-else class="text-slate-300">—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="mt-2 text-[11px] text-slate-400">
          واحد: فریم بر ثانیه (FPS). اعداد از جدول بنچمارک فروشگاه خوانده می‌شوند، نه از حافظهٔ مدل.
        </p>
      </section>
      <p
        v-else
        class="mb-8 rounded-xl border border-dashed border-slate-300 bg-surface p-5 text-sm leading-6 text-slate-500"
      >
        برای این محصولها بنچمارک فریمریت اندازهگیریشده ثبت نشده است — برای نمونه، خنککننده،
        کیس و منبع تغذیه فریم تولید نمیکنند و بنچمارک بازی ندارند. مقایسهٔ قیمت، موجودی و
        مشخصات فنی در بالای همین صفحه انجام شده است.
      </p>
    </template>
  </div>
</template>
