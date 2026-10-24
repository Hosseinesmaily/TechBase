<script setup lang="ts">
import type { Product } from "~/types/catalog"
import { formatPrice } from "~/utils/format"
import type { ProductSnapshot } from "~/composables/useCustomerShelf"

interface CompatibilityFinding {
  rule_code: string
  severity: "block" | "warn" | "info"
  message: string
  message_fa: string
  a: { slug: string; title: string }
  b: { slug: string; title: string }
}

interface CompatibilityReport {
  verdict: "ok" | "warn" | "block"
  findings: CompatibilityFinding[]
  checked: string[]
}

const steps = [
  { slug: "cpu", label: "پردازنده" },
  { slug: "motherboard", label: "مادربرد" },
  { slug: "ram", label: "حافظه" },
  { slug: "gpu", label: "کارت گرافیک" },
  { slug: "psu", label: "منبع تغذیه" },
  { slug: "case", label: "کیس" },
  { slug: "cooler", label: "خنک‌کننده" },
  { slug: "storage", label: "ذخیره‌سازی" },
] as const

useSeoMeta({
  title: "اسمبل سیستم | تک‌بیس",
  description: "قطعات سیستم را انتخاب کنید و سازگاری آن‌ها را بررسی کنید.",
})

const stepIndex = ref(0)
const selected = ref<Record<string, Product>>({})
const parts = ref<Product[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const compatibilityReport = ref<CompatibilityReport | null>(null)
const buildName = ref("سیستم گیمینگ من")
const shelf = useCustomerShelf()

const step = computed(() => steps[stepIndex.value]!)
const chosenForStep = computed(() => selected.value[step.value.slug])
const selectedProducts = computed(() => Object.values(selected.value))
const totalPrice = computed(() =>
  selectedProducts.value.reduce((sum, product) => sum + Number(product.price), 0),
)
const allPartsSelected = computed(() => steps.every(({ slug }) => selected.value[slug]))
const blockingFindings = computed(
  () => compatibilityReport.value?.findings.filter((finding) => finding.severity === "block") ?? [],
)
const canSaveBuild = computed(
  () => allPartsSelected.value && compatibilityReport.value && compatibilityReport.value.verdict !== "block",
)

function productSnapshot(product: Product): ProductSnapshot {
  return {
    sku: product.sku,
    title: product.display_title,
    price: product.price,
    currency: product.currency,
    entity_type: product.entity_type,
    entity_slug: product.entity_slug,
    in_stock: product.in_stock,
    updated_at: product.price_updated_at ?? product.updated_at,
  }
}

function saveCurrentBuild() {
  shelf.saveBuild(buildName.value, selectedProducts.value.map(productSnapshot))
}

async function loadParts() {
  loading.value = true
  error.value = null
  try {
    const response = await $fetch<{ results: Product[] }>("/api/v1/catalog/products/", {
      query: { category: step.value.slug, page_size: 50 },
    })
    parts.value = response.results
  } catch {
    error.value = "بارگذاری کالاها ناموفق بود. مطمئن شوید بک‌اند در حال اجراست."
    parts.value = []
  } finally {
    loading.value = false
  }
}

async function checkCompatibility() {
  try {
    compatibilityReport.value = await $fetch<CompatibilityReport>("/api/v1/compat/check/", {
      method: "POST",
      body: { parts: selectedProducts.value.map((product) => product.entity_slug) },
    })
  } catch {
    error.value = "بررسی سازگاری انجام نشد. دوباره تلاش کنید."
  }
}

async function selectProduct(product: Product) {
  selected.value[step.value.slug] = product
  compatibilityReport.value = null
  if (stepIndex.value < steps.length - 1) {
    stepIndex.value++
    await loadParts()
  } else {
    await checkCompatibility()
  }
}

async function goBack() {
  if (stepIndex.value === 0) return
  stepIndex.value--
  await loadParts()
}

function reset() {
  stepIndex.value = 0
  selected.value = {}
  parts.value = []
  error.value = null
  compatibilityReport.value = null
  void loadParts()
}

onMounted(loadParts)
</script>

<template>
  <div class="mx-auto max-w-6xl py-8">
    <h1 class="mb-1 text-2xl font-bold">اسمبل سیستم</h1>
    <p class="mb-6 text-sm text-slate-500">
      قطعات را انتخاب کنید؛ سازگاری با قوانین قطعی سیستم بررسی می‌شود.
    </p>

    <ol class="mb-6 flex flex-wrap items-center gap-2 text-xs text-slate-500">
      <li v-for="(item, index) in steps" :key="item.slug" class="flex items-center gap-2">
        <span
          class="rounded-full px-2 py-1"
          :class="index === stepIndex ? 'bg-brand-100 text-brand-700' : index < stepIndex ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'"
        >{{ index + 1 }}. {{ item.label }}</span>
      </li>
    </ol>

    <section class="rounded-xl border border-slate-200 bg-surface p-6">
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold">انتخاب {{ step.label }}</h2>
        <span v-if="chosenForStep" class="text-sm text-emerald-700">{{ chosenForStep.display_title }}</span>
      </div>

      <p v-if="loading" class="py-8 text-center text-sm text-slate-500">در حال بارگذاری…</p>
      <p v-else-if="error" class="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">{{ error }}</p>
      <div v-else-if="parts.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <button
          v-for="product in parts"
          :key="product.sku"
          type="button"
          class="rounded-xl text-start focus:outline-none focus:ring-2 focus:ring-brand-500"
          @click="selectProduct(product)"
        >
          <ProductCard :product="product" :show-actions="false" />
        </button>
      </div>
      <p v-else class="py-8 text-center text-sm text-slate-500">برای این دسته محصولی پیدا نشد.</p>
    </section>

    <div class="mt-4 flex justify-between">
      <button
        v-if="stepIndex > 0"
        type="button"
        class="rounded-lg border border-slate-300 px-4 py-2 text-sm"
        @click="goBack"
      >قبلی</button>
      <span v-else />
      <button v-if="allPartsSelected" type="button" class="text-sm text-brand-700" @click="checkCompatibility">
        بررسی دوبارهٔ سازگاری
      </button>
    </div>

    <section v-if="allPartsSelected" class="mt-8 rounded-xl border border-slate-200 bg-surface p-6">
      <h2 class="mb-3 text-lg font-bold">خلاصهٔ سیستم</h2>
      <ul class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="item in steps" :key="item.slug" class="rounded-lg border p-3">
          <p class="text-xs text-slate-500">{{ item.label }}</p>
          <p class="font-medium">{{ selected[item.slug]?.display_title }}</p>
          <p class="mt-1 text-sm">{{ formatPrice(selected[item.slug]?.price) }}</p>
        </li>
      </ul>
      <p class="mt-4 font-bold">جمع قیمت: {{ formatPrice(totalPrice) }}</p>

      <p v-if="compatibilityReport" class="mt-4 text-sm" :class="compatibilityReport.verdict === 'block' ? 'text-rose-700' : 'text-emerald-700'">
        {{ compatibilityReport.verdict === 'block' ? 'ناسازگاری پیدا شد' : compatibilityReport.verdict === 'warn' ? 'سازگار با موارد قابل توجه' : 'قطعات سازگار هستند' }}
      </p>
      <ul v-if="blockingFindings.length" class="mt-2 list-inside list-disc text-sm text-rose-700">
        <li v-for="(finding, index) in blockingFindings" :key="`${finding.rule_code}-${index}`">{{ finding.message_fa || finding.message }}</li>
      </ul>
      <p v-if="compatibilityReport?.verdict === 'ok'" class="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
        همهٔ بررسی‌های قطعی سازگاری موفق بودند؛ می‌توانی این سیستم را در پنل شخصی ذخیره کنی.
      </p>
      <div class="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
        <label class="flex-1 text-sm text-slate-500">
          نام سیستم ذخیره‌شده
          <input v-model="buildName" class="mt-1 w-full rounded-lg border border-slate-300 bg-surface px-3 py-2 text-slate-900" maxlength="80" />
        </label>
        <button
          v-if="canSaveBuild"
          type="button"
          class="rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-brand-500"
          @click="saveCurrentBuild"
        >ذخیره در پنل من</button>
        <button type="button" class="rounded-xl border border-slate-300 px-5 py-3 text-sm" @click="reset">
          شروع دوباره
        </button>
      </div>
    </section>
  </div>
</template>
