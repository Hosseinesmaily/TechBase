<script setup lang="ts">
/** Isolate Latin model names and ASCII numbers inside Persian RTL text. */
const props = defineProps<{ text: string }>()
const baseDirection = computed(() =>
  /[؀-ۿݐ-ݿࢠ-ࣿ]/u.test(props.text) ? "rtl" : "ltr",
)

const parts = computed(() => {
  const result: Array<{ text: string; latin: boolean }> = []
  const matcher = /[A-Za-z0-9][A-Za-z0-9._+\/-]*(?:\s+[A-Za-z0-9][A-Za-z0-9._+\/-]*)*/g
  let offset = 0

  for (const match of props.text.matchAll(matcher)) {
    const index = match.index ?? 0
    if (index > offset) result.push({ text: props.text.slice(offset, index), latin: false })
    result.push({ text: match[0], latin: true })
    offset = index + match[0].length
  }

  if (offset < props.text.length) result.push({ text: props.text.slice(offset), latin: false })
  return result
})
</script>

<template>
  <span :dir="baseDirection" class="bidi-text">
    <bdi v-for="(part, index) in parts" :key="index" :dir="part.latin ? 'ltr' : 'auto'">
      {{ part.text }}
    </bdi>
  </span>
</template>

<style scoped>
.bidi-text {
  unicode-bidi: isolate;
}
</style>
