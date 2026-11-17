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

/** One card's verdict, as returned by the deterministic rule engine. */
interface CandidateResult {
  verdict: "ok" | "warn" | "block" | "unknown"
  findings: CompatibilityFinding[]
  has_specs: boolean
  checked_rules: number
  known: boolean
  /** Why a verdict could not be reached yet (empty when it could). */
  reason?: string
}

type CardState = "unchecked" | "compatible" | "warning" | "incompatible" | "unknown"
type StepState = "active" | "done" | "todo" | "error"

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

/**
 * Every card state carries a word, not only a colour: the halo is a hint and the
 * badge text is the statement, so a verdict stays readable without colour vision.
 */
const CARD_STATES: Record<CardState, { label: string; frame: string; badge: string; hint?: string }> = {
  compatible: {
    label: "سازگار",
    frame: "border-emerald-500/40 shadow-[0_0_0_3px_rgba(52,211,153,0.12)]",
    badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
    hint: "با قطعه‌های انتخاب‌شده سازگار است.",
  },
  warning: {
    label: "سازگار، با نکته",
    frame: "border-amber-500/40 shadow-[0_0_0_3px_rgba(251,191,36,0.12)]",
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-300",
    hint: "سازگار است، اما نکتهٔ قابل توجهی دارد؛ برای دیدن دلیل نشانگر را روی همین کارت نگه دار.",
  },
  incompatible: {
    label: "ناسازگار",
    frame: "border-rose-500/50 shadow-[0_0_0_3px_rgba(244,63,94,0.14)]",
    badge: "border-rose-500/50 bg-rose-500/10 text-rose-300",
    hint: "با قطعه‌های انتخاب‌شده ناسازگار است؛ برای دیدن دلیل نشانگر را روی همین کارت نگه دار.",
  },
  unknown: {
    label: "نامشخص",
    frame: "border-slate-500/40",
    badge: "border-slate-500/40 bg-slate-500/10 text-slate-400",
    hint: "برای مقایسهٔ این قطعه با انتخاب‌های فعلی، مشخصات کافی در کاتالوگ ثبت نشده است.",
  },
  unchecked: {
    label: "نامشخص",
    frame: "border-slate-200",
    badge: "border-slate-200 bg-surface text-slate-500",
    hint: "هنوز قطعه‌ای برای مقایسه انتخاب نشده است.",
  },
}

const stepIndex = ref(0)
const selected = ref<Record<string, Product>>({})
const parts = ref<Product[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const report = ref<CompatibilityReport | null>(null)
const candidateResults = ref<Record<string, CandidateResult>>({})
const evaluating = ref(false)
const evaluateError = ref("")
/**
 * Verdicts already computed, under a key that contains *every* selection able to
 * change the answer. A different motherboard is a different key, so a stale
 * verdict can never be shown for a new selection.
 */
const verdictCache = ref<Record<string, Record<string, CandidateResult>>>({})
const buildName = ref("سیستم گیمینگ من")
const shelf = useCustomerShelf()
const account = useAccount()

useSeoMeta({
  title: "اسمبل سیستم | تک‌بیس",
  description: "قطعات سیستم را مرحله‌به‌مرحله انتخاب کنید و سازگاری آن‌ها را با قوانین قطعی بسنجید.",
})

const step = computed(() => steps[stepIndex.value]!)
const chosenForStep = computed(() => selected.value[step.value.slug])
const selectedProducts = computed(() => Object.values(selected.value))
const totalPrice = computed(() =>
  selectedProducts.value.reduce((sum, product) => sum + Number(product.price), 0),
)
const allPartsSelected = computed(() => steps.every(({ slug }) => selected.value[slug]))

/**
 * The parts a candidate is checked *against*: everything chosen for the other
 * steps. The current step's own selection is excluded, otherwise re-picking a part
 * would be compared with the very part it is replacing.
 */
const baseSlugs = computed(() =>
  steps
    .filter(({ slug }) => slug !== step.value.slug && selected.value[slug])
    .map(({ slug }) => selected.value[slug]!.entity_slug),
)

/**
 * Every option stays visible, each carrying its own verdict. Filtering the list
 * down to the compatible parts would hide exactly the cards whose reason the
 * customer has to read, so the status is shown instead of hidden.
 */
const visibleParts = computed(() => parts.value)
const compatibleCount = computed(
  () =>
    parts.value.filter((product) => ["compatible", "warning"].includes(cardState(product))).length,
)
const incompatibleCount = computed(
  () => parts.value.filter((product) => cardState(product) === "incompatible").length,
)
const blockingFindings = computed(
  () => report.value?.findings.filter((finding) => finding.severity === "block") ?? [],
)
const canSaveBuild = computed(
  () => allPartsSelected.value && report.value !== null && report.value.verdict !== "block",
)

/** What the part chosen for this step conflicts with — named, never hidden. */
const chosenConflicts = computed(() => {
  const product = chosenForStep.value
  if (!product || !report.value) return []
  return report.value.findings
    .filter((finding) => [finding.a.slug, finding.b.slug].includes(product.entity_slug))
    .map((finding) => ({
      code: finding.rule_code,
      severity: finding.severity,
      text: finding.message_fa || finding.message,
      other: finding.a.slug === product.entity_slug ? finding.b : finding.a,
    }))
})
function cardState(product: Product): CardState {
  if (!baseSlugs.value.length) return "unchecked"
  const result = candidateResults.value[product.entity_slug]
  if (!result || !result.known || !result.has_specs) return "unknown"
  if (result.verdict === "block") return "incompatible"
  if (result.verdict === "warn") return "warning"
  // No rule could compare anything yet: that is not the same statement as "compatible".
  if (result.checked_rules === 0) return "unknown"
  return "compatible"
}

function cardReason(product: Product): string {
  const finding = candidateResults.value[product.entity_slug]?.findings?.[0]
  return finding ? finding.message_fa || finding.message : ""
}

/**
 * The text a card shows: the blocking reason when there is one, the engine's own
 * explanation when a verdict could not be reached yet, otherwise the state's
 * generic hint. So "not determined" always names what is missing instead of a
 * vague "not enough data" — and it is never dressed up as compatible.
 */
function cardHint(product: Product): string {
  const state = cardState(product)
  const reason = candidateResults.value[product.entity_slug]?.reason
  if (state === "unknown" && reason) return reason
  return cardReason(product) || CARD_STATES[state].hint || ""
}

function stepState(index: number): StepState {
  if (index === stepIndex.value) return "active"
  const product = selected.value[steps[index]!.slug]
  if (!product) return "todo"
  const blocked = report.value?.findings.some(
    (finding) =>
      finding.severity === "block" &&
      [finding.a.slug, finding.b.slug].includes(product.entity_slug),
  )
  return blocked ? "error" : "done"
}

function stepClass(index: number): string {
  switch (stepState(index)) {
    case "active":
      return "border-brand-600 bg-brand-600 text-white"
    case "done":
      return "border-emerald-500/50 bg-emerald-500/10 text-emerald-300"
    case "error":
      return "border-rose-500/50 bg-rose-500/10 text-rose-300"
    default:
      return "border-slate-200 bg-surface text-slate-500"
  }
}

function stepMark(index: number): string {
  switch (stepState(index)) {
    case "active":
      return "◗"
    case "done":
      return "✓"
    case "error":
      return "!"
    default:
      return String(index + 1)
  }
}

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

/** The parts a step is checked against, as a stable signature (order-free). */
function selectionSignature(excludedStep: string): string {
  return steps
    .filter(({ slug }) => slug !== excludedStep && selected.value[slug])
    .map(({ slug }) => `${slug}:${selected.value[slug]!.entity_slug}`)
    .sort()
    .join("|")
}

/**
 * Ask the deterministic engine to badge every option of the step on screen.
 *
 * One code path for all eight steps: the parts chosen in the *other* steps are
 * sent as `parts`, and every option of this step is a `candidate`. The answer is
 * keyed by the identifier the API echoes back (`entity_slug`), so the mapping is
 * by identity and never by the response order. A step with nothing to compare
 * against is not sent at all, and its cards stay neutral.
 */
async function evaluateStep(): Promise<Record<string, CandidateResult>> {
  const stepSlug = step.value.slug
  const base = baseSlugs.value
  if (!base.length || !parts.value.length) return {}

  // The cache key carries the whole effective selection, so changing an earlier
  // part produces a miss instead of an old verdict.
  const cacheKey = `${stepSlug}::${selectionSignature(stepSlug)}`
  const cached = verdictCache.value[cacheKey]
  if (cached) return cached

  const candidates = [...new Set(parts.value.map((product) => product.entity_slug))]
  evaluating.value = true
  evaluateError.value = ""
  try {
    // Two attempts: a single blip (a restarting backend, a dropped connection)
    // must not blank every card and leave the page looking broken.
    let lastError: unknown = null
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        // `account.request` sends the CSRF token. Without it every card turned
        // "not determined" the moment a visitor signed in: DRF enforces CSRF for
        // an authenticated POST, and a plain `$fetch` carried no token.
        const response = await account.request<{ candidate_results?: Record<string, CandidateResult> }>(
          "/api/v1/compat/check/",
          { method: "POST", body: JSON.stringify({ parts: base, candidates }) },
        )
        const results = response.candidate_results ?? {}
        verdictCache.value[cacheKey] = results
        return results
      } catch (cause) {
        lastError = cause
      }
    }
    throw lastError
  } catch {
    // Still nothing after the retry: stay neutral and offer the manual retry —
    // an unknown state is never dressed up as "compatible".
    evaluateError.value = "بررسی سازگاری انجام نشد."
    return {}
  } finally {
    evaluating.value = false
  }
}

/** Re-badge the step that is on screen. */
async function refreshVerdicts() {
  candidateResults.value = await evaluateStep()
}

async function loadParts() {
  loading.value = true
  error.value = null
  candidateResults.value = {}
  evaluateError.value = ""
  try {
    const response = await $fetch<{ results: Product[] }>("/api/v1/catalog/products/", {
      query: { category: step.value.slug, page_size: 40 },
    })
    parts.value = response.results
    await refreshVerdicts()
  } catch {
    error.value = "بارگذاری کالاها ناموفق بود. ارتباط با سرور برقرار نشد."
    parts.value = []
  } finally {
    loading.value = false
  }
}

async function checkCompatibility() {
  const slugs = selectedProducts.value.map((product) => product.entity_slug)
  if (slugs.length < 2) {
    report.value = null
    return
  }
  try {
    report.value = await account.request<CompatibilityReport>("/api/v1/compat/check/", {
      method: "POST",
      body: JSON.stringify({ parts: slugs }),
    })
  } catch {
    report.value = null
    error.value = "بررسی سازگاری انجام نشد. دوباره تلاش کنید."
  }
}

async function goToStep(index: number) {
  if (index < 0 || index >= steps.length || index === stepIndex.value) return
  stepIndex.value = index
  await loadParts()
}

async function selectProduct(product: Product) {
  // A new pick never deletes another step's choice: any conflict is reported instead.
  selected.value[step.value.slug] = product
  await checkCompatibility()
  if (stepIndex.value < steps.length - 1) {
    stepIndex.value += 1
    await loadParts()
  } else {
    // The last step stays on screen; its badges still come from the engine.
    await refreshVerdicts()
  }
}

function reset() {
  stepIndex.value = 0
  selected.value = {}
  parts.value = []
  error.value = null
  report.value = null
  candidateResults.value = {}
  verdictCache.value = {}
  evaluateError.value = ""
  void loadParts()
}

onMounted(loadParts)
</script>

<template>
  <div class="mx-auto max-w-6xl py-8">
    <h1 class="mb-1 text-2xl font-bold">اسمبل سیستم</h1>
    <p class="mb-6 text-sm text-slate-500">
      قطعات را انتخاب کنید؛ سازگاری با قوانین قطعی سیستم بررسی می‌شود و دلیل هر ناسازگاری کنار همان قطعه می‌آید.
    </p>

    <ol
      class="-mx-1 mb-2 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible"
      aria-label="مراحل انتخاب قطعات"
    >
      <li v-for="(item, index) in steps" :key="item.slug" class="shrink-0">
        <button
          type="button"
          class="inline-flex min-h-10 items-center gap-2 rounded-full border px-3 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          :class="stepClass(index)"
          :aria-current="index === stepIndex ? 'step' : undefined"
          :aria-label="`مرحلهٔ ${index + 1}: ${item.label}`"
          @click="goToStep(index)"
        >
          <span aria-hidden="true">{{ stepMark(index) }}</span>
          {{ item.label }}
        </button>
      </li>
    </ol>

    <p class="mb-6 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
      <span>◗ مرحلهٔ جاری</span>
      <span>✓ انتخاب‌شده</span>
      <span>! ناسازگاری با قطعات دیگر</span>
    </p>

    <section class="rounded-xl border border-slate-200 bg-surface p-4 sm:p-6">
      <div class="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-semibold">انتخاب {{ step.label }}</h2>
          <p class="mt-1 text-sm text-slate-500">
            <template v-if="!baseSlugs.length">برای بررسی سازگاری، ابتدا قطعه‌های مراحل دیگر را انتخاب کنید.</template>
            <template v-else>{{ compatibleCount }} گزینه از {{ parts.length }} گزینه با انتخاب‌های فعلی سازگار است. گزینه‌های ناسازگار با لبهٔ قرمز مشخص شده‌اند.</template>
          </p>
        </div>
        <div class="flex flex-wrap items-center gap-3 text-xs">
          <span v-if="chosenForStep" class="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-emerald-300">
            انتخاب‌شده: {{ chosenForStep.display_title }}
          </span>
        </div>
      </div>

      <!--
        A conflicting selection is reported, never silently dropped: the user can
        still change this part or the part it clashes with.
      -->
      <div
        v-if="chosenConflicts.length"
        class="mb-4 rounded-lg border border-rose-500/40 bg-rose-500/10 p-3"
      >
        <p class="text-sm font-semibold text-rose-300">انتخاب فعلی با قطعهٔ دیگری ناسازگار است</p>
        <ul class="mt-1 list-inside list-disc text-xs leading-6 text-rose-200">
          <li v-for="conflict in chosenConflicts" :key="`${conflict.code}-${conflict.other.slug}`">
            {{ conflict.text }}
            <span class="opacity-80">— {{ conflict.other.title }}</span>
          </li>
        </ul>
        <p class="mt-2 text-xs leading-6 text-rose-200">
          می‌توانی این قطعه را عوض کنی یا قطعهٔ ناسازگار را در مرحلهٔ خودش تغییر دهی؛ هیچ
          انتخابی خودکار حذف نمی‌شود.
        </p>
      </div>

      <p
        v-if="evaluating && !loading"
        class="mb-3 text-xs text-slate-400"
        role="status"
        aria-live="polite"
      >
        در حال بررسی سازگاری گزینه‌ها...
      </p>
      <p v-if="evaluateError" class="mb-3 flex flex-wrap items-center gap-2 text-xs text-rose-300">
        {{ evaluateError }}
        <button
          type="button"
          class="rounded-lg border border-rose-500/40 px-2 py-1 text-rose-200 transition-colors hover:bg-rose-500/10"
          @click="refreshVerdicts"
        >
          تلاش مجدد
        </button>
      </p>

      <p v-if="loading" class="py-8 text-center text-sm text-slate-500" role="status" aria-live="polite">
        در حال بارگذاری و بررسی سازگاری...
      </p>

      <ApiErrorNotice
        v-else-if="error"
        title="بارگذاری قطعات ناموفق بود"
        :message="error"
        @retry="loadParts"
      />

      <template v-else>
        <div v-if="visibleParts.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <button
            v-for="product in visibleParts"
            :key="product.sku"
            type="button"
            class="flex flex-col rounded-xl text-start focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            @click="selectProduct(product)"
          >
            <div
              class="overflow-hidden rounded-xl border p-1 transition-colors"
              :class="CARD_STATES[cardState(product)].frame"
              :title="cardHint(product)"
            >
              <ProductCard :product="product" :show-actions="false" :link-to-wiki="false" />
              <!--
                An incompatible option is marked by its red edge and nothing else —
                that is exactly what the brief asked for. The reason is still
                available (on hover and to a screen reader), so the colour is not
                the only carrier of the verdict.
              -->
              <p
                v-if="cardState(product) !== 'incompatible'"
                class="mx-3 mb-2 inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium"
                :class="CARD_STATES[cardState(product)].badge"
              >
                {{ CARD_STATES[cardState(product)].label }}
              </p>
              <!-- Not determined: say exactly which part is still missing. -->
              <p
                v-if="cardState(product) === 'unknown'"
                class="mx-3 mb-3 text-[11px] leading-5 text-slate-400"
              >
                {{ cardHint(product) }}
              </p>
              <span v-else class="sr-only">
                {{ CARD_STATES.incompatible.label }}<template v-if="cardReason(product)"> — {{ cardReason(product) }}</template>
              </span>
              <p v-if="chosenForStep?.sku === product.sku" class="mx-3 mb-3 text-xs font-semibold text-emerald-300">
                این قطعه انتخاب شده است.
              </p>
            </div>
          </button>
        </div>

        <div
          v-else
          class="rounded-lg border border-dashed border-slate-300 py-10 text-center text-slate-500"
        >
          <p>برای این دسته محصولی در کاتالوگ ثبت نشده است.</p>
        </div>
      </template>

      <div
        v-if="chosenConflicts.length"
        class="mt-5 rounded-lg border border-rose-500/40 bg-rose-500/10 p-4"
        role="alert"
      >
        <p class="text-sm font-semibold text-rose-300">این انتخاب با قطعه‌های دیگر شما ناسازگار است</p>
        <ul class="mt-2 space-y-1 text-xs leading-6 text-rose-200/90">
          <li v-for="conflict in chosenConflicts" :key="`${conflict.code}-${conflict.other.slug}`">
            {{ conflict.text }}
          </li>
        </ul>
        <p class="mt-2 text-xs text-rose-200/80">
          انتخاب‌های شما حذف نشده‌اند؛ می‌توانید همین قطعه را نگه دارید و قطعهٔ ناسازگار را از مرحلهٔ خودش عوض کنید.
        </p>
      </div>
    </section>

    <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
      <button
        type="button"
        class="min-h-10 rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:opacity-40"
        :disabled="stepIndex === 0"
        @click="goToStep(stepIndex - 1)"
      >
        مرحلهٔ قبلی
      </button>
      <button
        type="button"
        class="min-h-10 rounded-lg border border-slate-300 px-4 py-2 text-sm disabled:opacity-40"
        :disabled="stepIndex === steps.length - 1"
        @click="goToStep(stepIndex + 1)"
      >
        مرحلهٔ بعدی
      </button>
    </div>

    <section v-if="allPartsSelected" class="mt-8 rounded-xl border border-slate-200 bg-surface p-4 sm:p-6">
      <h2 class="mb-3 text-lg font-bold">خلاصهٔ سیستم</h2>
      <ul class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <li
          v-for="(item, index) in steps"
          :key="item.slug"
          class="rounded-lg border p-3"
          :class="stepState(index) === 'error' ? 'border-rose-500/40' : 'border-slate-200'"
        >
          <p class="text-xs text-slate-500">{{ item.label }}</p>
          <p class="font-medium">{{ selected[item.slug]?.display_title }}</p>
          <p class="mt-1 text-sm">{{ formatPrice(selected[item.slug]?.price) }}</p>
          <p v-if="stepState(index) === 'error'" class="mt-1 text-xs text-rose-300">
            ! این قطعه با قطعهٔ دیگری ناسازگار است
          </p>
        </li>
      </ul>
      <p class="mt-4 font-bold">جمع قیمت: {{ formatPrice(totalPrice) }}</p>

      <p
        v-if="report"
        class="mt-4 text-sm"
        :class="report.verdict === 'block' ? 'text-rose-300' : 'text-emerald-300'"
      >
        {{ report.verdict === 'block' ? 'قطعات این سیستم با هم ناسازگارند' : report.verdict === 'warn' ? 'سازگار، با موارد قابل توجه' : 'همهٔ بررسی‌های قطعی سازگاری موفق بودند' }}
      </p>
      <ul v-if="blockingFindings.length" class="mt-2 list-inside list-disc text-sm text-rose-300">
        <li v-for="(finding, index) in blockingFindings" :key="`${finding.rule_code}-${index}`">
          {{ finding.message_fa || finding.message }}
        </li>
      </ul>

      <div class="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
        <label class="flex-1 text-sm text-slate-500">
          نام سیستم ذخیره‌شده
          <input
            v-model="buildName"
            class="mt-1 w-full rounded-lg border border-slate-300 bg-surface px-3 py-2 text-slate-900"
            maxlength="80"
          />
        </label>
        <button
          v-if="canSaveBuild"
          type="button"
          class="btn-primary"
          @click="saveCurrentBuild"
        >
          ذخیره در پنل من
        </button>
        <button type="button" class="rounded-xl border border-slate-300 px-5 py-3 text-sm" @click="reset">
          شروع دوباره
        </button>
      </div>
      <p v-if="!canSaveBuild" class="mt-3 text-xs text-amber-300">
        تا رفع ناسازگاری، امکان ذخیرهٔ سیستم فعال نیست.
      </p>
    </section>

    <section
      v-else
      class="mt-8 rounded-xl border border-dashed border-slate-300 p-5 text-sm text-slate-500"
    >
      برای دیدن خلاصه و بررسی نهایی، هر هشت مرحله را انتخاب کنید. مرحله‌های باقی‌مانده:
      {{ steps.filter(({ slug }) => !selected[slug]).map(({ label }) => label).join('، ') }}
    </section>

  </div>
</template>
