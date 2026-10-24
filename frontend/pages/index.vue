<script setup lang="ts">
interface Health {
  status: string
}

interface Ready {
  status: string
  checks: Record<string, string>
}

const query = ref("")
const { data: health } = await useFetch<Health>("/api/v1/health/", { server: true })
const { data: ready } = await useFetch<Ready>("/api/v1/health/ready/", {
  server: true,
  lazy: true,
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
    <section class="relative overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-bl from-brand-50 via-surface/65 to-transparent px-5 py-10 sm:px-10 sm:py-14">
      <div class="relative max-w-3xl">
        <p class="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-100 bg-surface/85 px-3 py-1 text-xs font-semibold text-brand-700">
          <span class="h-1.5 w-1.5 rounded-full bg-emerald-500" aria-hidden="true" />
          دانش سخت‌افزار به زبان فارسی
        </p>
        <h1 class="max-w-2xl text-3xl font-bold leading-[1.5] tracking-tight text-slate-950 sm:text-4xl lg:text-5xl">
          برای انتخاب قطعه،<br class="hidden sm:block" /> از دانستن شروع کنید.
        </h1>
        <p class="mt-4 max-w-2xl text-base leading-8 text-slate-600 sm:text-lg">
          مشخصات را بررسی کنید، راهنمای خرید بخوانید و قطعات سازگار پیدا کنید؛ اطلاعات فنی و قیمت را از منبع آن ببینید.
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

    <section class="flex flex-col gap-5 rounded-xl border border-slate-200 bg-surface p-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
      <div>
        <p class="text-xs font-semibold text-slate-500">وضعیت سرویس</p>
        <div class="mt-1 flex items-center gap-2">
          <span class="h-2 w-2 rounded-full" :class="health?.status === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'" aria-hidden="true" />
          <h2 class="font-semibold text-slate-900">{{ health?.status === 'ok' ? 'اتصال به API برقرار است' : 'در انتظار اتصال به API' }}</h2>
        </div>
      </div>
      <ul v-if="ready?.checks" class="flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500" aria-label="وضعیت وابستگی‌ها">
        <li v-for="(value, key) in ready.checks" :key="key" class="flex items-center gap-1.5" dir="ltr">
          <span class="h-1.5 w-1.5 rounded-full" :class="value === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'" aria-hidden="true" />
          {{ key }}
        </li>
      </ul>
    </section>
  </div>
</template>
