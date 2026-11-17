<script setup lang="ts">
/**
 * A shared, user-facing notice for a failed API request.
 *
 * It is deliberately presentational: the caller owns the request and decides
 * when there is an error, and can re-run it from the retry event. It never
 * shows a raw error, a status code or a stack trace — only a plain Persian
 * message and one retry action.
 */
const props = withDefaults(
  defineProps<{
    /** Show the loading state instead of the error. */
    pending?: boolean
    title?: string
    message?: string
  }>(),
  {
    pending: false,
    title: "ارتباط با سرور برقرار نشد",
    message:
      "اطلاعات از سرور دریافت نشد. ممکن است اتصال اینترنت یا سرویس موقتاً در دسترس نباشد؛ می‌توانید دوباره تلاش کنید.",
  },
)

defineEmits<{ retry: [] }>()
</script>

<template>
  <div
    v-if="props.pending"
    class="rounded-xl border border-slate-200 bg-surface p-4 text-sm text-slate-500"
    role="status"
    aria-live="polite"
  >
    در حال دریافت اطلاعات...
  </div>

  <div
    v-else
    class="flex flex-col gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 sm:flex-row sm:items-center sm:justify-between"
    role="alert"
  >
    <div class="min-w-0">
      <p class="font-semibold text-rose-700">{{ props.title }}</p>
      <p class="mt-1 text-sm leading-7 text-rose-700/90">{{ props.message }}</p>
    </div>
    <button
      type="button"
      class="btn-primary shrink-0"
      @click="$emit('retry')"
    >
      تلاش مجدد
    </button>
  </div>
</template>
