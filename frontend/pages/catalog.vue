<script setup lang="ts">
import type { Brand, Paginated, Product } from "~/types/catalog"

useSeoMeta({
  title: "کاتالوگ محصولات | تک‌بیس",
  description: "فهرست محصولات، قیمت و موجودی — با آخرین به‌روزرسانی.",
})

const TYPE_OPTIONS = [
  { value: "", label: "همهٔ انواع" },
  { value: "prebuilt", label: "سیستم آماده" },
  { value: "gpu", label: "کارت گرافیک" },
  { value: "cpu", label: "پردازنده" },
  { value: "motherboard", label: "مادربرد" },
  { value: "ram", label: "حافظه" },
  { value: "psu", label: "منبع تغذیه" },
  { value: "case", label: "کیس" },
  { value: "cooler", label: "خنک‌کننده" },
  { value: "storage", label: "ذخیره‌سازی" },
]

const route = useRoute()

// Filters live in the URL so a filtered catalog is shareable and SSR-renders
// the same view the server sees.
const type = ref(String(route.query.category ?? ""))
const brand = ref(String(route.query.brand ?? ""))
const inStockOnly = ref(route.query.in_stock === "true")
const maxPrice = ref(route.query.max_price ? Number(route.query.max_price) : null)
const page = ref(Number(route.query.page ?? 1))

const { data: brands } = await useFetch<Brand[]>("/api/v1/catalog/brands/", {
  server: true,
  default: () => [],
})

const query = computed(() => ({
  ...(type.value ? { category: type.value } : {}),
  ...(brand.value ? { brand: brand.value } : {}),
  ...(inStockOnly.value ? { in_stock: "true" } : {}),
  ...(maxPrice.value ? { max_price: String(maxPrice.value) } : {}),
  page: String(page.value),
  page_size: "24",
}))

const { data: products, pending, error } = await useFetch<Paginated<Product>>(
  "/api/v1/catalog/products/",
  {
    server: true,
    query,
    // The filter set is the cache key, so changing a filter re-fetches.
    key: "catalog-products",
    watch: [query],
    default: () => ({ count: 0, next: null, previous: null, results: [] }),
  },
)

// Keep the URL in sync with the filters (without reloading the page).
watch(
  [type, brand, inStockOnly, maxPrice, page],
  () => {
    const next: Record<string, string> = {}
    if (type.value) next.category = type.value
    if (brand.value) next.brand = brand.value
    if (inStockOnly.value) next.in_stock = "true"
    if (maxPrice.value) next.max_price = String(maxPrice.value)
    if (page.value > 1) next.page = String(page.value)
    navigateTo({ path: "/catalog", query: next }, { replace: true })
  },
)

watch([type, brand, inStockOnly, maxPrice], () => {
  page.value = 1
})

const totalPages = computed(() => {
  const count = products.value?.count ?? 0
  return Math.max(1, Math.ceil(count / 24))
})
</script>

<template>
  <div>
    <h1 class="mb-1 text-2xl font-bold">کاتالوگ محصولات</h1>
    <p class="mb-6 text-sm text-slate-500">
      قیمت و موجودی مستقیماً از انبار فروشگاه — هر کارت تاریخ به‌روزرسانی را نشان می‌دهد.
    </p>

    <div class="mb-6 grid gap-3 rounded-xl border border-slate-200 bg-surface p-4 sm:grid-cols-4">
      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-600">نوع</span>
        <select
          v-model="type"
          class="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option v-for="opt in TYPE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>

      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-600">برند</span>
        <select
          v-model="brand"
          class="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
        >
          <option value="">همهٔ برندها</option>
          <option v-for="b in brands ?? []" :key="b.slug" :value="b.slug">
            {{ b.name_fa || b.name }}
          </option>
        </select>
      </label>

      <label class="block">
        <span class="mb-1 block text-xs font-medium text-slate-600">حداکثر قیمت (تومان)</span>
        <input
          v-model.number="maxPrice"
          type="number"
          step="1000000"
          min="0"
          placeholder="مثلاً ۴۰۰۰۰۰۰۰"
          class="w-full rounded-lg border border-slate-300 px-2 py-1.5 text-sm"
        />
      </label>

      <label class="flex items-end gap-2 pb-1.5">
        <input v-model="inStockOnly" type="checkbox" class="h-4 w-4 rounded" />
        <span class="text-sm">فقط کالاهای موجود</span>
      </label>
    </div>

    <p v-if="pending" class="py-8 text-center text-sm text-slate-500">در حال بارگذاری…</p>

    <div v-else-if="error" class="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">
      خطا در دریافت اطلاعات کاتالوگ. مطمئن شوید سرویس API در حال اجراست.
    </div>

    <template v-else>
      <p class="mb-3 text-sm text-slate-500">
        {{ products?.count ?? 0 }} کالا
      </p>

      <div
        v-if="products && products.results.length > 0"
        class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      >
        <ProductCard v-for="product in products.results" :key="product.id" :product="product" />
      </div>

      <p
        v-else
        class="rounded-lg border border-dashed border-slate-300 py-10 text-center text-slate-500"
      >
        کالایی با این فیلترها پیدا نشد.
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
