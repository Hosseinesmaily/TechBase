<script setup lang="ts">
import { formatDate, formatPrice } from "~/utils/format"

const shelf = useCustomerShelf()

useSeoMeta({
  title: "پنل من | تک‌بیس",
  description: "علاقه‌مندی‌ها، سیستم‌های ذخیره‌شده و فهرست مقایسهٔ شما.",
})
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-8">
    <header>
      <p class="text-sm font-semibold text-brand-700">فضای شخصی این مرورگر</p>
      <h1 class="mt-1 text-2xl font-bold">پنل من</h1>
      <p class="mt-2 text-sm leading-7 text-slate-500">علاقه‌مندی‌ها، جست‌وجوهای اخیر و سیستم‌های اسمبل‌شده روی همین دستگاه ذخیره می‌شوند. این نسخه حساب کاربری، سفارش یا پرداخت آنلاین ندارد.</p>
    </header>

    <section class="rounded-xl border border-slate-200 bg-surface p-5">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 class="font-bold">فهرست مقایسه</h2>
          <p class="mt-1 text-xs text-slate-500">{{ shelf.compareItems.value.length }} محصول، حداکثر ۴ محصول</p>
        </div>
        <NuxtLink to="/compare" class="text-sm font-semibold text-brand-700 hover:underline">رفتن به مقایسه</NuxtLink>
      </div>
      <ul v-if="shelf.compareItems.value.length" class="divide-y divide-slate-100 rounded-lg border border-slate-200">
        <li v-for="product in shelf.compareItems.value" :key="product.sku" class="flex items-center justify-between gap-3 p-3">
          <NuxtLink :to="`/entity/${product.entity_slug}/`" class="min-w-0 truncate font-medium hover:text-brand-700">{{ product.title }}</NuxtLink>
          <div class="flex shrink-0 items-center gap-3 text-sm">
            <span>{{ formatPrice(product.price, product.currency) }}</span>
            <button type="button" class="text-xs text-rose-700" @click="shelf.removeCompare(product.sku)">حذف</button>
          </div>
        </li>
      </ul>
      <p v-else class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">در کاتالوگ یا نتایج جست‌وجو محصولی را به مقایسه اضافه کنید.</p>
      <NuxtLink v-if="shelf.compareItems.value.length >= 2" to="/compare" class="mt-4 inline-flex rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white">مقایسهٔ محصولات انتخاب‌شده</NuxtLink>
    </section>

    <section class="rounded-xl border border-slate-200 bg-surface p-5">
      <div class="mb-4 flex items-center justify-between gap-3">
        <h2 class="font-bold">علاقه‌مندی‌ها</h2>
        <NuxtLink to="/catalog" class="text-sm text-brand-700 hover:underline">مرور کاتالوگ</NuxtLink>
      </div>
      <ul v-if="shelf.favorites.value.length" class="grid gap-3 sm:grid-cols-2">
        <li v-for="product in shelf.favorites.value" :key="product.sku" class="rounded-lg border border-slate-200 p-4">
          <NuxtLink :to="`/entity/${product.entity_slug}/`" class="font-semibold hover:text-brand-700">{{ product.title }}</NuxtLink>
          <p class="mt-2 font-bold">{{ formatPrice(product.price, product.currency) }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ product.in_stock ? "هنگام ذخیره موجود بود" : "هنگام ذخیره ناموجود بود" }} · به‌روزرسانی داده: {{ formatDate(product.updated_at) }}</p>
          <div class="mt-3 flex gap-3 text-xs">
            <button type="button" class="text-brand-700 underline" @click="shelf.toggleCompare(product)">افزودن/حذف از مقایسه</button>
            <button type="button" class="text-rose-700 underline" @click="shelf.removeFavorite(product.sku)">حذف علاقه‌مندی</button>
          </div>
        </li>
      </ul>
      <p v-else class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">هنوز محصولی ذخیره نکرده‌اید. از کارت محصول دکمهٔ «علاقه‌مندی» را بزنید.</p>
    </section>

    <section class="rounded-xl border border-slate-200 bg-surface p-5">
      <div class="mb-4 flex items-center justify-between gap-3">
        <h2 class="font-bold">سیستم‌های ذخیره‌شده</h2>
        <NuxtLink to="/configurator" class="text-sm text-brand-700 hover:underline">ساخت سیستم</NuxtLink>
      </div>
      <ul v-if="shelf.builds.value.length" class="space-y-3">
        <li v-for="build in shelf.builds.value" :key="build.id" class="rounded-lg border border-slate-200 p-4">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="font-semibold">{{ build.name }}</h3>
              <p class="mt-1 text-xs text-slate-500">ذخیره‌شده در {{ formatDate(build.saved_at) }} · {{ build.products.length }} قطعه</p>
            </div>
            <button type="button" class="text-xs text-rose-700 underline" @click="shelf.removeBuild(build.id)">حذف سیستم</button>
          </div>
          <ul class="mt-3 flex flex-wrap gap-2">
            <li v-for="product in build.products" :key="product.sku" class="rounded-full bg-slate-100 px-3 py-1 text-xs">{{ product.title }}</li>
          </ul>
          <p class="mt-3 text-xs text-amber-700">قیمت و موجودی این نسخه، تصویر زمان ذخیره است؛ برای دادهٔ فعلی کاتالوگ را بررسی کنید.</p>
        </li>
      </ul>
      <p v-else class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">بعد از انتخاب همهٔ قطعات سازگار، سیستم را از صفحهٔ اسمبل اینجا ذخیره کنید.</p>
    </section>

    <section class="rounded-xl border border-slate-200 bg-surface p-5">
      <h2 class="mb-3 font-bold">جست‌وجوهای اخیر</h2>
      <div v-if="shelf.recentSearches.value.length" class="flex flex-wrap gap-2">
        <NuxtLink v-for="term in shelf.recentSearches.value" :key="term" :to="{ path: '/search', query: { q: term } }" class="rounded-full border border-slate-200 px-3 py-1.5 text-sm hover:border-brand-300">{{ term }}</NuxtLink>
      </div>
      <p v-else class="text-sm text-slate-500">جست‌وجوهای شما پس از اولین جست‌وجو اینجا دیده می‌شوند.</p>
    </section>
  </div>
</template>
