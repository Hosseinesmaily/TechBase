<script setup lang="ts">
const query = ref("")

/**
 * The API reachability comes from a real request, and only when it fails does
 * the page say anything about it: a successful connection is not a marketing
 * message, so no status text is rendered for it.
 */
const { state: apiState, check: checkApi } = useApiHealth()
const retrying = ref(false)

async function retryApi() {
  retrying.value = true
  await checkApi()
  retrying.value = false
}

onMounted(() => {
  if (apiState.value !== "ok") void checkApi()
})

const destinations = [
  {
    eyebrow: "راهنمای خرید",
    title: "قطعه را بهتر بشناسید",
    description: "مشخصات، کاربردها و نکته‌های انتخاب قطعات کامپیوتر را در مقاله‌های ویکی بخوانید.",
    to: "/wiki",
    action: "رفتن به ویکی",
    icon: "book",
  },
  {
    eyebrow: "محصولات فروشگاه",
    title: "قیمت و موجودی را مقایسه کنید",
    description: "قطعات و سیستم‌های آماده را با مشخصات و زمان آخرین به‌روزرسانی ببینید.",
    to: "/catalog",
    action: "دیدن کاتالوگ",
    icon: "box",
  },
  {
    eyebrow: "انتخاب قطعات",
    title: "سیستم سازگار بسازید",
    description: "قطعات را مرحله‌به‌مرحله انتخاب کنید و سازگاری آن‌ها را با قوانین فنی بسنجید.",
    to: "/configurator",
    action: "شروع اسمبل",
    icon: "cpu",
  },
]

function submitSearch() {
  const q = query.value.trim()
  if (q) navigateTo({ path: "/search", query: { q } })
  else navigateTo("/search")
}

useSeoMeta({
  title: "تک‌بیس | دانش سخت‌افزار، انتخاب آگاهانه",
  description: "جست‌وجو در محصولات، مقاله‌های ویکی و راهنماهای سخت‌افزار کامپیوتر؛ فارسی و مستند.",
})
</script>

<template>
  <div class="space-y-12 sm:space-y-16">
    <ApiErrorNotice
      v-if="apiState === 'error' || retrying"
      :pending="retrying"
      @retry="retryApi"
    />

    <section class="relative overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-bl from-brand-50 via-surface/65 to-transparent px-5 py-10 sm:px-10 sm:py-14">
      <div class="relative grid items-center gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div class="min-w-0">
        <p class="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-100 bg-surface/85 px-3 py-1 text-xs font-semibold text-brand-700">
          <span class="h-1.5 w-1.5 rounded-full bg-brand-400" aria-hidden="true" />
          دانش سخت‌افزار به زبان فارسی
        </p>
        <h1 class="max-w-2xl text-[1.7rem] font-bold leading-[1.5] tracking-tight text-slate-950 sm:text-[2.1rem] lg:text-[2.6rem]">
          برای انتخاب قطعات مناسب، از شناخت شروع کنید.
        </h1>
        <p class="mt-4 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
          مشخصات فنی را بررسی کنید، راهنماهای خرید را بخوانید و قطعات سازگار با سیستم خود را پیدا کنید.
          اطلاعات محصولات و قیمت‌ها را بر اساس منابع موجود در سایت بررسی کنید.
        </p>

        <form class="search-shell mt-7 flex flex-col gap-2 p-2 sm:max-w-2xl sm:flex-row" role="search" @submit.prevent="submitSearch">
          <label for="home-search" class="sr-only">جست‌وجو در قطعات و مقاله‌ها</label>
          <input
            id="home-search"
            v-model="query"
            type="search"
            name="q"
            autocomplete="off"
            placeholder="مثلاً کارت گرافیک برای بازی ۱۴۴۰p…"
            class="search-field min-w-0 flex-1 rounded-xl px-4 py-3 text-base"
          />
          <button type="submit" class="search-submit inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-300">
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <circle cx="10.8" cy="10.8" r="6.3" />
              <path d="m16 16 4.2 4.2" stroke-linecap="round" />
            </svg>
            جست‌وجو
          </button>
        </form>

        <div class="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span class="ml-1">جست‌وجوهای پرطرفدار:</span>
          <NuxtLink to="/search?q=پردازنده" class="rounded-full border border-slate-200 bg-surface px-3 py-1.5 transition-colors hover:border-brand-300 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600">پردازنده</NuxtLink>
          <NuxtLink to="/search?q=کارت+گرافیک" class="rounded-full border border-slate-200 bg-surface px-3 py-1.5 transition-colors hover:border-brand-300 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600">کارت گرافیک</NuxtLink>
          <NuxtLink to="/search?q=سیستم+گیمینگ" class="rounded-full border border-slate-200 bg-surface px-3 py-1.5 transition-colors hover:border-brand-300 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600">سیستم گیمینگ</NuxtLink>
        </div>
        </div>

        <div class="mx-auto w-full max-w-sm lg:max-w-none">
          <div class="rounded-2xl border border-slate-200 bg-surface/70 p-3 shadow-card">
            <svg
              viewBox="0 0 480 360"
              class="h-auto w-full"
              role="img"
              aria-label="تصویرسازی میز کار با رایانه شخصی و فردی که پشت آن نشسته است"
            >
              <defs>
                <linearGradient id="tb-hero-canvas" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#101a31" />
                  <stop offset="55%" stop-color="#0d1526" />
                  <stop offset="100%" stop-color="#17131b" />
                </linearGradient>
                <radialGradient id="tb-hero-blue" cx="28%" cy="20%" r="66%">
                  <stop offset="0%" stop-color="#2352b8" stop-opacity="0.45" />
                  <stop offset="100%" stop-color="#2352b8" stop-opacity="0" />
                </radialGradient>
                <radialGradient id="tb-hero-copper" cx="84%" cy="80%" r="62%">
                  <stop offset="0%" stop-color="#7b3a1b" stop-opacity="0.4" />
                  <stop offset="100%" stop-color="#7b3a1b" stop-opacity="0" />
                </radialGradient>
              </defs>

              <rect width="480" height="360" rx="20" fill="url(#tb-hero-canvas)" />
              <rect width="480" height="360" rx="20" fill="url(#tb-hero-blue)" />
              <rect width="480" height="360" rx="20" fill="url(#tb-hero-copper)" />

              <!-- the person, seated behind the desk -->
              <circle cx="88" cy="180" r="18" fill="#1b2842" stroke="#3a4965" stroke-width="2" />
              <path d="M56 250c0-25 14-44 32-44s32 19 32 44z" fill="#172238" stroke="#3a4965" stroke-width="2" />

              <!-- desk -->
              <rect x="40" y="250" width="400" height="12" rx="6" fill="#29364f" />
              <rect x="60" y="256" width="46" height="4" rx="2" fill="#1f2b44" />

              <!-- monitor -->
              <rect x="150" y="56" width="232" height="150" rx="14" fill="#0f1a2e" stroke="#29364f" stroke-width="2" />
              <rect x="162" y="68" width="208" height="112" rx="9" fill="#111a2d" />
              <rect x="162" y="68" width="208" height="112" rx="9" fill="#2868ee" opacity="0.06" />
              <rect x="178" y="84" width="96" height="8" rx="4" fill="#29364f" />
              <rect x="178" y="98" width="58" height="6" rx="3" fill="#1f2b44" />
              <rect x="178" y="136" width="20" height="30" rx="4" fill="#31518b" />
              <rect x="206" y="122" width="20" height="44" rx="4" fill="#2868ee" />
              <rect x="234" y="104" width="20" height="62" rx="4" fill="#4b83ff" />
              <rect x="262" y="130" width="20" height="36" rx="4" fill="#31518b" />
              <rect x="290" y="92" width="20" height="74" rx="4" fill="#b06a3c" />
              <rect x="318" y="116" width="20" height="50" rx="4" fill="#3479ff" />
              <rect x="252" y="206" width="28" height="32" rx="6" fill="#172238" />
              <rect x="216" y="238" width="100" height="12" rx="5" fill="#1f2b44" stroke="#29364f" />

              <!-- tower -->
              <rect x="396" y="110" width="62" height="140" rx="12" fill="#101a31" stroke="#29364f" stroke-width="2" />
              <circle cx="427" cy="146" r="16" fill="#0d1526" stroke="#29364f" />
              <circle cx="427" cy="192" r="16" fill="#0d1526" stroke="#29364f" />
              <circle cx="427" cy="146" r="5" fill="#1f2b44" />
              <circle cx="427" cy="192" r="5" fill="#1f2b44" />
              <rect x="410" y="220" width="34" height="6" rx="3" fill="#2868ee" opacity="0.9" />
              <circle cx="427" cy="238" r="4" fill="#34d399" />
            </svg>
          </div>
        </div>
      </div>
    </section>

    <section aria-labelledby="destinations-title">
      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-xs font-semibold text-brand-700">از کجا شروع کنیم؟</p>
          <h2 id="destinations-title" class="mt-1 text-xl font-bold text-slate-900 sm:text-2xl">ابزارهای انتخاب بهتر</h2>
        </div>
        <NuxtLink to="/chat" class="inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold text-brand-700 transition-colors hover:bg-brand-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600">
          پرسش از دستیار
          <span aria-hidden="true">←</span>
        </NuxtLink>
      </div>

      <div class="grid gap-4 md:grid-cols-3">
        <NuxtLink
          v-for="item in destinations"
          :key="item.to"
          :to="item.to"
          class="group flex min-h-56 flex-col rounded-xl border border-slate-200 bg-surface p-5 transition-colors duration-200 hover:border-brand-300 hover:bg-brand-50/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 focus-visible:ring-offset-2"
        >
          <span class="mb-5 grid h-11 w-11 place-items-center rounded-lg bg-brand-50 text-brand-700" aria-hidden="true">
            <svg v-if="item.icon === 'book'" viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M5 4.75h10.5A2.5 2.5 0 0 1 18 7.25v12H7a2 2 0 0 1-2-2z" stroke-linejoin="round" />
              <path d="M8 8h6m-6 3h6m-6 3h4M18 17.25a2 2 0 0 1 2 2H7a2 2 0 0 1-2-2" stroke-linecap="round" />
            </svg>
            <svg v-else-if="item.icon === 'box'" viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="m12 3.75 8 4.5v7.5l-8 4.5-8-4.5v-7.5z" stroke-linejoin="round" />
              <path d="m4.25 8.4 7.75 4.35 7.75-4.35M12 12.75v7" stroke-linejoin="round" />
            </svg>
            <svg v-else viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8">
              <rect x="6.5" y="6.5" width="11" height="11" rx="1.5" />
              <path d="M9 2.75v3.5m6-3.5v3.5M9 17.75v3.5m6-3.5v3.5M2.75 9h3.5m-3.5 6h3.5m11.5-6h3.5m-3.5 6h3.5" stroke-linecap="round" />
            </svg>
          </span>
          <p class="text-xs font-medium text-brand-700">{{ item.eyebrow }}</p>
          <h3 class="mt-1 text-lg font-bold text-slate-900">{{ item.title }}</h3>
          <p class="mt-2 flex-1 text-sm leading-7 text-slate-600">{{ item.description }}</p>
          <span class="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-brand-700">
            {{ item.action }}
            <span class="transition-transform group-hover:-translate-x-1" aria-hidden="true">←</span>
          </span>
        </NuxtLink>
      </div>
    </section>

  </div>
</template>
