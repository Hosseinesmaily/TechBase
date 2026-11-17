<script setup lang="ts">
import type { TicketSummary } from "~/types/support"
import { TICKET_STATUS_CLASS, TICKET_STATUSES } from "~/types/support"
import { formatDate } from "~/utils/format"

/**
 * One ticket thread, shared by the customer's panel and the staff workspace.
 *
 * The component never decides access: `canChangeStatus` only reflects what the
 * person may do, and the API refuses the rest on the server either way.
 */
const props = withDefaults(
  defineProps<{
    ticket: TicketSummary
    submitReply: (body: string) => Promise<void>
    submitStatus?: (status: string) => Promise<void>
    /** Closes the detail view only. Supplied by the page that renders the thread. */
    closeView?: () => void
    canChangeStatus?: boolean
  }>(),
  { canChangeStatus: false, submitStatus: undefined, closeView: undefined },
)

const draft = ref("")
const localError = ref("")
const sending = ref(false)
/** Feedback for the status action, shown inside the thread so a click is never silent. */
const statusNotice = ref("")
const statusError = ref("")

async function send() {
  const body = draft.value.trim()
  if (!body) {
    localError.value = "متن پاسخ را بنویسید."
    return
  }
  localError.value = ""
  sending.value = true
  try {
    await props.submitReply(body)
    draft.value = ""
  } catch {
    // The page keeps the server's message; the draft stays so nothing is lost.
  } finally {
    sending.value = false
  }
}

async function move(status: string) {
  if (!props.submitStatus) return
  localError.value = ""
  statusNotice.value = ""
  statusError.value = ""
  sending.value = true
  try {
    await props.submitStatus(status)
    const label = TICKET_STATUSES.find((option) => option.value === status)?.label ?? status
    statusNotice.value = `وضعیت تیکت به «${label}» تغییر کرد.`
  } catch (error) {
    // Inline, next to the buttons: a failed click must not look like a no-op.
    statusError.value = error instanceof Error ? error.message : "تغییر وضعیت انجام نشد."
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <article class="rounded-xl border border-slate-200 bg-surface">
    <header class="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 p-4">
      <div class="min-w-0">
        <h3 class="font-semibold leading-7">{{ props.ticket.subject }}</h3>
        <p class="mt-1 text-xs text-slate-500">
          ثبتشده در {{ formatDate(props.ticket.created_at) }} ·
          {{ props.ticket.message_count }} پیام
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2">
        <span
          class="shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium"
          :class="TICKET_STATUS_CLASS[props.ticket.status] ?? TICKET_STATUS_CLASS.open"
        >
          {{ props.ticket.status_label }}
        </span>
        <!--
          Closing the *conversation* lives here and is deliberately separate from
          the ticket status below: it only hides this panel and sends no request.
        -->
        <button
          v-if="props.closeView"
          type="button"
          class="min-h-8 rounded-lg border border-slate-200 px-2.5 text-xs text-slate-500 transition-colors hover:border-brand-300 hover:text-brand-700"
          @click="props.closeView()"
        >
          بستن گفت‌وگو
        </button>
      </div>
    </header>

    <ul class="space-y-3 p-4">
      <li
        v-for="message in props.ticket.messages ?? []"
        :key="message.id"
        class="rounded-lg border p-3"
        :class="message.from_staff ? 'border-emerald-200 bg-emerald-50/60' : 'border-slate-200 bg-slate-50'"
      >
        <p class="mb-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <span class="font-semibold" :class="message.from_staff ? 'text-emerald-700' : 'text-slate-700'">
            {{ message.from_staff ? "تیم پشتیبانی" : "شما" }}
          </span>
          <span>{{ formatDate(message.created_at) }}</span>
        </p>
        <p class="whitespace-pre-line text-sm leading-7 text-slate-700">{{ message.body }}</p>
      </li>
    </ul>

    <div v-if="props.canChangeStatus" class="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 pt-3">
      <span class="text-xs text-slate-500">تغییر وضعیت:</span>
      <button
        v-for="option in TICKET_STATUSES"
        :key="option.value"
        type="button"
        class="min-h-9 rounded-lg border px-3 text-xs transition-colors"
        :class="
          props.ticket.status === option.value
            ? 'border-brand-300 bg-brand-50 font-semibold text-brand-700'
            : 'border-slate-200 text-slate-600 hover:border-brand-300'
        "
        :disabled="sending"
        :aria-pressed="props.ticket.status === option.value"
        @click="move(option.value)"
      >
        {{ option.label }}
      </button>
      <button
        v-if="props.ticket.status !== 'closed'"
        type="button"
        class="min-h-9 rounded-lg border border-rose-500/40 px-3 text-xs text-rose-200 transition-colors hover:bg-rose-500/10 disabled:opacity-50"
        title="وضعیت تیکت را به «بسته» تغییر می‌دهد؛ بستن گفت‌وگو وضعیت را تغییر نمی‌دهد."
        :disabled="sending"
        @click="move('closed')"
      >
        بستن تیکت
      </button>
    </div>

    <p v-if="statusNotice" class="px-4 pb-1 text-xs text-emerald-300">{{ statusNotice }}</p>
    <p v-if="statusError" class="px-4 pb-1 text-xs text-rose-300">{{ statusError }}</p>

    <form class="border-t border-slate-100 p-4" @submit.prevent="send">
      <p v-if="props.ticket.status === 'closed'" class="mb-2 text-xs text-amber-700">
        این تیکت بسته است؛ ارسال پاسخ تازه آن را دوباره باز می‌کند.
      </p>
      <label class="form-label" :for="`ticket-reply-${props.ticket.id}`">
        {{ props.canChangeStatus ? "پاسخ به کاربر" : "پیام تازه در این تیکت" }}
      </label>
      <textarea
        :id="`ticket-reply-${props.ticket.id}`"
        v-model="draft"
        class="form-field mt-1 min-h-24"
        maxlength="4000"
        placeholder="پاسخ خود را بنویسید..."
      />
      <p v-if="localError" class="mt-2 text-xs text-rose-700">{{ localError }}</p>
      <button type="submit" class="btn-primary mt-3" :disabled="sending">
        {{ sending ? "در حال ثبت..." : "ثبت پاسخ" }}
      </button>
    </form>
  </article>
</template>
