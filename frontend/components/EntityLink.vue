<script setup lang="ts">
/** A consistently styled wiki link; catalog entities remain reachable as fallbacks. */

const props = defineProps<{
  slug: string
  text: string
  /** True when the entity has no published wiki page yet. */
  red?: boolean
}>()
</script>

<template>
  <NuxtLink
    :to="props.red ? `/entity/${props.slug}/` : `/wiki/${props.slug}/`"
    class="entity-link"
    :data-entity="props.slug"
  >
    <BidiText :text="props.text" />
  </NuxtLink>
</template>

<style scoped>
.entity-link {
  color: rgb(29 78 216);
  text-decoration: underline;
  text-underline-offset: 3px;
  text-decoration-thickness: 1px;
}

</style>
