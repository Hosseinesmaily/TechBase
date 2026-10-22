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

const skus = computed(() => {
  const raw = route.query.skus
  if (typeof raw === "string") return raw.split(",").filter(Boolean)
  if (Array.isArray(raw)) return raw.filter(Boolean)
  return []
})

const { data, pending, error } = await useAsyncData<CompareResponse>(
  "compare",
  () =>
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

    <p v-if="skus.length < 2" class="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-500">
      برای مقایسه، دست‌کم دو محصول لازم است. آدرس را به شکل
      <code dir="ltr">/compare/?skus=sku-a,sku-b</code> بدهید.
    </p>

    <p v-else-if="pending" class="py-8 text-center text-sm text-slate-500">در حال مقایسه…</p>

    <div v-else-if="error" class="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">
      مقایسه ممکن نشد.
    </div>

    <template v-else-if="data">
      <div class="mb-6 grid gap-3 sm:grid-cols-2">
        <div
          v-for="product in data.products"
          :key="product.sku"
          class="rounded-xl border border-slate-200 bg-white p-4"
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
        <div class="overflow-x-auto rounded-xl border border-slate-200 bg-white">
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
        <div class="overflow-x-auto rounded-xl border border-slate-200 bg-white">
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
