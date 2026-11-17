<script setup lang="ts">
import type { ShoppingCartItem } from "~/composables/useCart"
import { formatDate, formatPrice } from "~/utils/format"

const account = useAccount()
const shoppingCart = useCart()
const actionPending = ref(false)

useSeoMeta({
  title: "سبد خرید | تک‌بیس",
  description: "مدیریت محصولات انتخاب‌شده در سبد خرید تک‌بیس.",
})

async function updateQuantity(item: ShoppingCartItem, event: Event) {
  const quantity = Number((event.target as HTMLInputElement).value)
  actionPending.value = true
  shoppingCart.error.value = ""
  try {
    await shoppingCart.update(item.sku, quantity)
  } catch (error) {
    shoppingCart.error.value = error instanceof Error ? error.message : "تعداد به‌روزرسانی نشد."
  } finally {
    actionPending.value = false
  }
}

async function removeItem(sku: string) {
  actionPending.value = true
  shoppingCart.error.value = ""
  try {
    await shoppingCart.remove(sku)
  } catch (error) {
    shoppingCart.error.value = error instanceof Error ? error.message : "حذف محصول انجام نشد."
  } finally {
    actionPending.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-4xl space-y-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <p class="text-sm font-semibold text-brand-700">متصل به حساب کاربری</p>
        <h1 class="mt-1 text-2xl font-bold">سبد خرید</h1>
      </div>
      <NuxtLink to="/catalog" class="text-sm font-medium text-brand-700 hover:underline">ادامهٔ خرید از کاتالوگ</NuxtLink>
    </header>

    <section v-if="account.pending.value" class="rounded-xl border border-slate-200 bg-surface p-8 text-center text-slate-500">
      در حال بررسی حساب…
    </section>

    <section v-else-if="!account.user.value" class="rounded-xl border border-slate-200 bg-surface p-8 text-center">
      <h2 class="font-bold">برای دیدن سبد خرید وارد حساب شو</h2>
      <p class="mt-2 text-sm text-slate-500">سبد خرید هر کاربر جداگانه ذخیره می‌شود.</p>
      <NuxtLink :to="{ path: '/account', query: { next: '/cart' } }" class="btn-primary mt-4 inline-flex">ورود یا ساخت حساب</NuxtLink>
    </section>

    <template v-else>
      <p v-if="shoppingCart.pending.value" class="rounded-xl border border-slate-200 bg-surface p-6 text-center text-sm text-slate-500">در حال بارگذاری سبد…</p>
      <p v-if="shoppingCart.error.value" role="alert" class="alert-error">{{ shoppingCart.error.value }}</p>

      <section v-if="shoppingCart.cart.value?.items.length" class="space-y-3">
        <article v-for="item in shoppingCart.cart.value.items" :key="item.sku" class="grid gap-4 rounded-xl border border-slate-200 bg-surface p-4 sm:grid-cols-[1fr_auto] sm:items-center">
          <div class="min-w-0">
            <NuxtLink :to="`/entity/${item.entity_slug}/`" class="font-semibold leading-7 hover:text-brand-700">{{ item.title }}</NuxtLink>
            <p class="mt-1 text-sm font-bold">{{ formatPrice(item.price, item.currency) }} <span class="font-normal text-slate-500">برای هر عدد</span></p>
            <p class="mt-1 text-xs" :class="item.in_stock && item.stock >= item.quantity ? 'text-emerald-700' : 'text-rose-700'">
              {{ item.in_stock ? `موجودی فعلی: ${item.stock}` : "در حال حاضر ناموجود" }}
            </p>
            <p v-if="item.price_updated_at" class="mt-1 text-xs text-slate-400">به‌روزرسانی قیمت: {{ formatDate(item.price_updated_at) }}</p>
          </div>
          <div class="flex items-center justify-between gap-4 sm:justify-end">
            <label class="text-xs text-slate-500">تعداد
              <input type="number" min="1" max="99" :value="item.quantity" :disabled="actionPending" class="mt-1 block w-20 rounded-lg border border-slate-300 px-2 py-2 text-center text-sm" @change="updateQuantity(item, $event)" />
            </label>
            <div class="text-left">
              <p class="text-xs text-slate-500">جمع این محصول</p>
              <p class="mt-1 font-bold">{{ formatPrice(item.subtotal, item.currency) }}</p>
              <button type="button" :disabled="actionPending" class="mt-2 text-xs text-rose-700 underline disabled:opacity-50" @click="removeItem(item.sku)">حذف از سبد</button>
            </div>
          </div>
        </article>

        <section class="rounded-xl border border-slate-200 bg-surface p-5">
          <div class="flex items-center justify-between gap-4">
            <span class="font-semibold">جمع فعلی سبد · {{ shoppingCart.cart.value.item_count }} عدد</span>
            <span class="text-lg font-bold">{{ formatPrice(shoppingCart.cart.value.total, shoppingCart.cart.value.currency) }}</span>
          </div>
          <p class="mt-3 text-xs leading-6 text-slate-500">این جمع بر اساس قیمت و موجودی فعلی کاتالوگ است. ثبت سفارش و پرداخت آنلاین هنوز به درگاه یا سامانهٔ فروش متصل نشده است.</p>
        </section>
      </section>

      <section v-else-if="!shoppingCart.pending.value" class="rounded-xl border border-dashed border-slate-300 bg-surface p-10 text-center">
        <h2 class="font-semibold">سبد خریدت خالی است</h2>
        <p class="mt-2 text-sm text-slate-500">از کاتالوگ محصول انتخاب کن و به سبد اضافه کن.</p>
        <NuxtLink to="/catalog" class="btn-primary mt-4 inline-flex">رفتن به کاتالوگ</NuxtLink>
      </section>
    </template>
  </div>
</template>
