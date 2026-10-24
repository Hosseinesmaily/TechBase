<script setup lang="ts">
import type { WikiPage } from "~/types/wiki"
import { formatDate, formatPrice } from "~/utils/format"

const route = useRoute()
const slug = computed(() => String(route.params.slug))

const { data: page, error } = await useFetch<WikiPage>(
  () => `/api/v1/wiki/pages/${slug.value}/`,
  {
    server: true,
    key: `wiki-page-${slug.value}`,
    default: () => null,
  },
)

if (error.value) {
  throw createError({ statusCode: 404, statusMessage: "این صفحه پیدا نشد" })
}

useSeoMeta({
  title: () => page.value?.title ?? "ویکی",
  description: () => page.value?.summary ?? "",
  ogTitle: () => page.value?.title ?? "ویکی",
  ogDescription: () => page.value?.summary ?? "",
  ogType: "article",
})

/** schema.org structured data, so search engines can render the page richly. */
const siteUrl = useRequestURL().origin
const ENTITY_TYPE_LABELS: Record<string, string> = {
  cpu: "پردازنده",
  gpu: "کارت گرافیک",
  motherboard: "مادربرد",
  ram: "حافظهٔ رم",
  psu: "پاور",
  case: "کیس",
  cooler: "خنک‌کننده",
  ssd: "حافظهٔ SSD",
  prebuilt: "سیستم آماده",
  concept: "مفهوم سخت‌افزاری",
}

useHead(() => ({
  script: page.value
    ? [
        {
          type: "application/ld+json",
          innerHTML: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Article",
            headline: page.value.title,
            description: page.value.summary,
            inLanguage: "fa",
            datePublished: page.value.last_updated,
            dateModified: page.value.last_updated,
            mainEntityOfPage: {
              "@type": "WebPage",
              "@id": `${siteUrl}/wiki/${page.value.slug}/`,
            },
            ...(page.value.entity
              ? {
                  about: {
                    "@type": "Product",
                    name: page.value.entity.title,
                    ...(page.value.recommended_products?.[0]
                      ? {
                          offers: {
                            "@type": "Offer",
                            price: page.value.recommended_products[0].price,
                            priceCurrency: "IRT",
                            availability: page.value.recommended_products[0].in_stock
                              ? "https://schema.org/InStock"
                              : "https://schema.org/OutOfStock",
                          },
                        }
                      : {}),
                  },
                }
              : {}),
          }),
        },
      ]
    : [],
}))

/**
 * Turn the plain body text into segments so entity names can be rendered as
 * hover-card links. The backend already computed which entity each mention
 * belongs to (the `links` array), so we match the surface text against them.
 */
interface Segment {
  text: string
  entitySlug?: string
  red?: boolean
}

const segments = computed<Segment[]>(() => {
  if (!page.value) return []
  const links = page.value.links ?? []
  if (!links.length) return []

  // The auto-linker stores the surface text of each mention; find them in the
  // body text and mark them.
  const mentions = links
    .filter((link) => link.text)
    .sort((a, b) => b.text.length - a.text.length)

  const out: Segment[] = []
  const seen = new Set<string>()

  for (const link of mentions) {
    if (seen.has(link.text)) continue
    seen.add(link.text)
    out.push({
      text: link.text,
      entitySlug: link.target_slug,
      red: !link.target_exists,
    })
  }
  return out
})

/** Split a text block into plain and linked segments. */
function splitText(text: string): Segment[] {
  if (!segments.value.length) return [{ text }]

  // Sort by length (longest first) so "RTX 4070 SUPER" wins over "4070".
  const ordered = [...segments.value].sort((a, b) => b.text.length - a.text.length)
  const result: Segment[] = []
  let rest = text

  while (rest.length) {
    let best: { index: number; segment: Segment } | null = null

    for (const segment of ordered) {
      const index = rest.indexOf(segment.text)
      if (index === -1) continue
      // Only match on a word boundary so "4060" does not match inside "40601".
      const before = index > 0 ? rest[index - 1] : " "
      const afterIndex = index + segment.text.length
      const after = afterIndex < rest.length ? rest[afterIndex] : " "
      if (/[\w‌‍]/.test(before) || /[\w‌‍]/.test(after)) continue
      if (!best || index < best.index) best = { index, segment }
    }

    if (!best) {
      result.push({ text: rest })
      break
    }

    if (best.index > 0) result.push({ text: rest.slice(0, best.index) })
    result.push(best.segment)
    rest = rest.slice(best.index + best.segment.text.length)
  }

  return result
}
</script>

<template>
  <article v-if="page" class="max-w-3xl">
    <nav class="mb-4 text-sm text-slate-500" aria-label="مسیر">
      <NuxtLink to="/" class="hover:text-slate-900">خانه</NuxtLink>
      <span class="mx-1">/</span>
      <NuxtLink to="/wiki" class="hover:text-slate-900">ویکی</NuxtLink>
      <span class="mx-1">/</span>
      <span class="text-slate-700"><BidiText :text="page.title" /></span>
    </nav>

    <header class="mb-6">
      <h1 class="text-3xl font-bold leading-snug"><BidiText :text="page.title" /></h1>
      <p v-if="page.summary" class="mt-2 text-slate-600"><BidiText :text="page.summary" /></p>

      <div class="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span v-if="page.entity" class="rounded-full bg-brand-50 px-2.5 py-1 text-brand-700">
          {{ ENTITY_TYPE_LABELS[page.entity.type] ?? "قطعه" }}
        </span>
        <span v-if="page.review_by">بازبینی: {{ formatDate(page.review_by) }}</span>
        <span v-if="page.is_stale" class="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
          محتوای قدیمی
        </span>
      </div>
    </header>

    <dl
      v-if="page.use_case || page.resolution || page.budget_max"
      class="mb-6 grid grid-cols-3 gap-3 rounded-xl border border-slate-200 bg-surface p-4 text-sm"
    >
      <div v-if="page.use_case">
        <dt class="text-xs text-slate-500">کاربرد</dt>
        <dd class="mt-0.5 font-medium">{{ page.use_case }}</dd>
      </div>
      <div v-if="page.resolution">
        <dt class="text-xs text-slate-500">رزولوشن</dt>
        <dd class="mt-0.5 font-medium" dir="ltr">{{ page.resolution }}</dd>
      </div>
      <div v-if="page.budget_max">
        <dt class="text-xs text-slate-500">بودجه</dt>
        <dd class="mt-0.5 font-medium">{{ formatPrice(page.budget_max) }}</dd>
      </div>
    </dl>

    <section
      v-if="page.recommended_products && page.recommended_products.length"
      class="mb-8"
    >
      <h2 class="mb-3 text-lg font-semibold">پیشنهادها</h2>
      <ol class="space-y-2">
        <li
          v-for="(product, index) in page.recommended_products"
          :key="product.sku"
          class="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-surface px-4 py-3"
        >
          <span class="flex items-center gap-3">
            <span
              class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700"
            >
              {{ index + 1 }}
            </span>
            <span class="font-medium"><BidiText :text="product.title" /></span>
            <span
              v-if="!product.in_stock"
              class="rounded-full bg-rose-50 px-2 py-0.5 text-xs text-rose-600"
            >
              ناموجود
            </span>
          </span>
          <span class="shrink-0 font-bold">{{ formatPrice(product.price) }}</span>
        </li>
      </ol>
    </section>

    <div class="wiki-body space-y-4">
      <template v-for="(block, index) in page.body ?? []" :key="index">
        <h2
          v-if="block.type === 'heading' && block.level === 'h2'"
          :id="block.id"
          class="mt-8 text-xl font-semibold scroll-mt-20"
        >
          <BidiText :text="block.text ?? ''" />
        </h2>

        <h3
          v-else-if="block.type === 'heading' && block.level === 'h3'"
          :id="block.id"
          class="mt-6 text-lg font-semibold scroll-mt-20"
        >
          <BidiText :text="block.text ?? ''" />
        </h3>

        <h4
          v-else-if="block.type === 'heading'"
          :id="block.id"
          class="mt-5 font-semibold scroll-mt-20"
        >
          <BidiText :text="block.text ?? ''" />
        </h4>

        <p v-else-if="block.type === 'paragraph'" class="leading-8 text-slate-700">
          <template v-for="(segment, sIndex) in splitText(block.text ?? '')" :key="sIndex">
            <EntityLink
              v-if="segment.entitySlug"
              :slug="segment.entitySlug"
              :text="segment.text"
              :red="segment.red"
            />
            <BidiText v-else :text="segment.text" />
          </template>
        </p>

        <ul
          v-else-if="block.type === 'list' && block.style !== 'ol'"
          class="list-disc space-y-1 ps-6 text-slate-700"
        >
          <li v-for="(item, i) in block.items ?? []" :key="i" class="leading-8">
            <BidiText :text="item" />
          </li>
        </ul>

        <ol
          v-else-if="block.type === 'list'"
          class="list-decimal space-y-1 ps-6 text-slate-700"
        >
          <li v-for="(item, i) in block.items ?? []" :key="i" class="leading-8">
            <BidiText :text="item" />
          </li>
        </ol>

        <blockquote
          v-else-if="block.type === 'quote'"
          class="border-s-4 border-brand-300 bg-brand-50/50 px-4 py-3 text-slate-700"
        >
          <p class="leading-8"><BidiText :text="block.text ?? ''" /></p>
          <cite v-if="block.source" class="mt-1 block text-xs text-slate-500">
            <BidiText :text="block.source" />
          </cite>
        </blockquote>

        <aside
          v-else-if="block.type === 'callout'"
          class="rounded-lg border p-4"
          :class="{
            'border-sky-200 bg-sky-50': block.kind === 'info',
            'border-amber-200 bg-amber-50': block.kind === 'warning' || block.kind === 'tip',
            'border-rose-200 bg-rose-50': block.kind === 'danger',
          }"
        >
          <p v-if="block.title" class="mb-1 font-semibold"><BidiText :text="block.title" /></p>
          <p class="text-sm leading-7 text-slate-700"><BidiText :text="block.text ?? ''" /></p>
        </aside>

        <table
          v-else-if="block.type === 'spec_table'"
          class="w-full overflow-hidden rounded-lg border border-slate-200 text-sm"
        >
          <tbody>
            <tr
              v-for="(row, rIndex) in block.rows ?? []"
              :key="rIndex"
              class="border-b border-slate-100 last:border-0 even:bg-slate-50/60"
            >
              <th scope="row" class="w-1/2 px-4 py-2.5 text-start font-medium text-slate-600">
                <BidiText :text="row.label" />
              </th>
              <td class="px-4 py-2.5 text-slate-900"><BidiText :text="row.value" /></td>
            </tr>
          </tbody>
        </table>

        <figure v-else-if="block.type === 'image' && block.url">
          <img :src="block.url" :alt="block.caption" class="rounded-lg" loading="lazy" />
          <figcaption v-if="block.caption" class="mt-1 text-center text-xs text-slate-500">
            <BidiText :text="block.caption" />
          </figcaption>
        </figure>

        <p v-else-if="block.type === 'related_entity'" class="text-sm">
          <EntityLink
            :slug="block.entity_slug ?? ''"
            :text="block.entity_slug ?? ''"
          />
          <span v-if="block.note" class="ms-2 text-slate-500"><BidiText :text="block.note" /></span>
        </p>
      </template>
    </div>

    <footer class="mt-10 border-t border-slate-200 pt-4 text-xs text-slate-400">
      آخرین انتشار: {{ formatDate(page.last_updated) }}
    </footer>
  </article>
</template>
