<script setup lang="ts">
/**
 * A horizontal bar chart of measured frame rates, one block per game + resolution.
 *
 * It is deliberately dependency-free — the site ships with Nuxt, Vue and Tailwind
 * only, so the bars are plain divs, not a chart library. Each bar is the product's
 * average FPS; the solid core inside it is the 1% low, so the stable floor is
 * visible against the average. Every bar shares one scale (the highest average on
 * the chart), so a longer bar always means a higher frame rate: the comparison is
 * absolute, never normalised per row, which would flatter the slower product.
 *
 * Nothing here is invented. The numbers come from the benchmark table the API
 * returned; a product with no measurement for a game simply has no bar.
 */

interface ChartSeries {
  slug: string
  title: string
}

interface ChartBar {
  slug: string
  avg: number | null
  low: number | null
}

interface ChartGroup {
  key: string
  label: string
  meta: string
  bars: ChartBar[]
}

const props = defineProps<{
  series: ChartSeries[]
  groups: ChartGroup[]
}>()

/** A distinct, high-contrast colour per series on the dark canvas. */
const SERIES_COLORS = ["#3479ff", "#f59e0b", "#10b981", "#f43f5e"]

function colorFor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length] ?? SERIES_COLORS[0]
}

const seriesIndexBySlug = computed(() => {
  const map = new Map<string, number>()
  props.series.forEach((item, index) => map.set(item.slug, index))
  return map
})

const titleBySlug = computed(() => {
  const map = new Map<string, string>()
  props.series.forEach((item) => map.set(item.slug, item.title))
  return map
})

function colorForSlug(slug: string): string {
  return colorFor(seriesIndexBySlug.value.get(slug) ?? 0)
}

const fpsNumber = new Intl.NumberFormat("fa-IR")

function formatFps(value: number | null): string {
  return value === null ? "—" : fpsNumber.format(value)
}

/** The highest average anywhere on the chart — the shared 100% of the scale. */
const maxFps = computed(() => {
  let max = 0
  for (const group of props.groups) {
    for (const bar of group.bars) {
      if (bar.avg !== null && bar.avg > max) max = bar.avg
    }
  }
  return max
})

function avgWidth(avg: number | null): string {
  if (avg === null || maxFps.value <= 0) return "0%"
  return `${Math.max(2, (avg / maxFps.value) * 100)}%`
}

/**
 * The 1% low on the same absolute scale as the average, capped so it never
 * pokes out of its own bar if a row's numbers disagree (data can be odd).
 */
function lowWidth(avg: number | null, low: number | null): string {
  if (low === null || maxFps.value <= 0) return "0%"
  const pct = low / maxFps.value
  const cap = avg === null ? pct : Math.min(pct, avg / maxFps.value)
  return `${Math.max(0, cap) * 100}%`
}
</script>

<template>
  <figure class="rounded-xl border border-slate-200 bg-surface p-4 sm:p-5">
    <figcaption class="sr-only">
      نمودار مقایسهای میانگین و حداقل فریمریت محصولات، به تفکیک بازی و رزولوشن
    </figcaption>

    <!-- Legend: which colour belongs to which product. -->
    <ul class="mb-5 flex flex-wrap gap-x-5 gap-y-2">
      <li
        v-for="item in series"
        :key="item.slug"
        class="flex items-center gap-2 text-xs text-slate-600"
      >
        <span
          class="inline-block h-3 w-3 shrink-0 rounded-sm"
          :style="{ backgroundColor: colorForSlug(item.slug) }"
          aria-hidden="true"
        />
        <span class="max-w-56 truncate" :title="item.title">{{ item.title }}</span>
      </li>
    </ul>

    <div class="space-y-6">
      <div v-for="group in groups" :key="group.key">
        <div class="mb-2 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <h3 class="text-sm font-semibold text-slate-900">{{ group.label }}</h3>
          <span v-if="group.meta" dir="ltr" class="text-xs text-slate-500">{{ group.meta }}</span>
        </div>

        <ul class="space-y-2">
          <li
            v-for="bar in group.bars"
            :key="bar.slug"
            class="flex items-center gap-3"
            :aria-label="`${titleBySlug.get(bar.slug) ?? bar.slug}: میانگین ${formatFps(bar.avg)}، حداقل ${formatFps(bar.low)} فریم بر ثانیه`"
          >
            <span
              class="w-20 shrink-0 truncate text-xs text-slate-500 sm:w-28"
              :title="titleBySlug.get(bar.slug)"
            >
              {{ titleBySlug.get(bar.slug) ?? bar.slug }}
            </span>

            <div class="relative h-5 flex-1 overflow-hidden rounded-md bg-slate-100">
              <!-- The average: a translucent bar on the shared scale. -->
              <div
                class="absolute inset-y-0 start-0 rounded-md opacity-30"
                :style="{ width: avgWidth(bar.avg), backgroundColor: colorForSlug(bar.slug) }"
              />
              <!-- The 1% low: the solid core, so the floor is readable at a glance. -->
              <div
                class="absolute inset-y-0 start-0 rounded-md"
                :style="{ width: lowWidth(bar.avg, bar.low), backgroundColor: colorForSlug(bar.slug) }"
              />
            </div>

            <span class="w-16 shrink-0 text-end text-xs sm:w-20">
              <span class="font-semibold text-slate-900">{{ formatFps(bar.avg) }}</span>
              <span class="block text-[10px] text-slate-500">کمینه {{ formatFps(bar.low) }}</span>
            </span>
          </li>
        </ul>
      </div>
    </div>

    <p class="mt-4 text-[11px] leading-5 text-slate-400">
      نوار کمرنگ = میانگین فریمریت؛ هستهٔ پررنگ = ۱٪ کمینه. همهٔ نوارها یک مقیاس دارند
      (بلندترین = بیشترین فریمریت)، پس نوار بلندتر همیشه یعنی فریم بیشتر.
    </p>
  </figure>
</template>
