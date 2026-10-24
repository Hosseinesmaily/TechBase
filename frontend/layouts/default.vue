<script setup lang="ts">
const route = useRoute()

const links = [
  { to: "/wiki", label: "ویکی" },
  { to: "/catalog", label: "کاتالوگ" },
  { to: "/search", label: "جستجو" },
  { to: "/configurator", label: "اسمبل سیستم" },
  { to: "/compare", label: "مقایسه" },
  { to: "/chat", label: "دستیار" },
]

function isActive(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`)
}
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="border-b border-slate-200 bg-surface">
      <div class="mx-auto max-w-7xl px-4 sm:px-6">
        <div class="flex min-h-16 items-center justify-between gap-4">
          <NuxtLink to="/" class="inline-flex shrink-0 items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600" aria-label="تک‌بیس، صفحهٔ اصلی">
            <span class="grid h-9 w-9 place-items-center rounded-lg bg-brand-600 text-white" aria-hidden="true">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M4 5.5h16v10H4zM8 19h8m-4-3.5V19m-3-10h6m-6 3h4" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <span>
              <span class="block text-base font-bold leading-tight text-slate-900">تک‌بیس</span>
              <span class="block text-[11px] leading-tight text-slate-500">دانش سخت‌افزار، انتخاب آگاهانه</span>
            </span>
          </NuxtLink>

          <NuxtLink
            to="/search"
            class="hidden items-center gap-2 rounded-full border border-slate-200 bg-surface/65 px-4 py-2.5 text-sm text-slate-500 shadow-sm transition-colors hover:border-brand-300 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 lg:flex"
          >
            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <circle cx="10.8" cy="10.8" r="6.3" />
              <path d="m16 16 4.2 4.2" stroke-linecap="round" />
            </svg>
            <span>جست‌وجو در محصولات و راهنماها</span>
            <kbd dir="ltr" class="mr-8 rounded border border-slate-200 px-1.5 py-0.5 text-[10px]">/</kbd>
          </NuxtLink>

          <NuxtLink
            to="/account"
            aria-label="پنل من"
            :aria-current="isActive('/account') ? 'page' : undefined"
            title="پنل من"
            class="inline-flex h-10 shrink-0 items-center gap-2 rounded-full border border-slate-200 px-2.5 text-sm font-medium text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 sm:px-3"
            :class="isActive('/account') ? 'border-brand-200 bg-brand-50 text-brand-700' : ''"
          >
            <span class="grid h-7 w-7 place-items-center rounded-full bg-slate-100 text-slate-600" aria-hidden="true">
              <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8">
                <circle cx="12" cy="8" r="3.25" />
                <path d="M5.5 20a6.5 6.5 0 0 1 13 0" stroke-linecap="round" />
              </svg>
            </span>
            <span class="hidden sm:inline">پنل من</span>
          </NuxtLink>
        </div>

        <nav aria-label="ناوبری اصلی" class="grid grid-cols-3 gap-1 pb-3 sm:flex sm:flex-wrap sm:items-center sm:gap-1">
          <NuxtLink
            v-for="link in links"
            :key="link.to"
            :to="link.to"
            :aria-current="isActive(link.to) ? 'page' : undefined"
            class="rounded-lg px-3 py-2 text-center text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 sm:text-start"
            :class="isActive(link.to) ? 'bg-brand-50 font-semibold text-brand-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'"
          >
            {{ link.label }}
          </NuxtLink>
        </nav>
      </div>
    </header>

    <main class="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
      <slot />
    </main>

    <footer class="border-t border-slate-200 bg-surface">
      <div class="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>تک‌بیس؛ مرجع فارسی سخت‌افزار و راهنمای خرید</p>
        <div class="flex items-center gap-4 text-xs">
          <p>قیمت و موجودی بر اساس آخرین دادهٔ فروشگاه نمایش داده می‌شود.</p>
          <NuxtLink to="/admin-panel" class="underline underline-offset-2 hover:text-brand-700">مدیریت</NuxtLink>
        </div>
      </div>
    </footer>
  </div>
</template>
