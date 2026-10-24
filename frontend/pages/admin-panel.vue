<script setup lang="ts">
interface Health { status: string; service?: string }
interface Readiness { status: string; checks: Record<string, string> }

const { data: health, pending: healthPending } = await useFetch<Health>("/api/v1/health/", { server: true })
const { data: readiness, pending: readinessPending } = await useFetch<Readiness>("/api/v1/health/ready/", { server: true })

const managementLinks = [
  { title: "مدیریت Django", description: "مدیریت کاربران، محصولات، قطعات، برندها و داده‌های فروشگاه.", href: "http://localhost:8000/admin/", action: "ورود به مدیریت Django" },
  { title: "مدیریت محتوای ویکی", description: "ساخت و بازبینی راهنماها، صفحات قطعات و محتوای تحریریه در Wagtail.", href: "http://localhost:8000/cms/", action: "ورود به مدیریت ویکی" },
  { title: "مستندات API", description: "مشاهدهٔ مسیرهای API و قراردادهای درخواست و پاسخ.", href: "http://localhost:8000/api/docs/", action: "بازکردن مستندات API" },
]

useSeoMeta({ title: "پنل مدیریت | تک‌بیس", description: "دسترسی به مدیریت محتوا، کاتالوگ و سلامت سرویس تک‌بیس." })
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-8">
    <header>
      <p class="text-sm font-semibold text-brand-700">ویژهٔ مدیران و تحریریه</p>
      <h1 class="mt-1 text-2xl font-bold">پنل مدیریت</h1>
      <p class="mt-2 text-sm leading-7 text-slate-500">ورود و سطح دسترسی توسط سامانهٔ مدیریت Django و Wagtail کنترل می‌شود؛ این صفحه فقط میان‌بُرها و وضعیت سرویس را نمایش می‌دهد.</p>
    </header>

    <section class="grid gap-3 sm:grid-cols-2">
      <div class="rounded-xl border border-slate-200 bg-surface p-4">
        <p class="text-xs text-slate-500">پاسخ API</p>
        <p class="mt-2 font-semibold" :class="health?.status === 'ok' ? 'text-emerald-700' : 'text-amber-700'">
          {{ healthPending ? "در حال بررسی…" : health?.status === "ok" ? "سرویس فعال است" : "سرویس در دسترس نیست" }}
        </p>
      </div>
      <div class="rounded-xl border border-slate-200 bg-surface p-4">
        <p class="text-xs text-slate-500">آمادگی وابستگی‌ها</p>
        <p class="mt-2 font-semibold" :class="readiness?.status === 'ok' ? 'text-emerald-700' : 'text-amber-700'">
          {{ readinessPending ? "در حال بررسی…" : readiness?.status === "ok" ? "همهٔ وابستگی‌های لازم آماده‌اند" : "برخی وابستگی‌ها آماده نیستند" }}
        </p>
        <ul v-if="readiness?.checks" class="mt-3 flex flex-wrap gap-2">
          <li v-for="(state, name) in readiness.checks" :key="name" class="rounded-full px-2.5 py-1 text-xs" :class="state === 'ok' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'" dir="ltr">{{ name }}: {{ state }}</li>
        </ul>
      </div>
    </section>

    <section class="grid gap-4 md:grid-cols-3">
      <article v-for="item in managementLinks" :key="item.href" class="flex flex-col rounded-xl border border-slate-200 bg-surface p-5">
        <h2 class="font-bold">{{ item.title }}</h2>
        <p class="mt-2 flex-1 text-sm leading-7 text-slate-500">{{ item.description }}</p>
        <a :href="item.href" target="_blank" rel="noopener noreferrer" class="mt-5 inline-flex min-h-10 items-center justify-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-500">{{ item.action }}</a>
      </article>
    </section>

    <p class="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-7 text-slate-600">در اجرای محلی بدون Docker، بک‌اند باید روی <span dir="ltr">127.0.0.1:8000</span> و فرانت‌اند روی <span dir="ltr">localhost:3000</span> فعال باشند. ورود مدیر با حساب Django انجام می‌شود؛ این صفحه رمز پیش‌فرضی تعریف نمی‌کند.</p>
  </div>
</template>
