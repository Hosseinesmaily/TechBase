<script setup lang="ts">
interface Health {
  status: string
}

interface Ready {
  status: string
  checks: Record<string, string>
}

const { data: health } = await useFetch<Health>("/api/v1/health/", { server: true })

const { data: ready } = await useFetch<Ready>("/api/v1/health/ready/", {
  server: true,
  lazy: true,
})

useSeoMeta({
  title: "تک‌بیس | پایگاه دانش سخت‌افزار",
  description: "راهنمای خرید، بنچمارک و پیشنهاد سیستم — فارسی، با استناد به ویکی.",
})
</script>

<template>
  <div class="space-y-8">
    <section class="text-center py-10">
      <h1 class="text-3xl font-bold mb-3">پایگاه دانش سخت‌افزار تک‌بیس</h1>
      <p class="text-slate-600 max-w-2xl mx-auto">
        راهنمای خرید، مشخصات فنی، بنچمارک و ویکی سخت‌افزار — همه با استناد به صفحات داخلی.
      </p>
    </section>

    <section class="grid gap-4 sm:grid-cols-2">
      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <h2 class="font-semibold mb-2">وضعیت API</h2>
        <p v-if="health" class="text-sm">
          <span
            class="inline-block w-2 h-2 rounded-full align-middle"
            :class="health.status === 'ok' ? 'bg-emerald-500' : 'bg-rose-500'"
          />
          <span class="mr-2" dir="ltr">/api/v1/health/ → {{ health.status }}</span>
        </p>
        <p v-else class="text-sm text-rose-600">API در دسترس نیست.</p>

        <template v-if="ready">
          <p class="mt-3 font-semibold text-sm">Readiness:</p>
          <ul class="text-sm text-slate-600 space-y-1 mt-1">
            <li v-for="(value, key) in ready.checks" :key="key" dir="ltr">
              {{ key }}: {{ value }}
            </li>
          </ul>
        </template>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <h2 class="mb-2 font-semibold">کاتالوگ محصولات</h2>
        <p class="mb-3 text-sm text-slate-600">
          قیمت، موجودی و مشخصات فنی سیستم‌های آماده و قطعات — با تاریخ به‌روزرسانی.
        </p>
        <NuxtLink
          to="/catalog"
          class="inline-block rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-500"
        >
          مشاهدهٔ کاتالوگ
        </NuxtLink>
      </div>

      <div class="rounded-xl border border-slate-200 bg-white p-5">
        <h2 class="font-semibold mb-2">دستیار هوشمند</h2>
        <p class="text-sm text-slate-600 mb-3">
          سؤال خود را به فارسی بپرسید و پاسخِ با استناد بگیرید. (فاز ۴ فعال می‌شود)
        </p>
        <NuxtLink
          to="/chat"
          class="inline-block rounded-lg bg-brand-600 text-white px-4 py-2 text-sm hover:bg-brand-500"
        >
          شروع گفتگو
        </NuxtLink>
      </div>
    </section>
  </div>
</template>
