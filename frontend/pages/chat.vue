<script setup lang="ts">
const { messages, streaming, send, reset } = useChat()

const question = ref("")

const suggestions = [
  "بهترین سیستم گیمینگ برای 1080p کدام است؟",
  "سوکت پردازنده رایزن ۷ ۸۰۰۰X3D چیست؟",
  "حافظه DDR5 چیست؟",
  "قیمت کارت گرافیک RTX 4070 SUPER چقدر است؟",
]

async function ask(text: string) {
  if (!text.trim()) return
  question.value = ""
  await send(text)
}

useSeoMeta({
  title: "دستیار هوشمند | تک‌بیس",
  description: "پرسش خود را به فارسی بپرسید و پاسخِ با استناد بگیرید.",
})
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <h1 class="mb-1 text-2xl font-bold">دستیار هوشمند</h1>
    <p class="mb-6 text-sm text-slate-500">
      پاسخ‌ها فقط از ابزارها و مستندات فروشگاه ساخته می‌شوند و هر ادعا ارجاع دارد.
    </p>

    <div v-if="messages.length === 0" class="rounded-xl border border-dashed border-slate-300 p-8">
      <p class="mb-4 text-center text-slate-500">یکی از این سؤال‌ها را بپرسید:</p>
      <div class="flex flex-col gap-2">
        <button
          v-for="suggestion in suggestions"
          :key="suggestion"
          class="rounded-lg border border-slate-200 bg-surface px-4 py-2.5 text-start text-sm hover:border-brand-300 hover:bg-brand-50"
          @click="ask(suggestion)"
        >
          {{ suggestion }}
        </button>
      </div>
    </div>

    <div v-else class="space-y-5">
      <div
        v-for="(message, index) in messages"
        :key="index"
        class="rounded-xl border p-4"
        :class="
          message.role === 'user'
            ? 'border-brand-200 bg-brand-50/60'
            : 'border-slate-200 bg-surface'
        "
      >
        <p class="mb-1 text-xs font-semibold text-slate-400">
          {{ message.role === "user" ? "شما" : "دستیار" }}
        </p>

        <p v-if="message.error" class="text-sm text-rose-600">{{ message.error }}</p>

        <p v-else-if="message.clarifyingQuestion" class="leading-8 text-slate-800">
          {{ message.clarifyingQuestion }}
        </p>

        <p v-else class="whitespace-pre-line leading-8 text-slate-800">
          {{ message.text }}
          <span v-if="message.pending" class="inline-block w-1.5 animate-pulse bg-slate-400" />
        </p>

        <ProductCardsRow v-if="message.cards?.length" :cards="message.cards" />

        <div v-if="message.citations?.length" class="mt-4 border-t border-slate-100 pt-3">
          <p class="mb-2 text-xs font-medium text-slate-500">منابع:</p>
          <ul class="space-y-1">
            <li v-for="citation in message.citations" :key="citation.index" class="text-sm">
              <a
                :href="citation.url"
                class="text-brand-700 underline underline-offset-2 hover:text-brand-800"
              >
                [{{ citation.index }}] {{ citation.page_title }}
              </a>
              <span v-if="citation.section_path" class="text-slate-500">
                › {{ citation.section_path }}
              </span>
            </li>
          </ul>
        </div>

        <p
          v-if="message.guardrails && message.guardrails.ok === false"
          class="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700"
        >
          این پاسخ از نظر استناد یا صحت داده تأیید نشد.
        </p>
      </div>

      <button
        class="text-sm text-slate-500 underline underline-offset-2 hover:text-slate-700"
        @click="reset()"
      >
        شروع دوباره
      </button>
    </div>

    <form class="search-shell mt-6 flex items-center gap-2 p-2" @submit.prevent="ask(question)">
      <input
        v-model="question"
        type="text"
        placeholder="سؤال خود را بنویسید…"
        class="search-field min-w-0 flex-1 rounded-xl px-4 py-3 text-base"
        :disabled="streaming"
      />
      <button
        type="submit"
        class="search-submit shrink-0 rounded-xl px-5 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        :disabled="streaming || !question.trim()"
      >
        {{ streaming ? "در حال پاسخ…" : "بپرس" }}
      </button>
    </form>
  </div>
</template>
