<script setup lang="ts">
/**
 * A link to a catalog entity, with a hover card.
 *
 * The hover card is fetched lazily on hover and shows the price, the stock and
 * the key specs — all straight from the catalog, so it can never contradict
 * the shop. Entities without a wiki page render as a red link.
 */
import type { HoverCard } from "~/types/wiki"
import { formatPrice } from "~/utils/format"

const props = defineProps<{
  slug: string
  text: string
  /** True when the entity has no wiki page yet (a red link). */
  red?: boolean
}>()

const card = ref<HoverCard | null>(null)
const loading = ref(false)
const show = ref(false)
let fetched = false

async function fetchCard() {
  if (fetched || loading.value) return
  fetched = true
  loading.value = true
  try {
    card.value = await $fetch<HoverCard>("/api/v1/linking/hovercard/", {
      query: { entity: props.slug },
    })
  } catch {
    card.value = null
  } finally {
    loading.value = false
  }
}

function onEnter() {
  show.value = true
  void fetchCard()
}
</script>

<template>
  <span class="relative inline-block">
    <a
      :href="props.red ? `/wiki/${props.slug}/` : `/entity/${props.slug}/`"
      class="entity-link"
      :class="{ 'entity-link--red': props.red }"
      :data-entity="props.slug"
      @mouseenter="onEnter"
      @focus="onEnter"
    >
      <slot>{{ props.text }}</slot>
    </a>

    <Transition name="fade">
      <div
        v-if="show"
        class="hover-card"
        role="tooltip"
        @mouseleave="show = false"
      >
        <p v-if="loading" class="text-xs text-slate-400">در حال بارگذاری…</p>

        <template v-else-if="card">
          <p class="hover-card__title">{{ card.entity.title }}</p>
          <p v-if="card.entity.brand" class="text-xs text-slate-500">
            {{ card.entity.brand }}
          </p>

          <p v-if="card.product" class="mt-2 font-bold text-slate-900">
            {{ formatPrice(card.product.price, card.product.currency) }}
            <span
              class="text-xs font-normal"
              :class="card.product.in_stock ? 'text-emerald-600' : 'text-rose-500'"
            >
              {{ card.product.in_stock ? `موجود (${card.product.stock})` : "ناموجود" }}
            </span>
          </p>

          <dl v-if="card.specs.length" class="mt-2 space-y-0.5">
            <div v-for="spec in card.specs" :key="spec.key" class="flex gap-2 text-xs">
              <dt class="text-slate-500">{{ spec.label }}:</dt>
              <dd class="text-slate-800" dir="ltr">{{ spec.value }}</dd>
            </div>
          </dl>

          <p v-if="!card.has_page" class="mt-2 text-xs text-amber-600">
            این صفحه هنوز نوشته نشده است.
          </p>
        </template>

        <p v-else class="text-xs text-slate-400">اطلاعاتی موجود نیست.</p>
      </div>
    </Transition>
  </span>
</template>

<style scoped>
.entity-link {
  color: rgb(29 78 216);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
}

.entity-link--red {
  color: rgb(180 83 9);
  text-decoration-style: dotted;
}

.hover-card {
  position: absolute;
  z-index: 50;
  inset-inline-start: 0;
  top: 100%;
  margin-top: 0.375rem;
  width: 17rem;
  border: 1px solid rgb(226 232 240);
  border-radius: 0.5rem;
  background: white;
  padding: 0.75rem;
  box-shadow: 0 10px 25px -12px rgb(0 0 0 / 0.25);
  text-align: start;
}

.hover-card__title {
  font-weight: 600;
  line-height: 1.4;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.12s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
