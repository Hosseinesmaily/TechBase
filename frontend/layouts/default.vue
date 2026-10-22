<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-white border-b border-slate-200">
      <nav class="mx-auto max-w-6xl px-4 h-14 flex items-center justify-between">
        <NuxtLink to="/" class="font-bold text-lg text-brand-600">تک‌بیس</NuxtLink>
        <div class="flex items-center gap-4 text-sm text-slate-600">
          <NuxtLink to="/" class="hover:text-slate-900">خانه</NuxtLink>
          <NuxtLink to="/wiki" class="hover:text-slate-900">ویکی</NuxtLink>
          <NuxtLink to="/catalog" class="hover:text-slate-900">کاتالوگ</NuxtLink>
          <NuxtLink to="/search" class="hover:text-slate-900">جستجو</NuxtLink>
          <NuxtLink to="/chat" class="hover:text-slate-900">دستیار</NuxtLink>
        </div>
      </nav>
    </header>

    <main class="flex-1 mx-auto w-full max-w-6xl px-4 py-8">
      <slot />
    </main>

    <footer class="border-t border-slate-200 bg-white">
      <div class="mx-auto max-w-6xl px-4 py-4 text-sm text-slate-500">
        تک‌بیس — پایگاه دانش سخت‌افزار
      </div>
    </footer>
  </div>
</template>
