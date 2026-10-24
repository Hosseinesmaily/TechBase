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
    avg_fps: number
    p1_low: number | null
  }[]
}

const route = useRoute()
const router = useRouter()
const shelf = useCustomerShelf()

const skus = computed(() => {
  const raw = route.query.skus
  if (typeof raw === "string") return raw.split(",").filter(Boolean)
  if (Array.isArray(raw)) return raw.filter(Boolean)
  return []
})

const { data, pending, error } = await useAsyncData<CompareResponse>(
  "compare",
  () => skus.value.length < 2 ? Promise.resolve({ products: [], specs: [], benchmarks: [] }) :
    $fetch<CompareResponse>("/api/v1/ai/compare/", {
      method: "POST",
      body: { skus: skus.value },
    }),
  {
    server: true,
    watch: [skus],
    default: () => ({ products: [], specs: [], benchmarks: [] }),
  },
)

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
        <button type="button" class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50" :disabled="selectedProducts.length < 2" @click="beginComparison">
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

    <div v-else-if="error" class="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">
      مقایسه ممکن نشد.
    </div>

    <template v-else-if="data">
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

      <section v-if="data.benchmarks.length">
        <h2 class="mb-3 text-lg font-semibold">فریم‌ریت اندازه‌گیری‌شده</h2>
        <div class="overflow-x-auto rounded-xl border border-slate-200 bg-surface">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 text-xs text-slate-500">
              <tr>
                <th class="px-4 py-2 text-start font-medium">بازی</th>
                <th class="px-4 py-2 text-start font-medium">رزولوشن</th>
                <th class="px-4 py-2 text-start font-medium">میانگین</th>
                <th class="px-4 py-2 text-start font-medium">۱٪ پایین</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in data.benchmarks" :key="`${row.component}-${row.game}-${row.resolution}`" class="border-t border-slate-100">
                <td class="px-4 py-2">{{ row.game_fa || row.game }}</td>
                <td class="px-4 py-2" dir="ltr">{{ row.resolution }}</td>
                <td class="px-4 py-2 font-medium" dir="ltr">{{ row.avg_fps }} fps</td>
                <td class="px-4 py-2 text-slate-500" dir="ltr">{{ row.p1_low ?? "—" }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
