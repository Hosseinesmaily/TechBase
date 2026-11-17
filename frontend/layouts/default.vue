<script setup lang="ts">
const route = useRoute()
const account = useAccount()
const shoppingCart = useCart()
const shelf = useCustomerShelf()

/**
 * Content sections stay in the navigation row; the visitor's own things (the
 * comparison queue, the cart, the panel) sit together in the actions cluster next
 * to the other user controls, so nothing about the account is duplicated.
 */
const links = [
  { to: "/wiki", label: "ویکی" },
  { to: "/catalog", label: "کاتالوگ" },
  { to: "/search", label: "جستجو" },
  { to: "/configurator", label: "اسمبل سیستم" },
  { to: "/chat", label: "دستیار" },
]

const comparedCount = computed(() => shelf.compareItems.value.length)
const cartCount = computed(() => shoppingCart.cart.value?.item_count ?? 0)

function isActive(path: string) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function controlClass(path: string) {
  return isActive(path)
    ? "border-brand-200 bg-brand-50 text-brand-700"
    : "border-slate-200 text-slate-600 hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
}
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="border-b border-slate-200 bg-surface">
      <div class="mx-auto max-w-7xl px-4 sm:px-6">
        <div class="flex min-h-16 items-center justify-between gap-3">
          <NuxtLink
            to="/"
            class="inline-flex min-w-0 shrink items-center gap-2.5 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
            aria-label="تک‌بیس، صفحهٔ اصلی"
          >
            <span class="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-600 text-white" aria-hidden="true">
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M4 5.5h16v10H4zM8 19h8m-4-3.5V19m-3-10h6m-6 3h4" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </span>
            <span class="min-w-0">
              <span class="block truncate text-base font-bold leading-tight text-slate-900">تک‌بیس</span>
              <span class="hidden truncate text-[11px] leading-tight text-slate-500 sm:block">دانش سخت‌افزار، انتخاب آگاهانه</span>
            </span>
          </NuxtLink>

          <NuxtLink
            to="/search"
            class="hidden items-center gap-2 rounded-full border border-slate-200 bg-surface/65 px-4 py-2.5 text-sm text-slate-500 shadow-sm transition-colors hover:border-brand-300 hover:text-brand-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 md:flex lg:max-w-md lg:flex-1"
          >
            <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
              <circle cx="10.8" cy="10.8" r="6.3" />
              <path d="m16 16 4.2 4.2" stroke-linecap="round" />
            </svg>
            <span class="truncate">جست‌وجو در محصولات و راهنماها</span>
            <kbd dir="ltr" class="ms-auto hidden rounded border border-slate-200 px-1.5 py-0.5 text-[10px] lg:block">/</kbd>
          </NuxtLink>

          <!-- The visitor's own things: the comparison queue, the cart and the panel. -->
          <nav class="flex shrink-0 items-center gap-1.5 sm:gap-2" aria-label="کنترل‌های کاربر">
            <NuxtLink
              to="/compare"
              class="relative inline-flex h-10 items-center gap-2 rounded-full border px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 sm:px-3"
              :class="controlClass('/compare')"
              :aria-current="isActive('/compare') ? 'page' : undefined"
              aria-label="فهرست مقایسه"
              title="فهرست مقایسه"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M12 4.75v14.5M7.25 19.25h9.5M4.75 8.75h14.5" stroke-linecap="round" />
                <path d="M12 9.25 8.75 15h6.5z" stroke-linejoin="round" />
              </svg>
              <span class="hidden sm:inline">مقایسه</span>
              <span
                v-if="comparedCount"
                class="grid min-w-5 place-items-center rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white"
              >
                {{ comparedCount }}
              </span>
            </NuxtLink>

            <NuxtLink
              to="/cart"
              class="relative inline-flex h-10 items-center gap-2 rounded-full border px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 sm:px-3"
              :class="controlClass('/cart')"
              :aria-current="isActive('/cart') ? 'page' : undefined"
              aria-label="سبد خرید"
              title="سبد خرید"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <path d="M4 6.5h2l1.6 9.2A2 2 0 0 0 9.57 17.4h7.1a2 2 0 0 0 1.96-1.6L20 9.5H7" stroke-linecap="round" stroke-linejoin="round" />
                <circle cx="10" cy="20" r="1.2" />
                <circle cx="17" cy="20" r="1.2" />
              </svg>
              <span class="hidden sm:inline">سبد خرید</span>
              <span
                v-if="cartCount"
                class="grid min-w-5 place-items-center rounded-full bg-brand-600 px-1.5 py-0.5 text-[10px] font-bold text-white"
              >
                {{ cartCount }}
              </span>
            </NuxtLink>

            <NuxtLink
              to="/account"
              class="inline-flex h-10 items-center gap-2 rounded-full border px-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600 sm:px-3"
              :class="controlClass('/account')"
              :aria-current="isActive('/account') ? 'page' : undefined"
              aria-label="پنل من"
              title="پنل من"
            >
              <svg viewBox="0 0 24 24" class="h-4 w-4 shrink-0" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
                <circle cx="12" cy="8" r="3.25" />
                <path d="M5.5 20a6.5 6.5 0 0 1 13 0" stroke-linecap="round" />
              </svg>
              <span class="hidden sm:inline">پنل من</span>
            </NuxtLink>
          </nav>

        </div>

        <nav
          aria-label="ناوبری اصلی"
          class="grid grid-cols-3 gap-1 pb-3 sm:flex sm:flex-wrap sm:items-center sm:gap-1"
        >
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
        <NuxtLink to="/account" class="text-xs text-slate-500 underline underline-offset-2 hover:text-brand-700">
          پرسش یا مشکلی داری؟ از پنل خودت تیکت بفرست
        </NuxtLink>
      </div>
    </footer>

  </div>
</template>
