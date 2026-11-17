<script setup lang="ts">
/**
 * A shared pager: previous / next plus numbered pages.
 *
 * The parent owns the state (`page` + `totalPages`) and reacts to the `change`
 * event, which is what keeps the page number in the URL and the request in sync.
 * The window is kept short (first, last, and the pages around the current one) so
 * a long list never turns into a wall of buttons on a phone.
 */
const props = defineProps<{ page: number; totalPages: number }>()
const emit = defineEmits<{ change: [page: number] }>()

const total = computed(() => Math.max(1, props.totalPages))
const current = computed(() => Math.min(Math.max(1, props.page), total.value))

const pages = computed<number[]>(() => {
  if (total.value <= 7) {
    return Array.from({ length: total.value }, (_, index) => index + 1)
  }
  const window = new Set<number>([
    1,
    total.value,
    current.value,
    current.value - 1,
    current.value + 1,
  ])
  return [...window].filter((value) => value >= 1 && value <= total.value).sort((a, b) => a - b)
})

const leadingGap = computed(() => pages.value.length > 0 && (pages.value[0] ?? 1) > 2)
const trailingGap = computed(() => {
  const last = pages.value[pages.value.length - 1] ?? total.value
  return last < total.value - 1
})

function go(next: number) {
  const target = Math.min(Math.max(1, next), total.value)
  if (target !== current.value) emit("change", target)
}
</script>

<template>
  <nav
    v-if="total > 1"
    class="flex flex-wrap items-center justify-center gap-2"
    aria-label="صفحه‌بندی"
  >
    <button
      type="button"
      class="min-h-10 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-40"
      :disabled="current <= 1"
      @click="go(current - 1)"
    >
      قبلی
    </button>

    <template v-for="(value, index) in pages" :key="value">
      <span
        v-if="index === 0 && leadingGap"
        class="px-1 text-sm text-slate-400"
        aria-hidden="true"
      >
        …
      </span>

      <button
        type="button"
        class="min-h-10 min-w-10 rounded-lg border px-3 py-1.5 text-sm transition-colors"
        :class="
          value === current
            ? 'border-brand-600 bg-brand-600 font-semibold text-white'
            : 'border-slate-300 text-slate-600 hover:border-brand-300 hover:text-brand-700'
        "
        :aria-current="value === current ? 'page' : undefined"
        :aria-label="`صفحهٔ ${value}`"
        @click="go(value)"
      >
        {{ value }}
      </button>

      <span
        v-if="index === pages.length - 1 && trailingGap"
        class="px-1 text-sm text-slate-400"
        aria-hidden="true"
      >
        …
      </span>
    </template>

    <button
      type="button"
      class="min-h-10 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-700 disabled:cursor-not-allowed disabled:opacity-40"
      :disabled="current >= total"
      @click="go(current + 1)"
    >
      بعدی
    </button>
  </nav>
</template>
