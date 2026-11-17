<script setup lang="ts">
import type { AccountResponse } from "~/types/account"
import type { Paginated, Product } from "~/types/catalog"
import type { TicketSummary } from "~/types/support"
import { TICKET_STATUS_CLASS, TICKET_STATUSES } from "~/types/support"
import type { WikiPage } from "~/types/wiki"
import { formatDate } from "~/utils/format"

/**
 * The staff workspace: wiki articles and support tickets, in one place.
 *
 * The page only *offers* the door — every action it triggers is checked again on
 * the server (`IsAdminUser`, and the ticket endpoints scope their queryset to the
 * requester). Hiding the panel from a non-staff visitor has never been the
 * control; refusing the request is.
 */
interface AdminLinks {
  explorer: string
  wiki_root: string
  images: string
  documents: string
  tickets: string
  new_page: Record<string, string>
}

const account = useAccount()
const support = useSupport()
const adminBase = computed(() =>
  String(useRuntimeConfig().public.adminBaseUrl || "").replace(/\/+$/, ""),
)
const isStaff = computed(() => Boolean(account.user.value?.is_staff))

const wikiQuery = ref("")
const wikiType = ref("")
const ticketFilter = ref("")
const notice = ref("")

/**
 * The panel's two workspaces, in the same tab-bar shape as the site navigation.
 * Switching tabs only changes what is rendered — the data is loaded once.
 */
const panelTab = ref<"wiki" | "tickets">("wiki")
const PANEL_TABS = computed(() => [
  { key: "wiki" as const, label: "مدیریت ویکی", count: pages.value?.count ?? 0 },
  {
    key: "tickets" as const,
    label: "تیکتهای کاربران",
    count: support.allTickets.value.length,
  },
])

// --- image upload (wiki article image / product image) ---
const uploadTarget = ref("")
const uploadFile = ref<File | null>(null)
const uploadPending = ref(false)
const uploadError = ref("")
const uploadNotice = ref("")

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  uploadFile.value = input.files?.[0] ?? null
  uploadError.value = ""
  uploadNotice.value = ""
}

async function submitUpload() {
  uploadError.value = ""
  uploadNotice.value = ""
  if (!uploadTarget.value) {
    uploadError.value = "ابتدا مقصد تصویر را انتخاب کن."
    return
  }
  if (!uploadFile.value) {
    uploadError.value = "فایلی انتخاب نشده است."
    return
  }
  const form = new FormData()
  form.append("file", uploadFile.value)
  const [kind, value] = uploadTarget.value.split(":", 2)
  if (kind === "page") form.append("page", value ?? "")
  else form.append("sku", value ?? "")

  uploadPending.value = true
  try {
    const result = await account.request<{ attached_to?: string; url?: string } & AccountResponse>(
      "/api/v1/admin/images/",
      { method: "POST", body: form },
    )
    uploadNotice.value = result.attached_to
      ? `تصویر بارگذاری و به ${result.attached_to} وصل شد.`
      : "تصویر بارگذاری شد."
    uploadFile.value = null
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : "بارگذاری تصویر انجام نشد."
  } finally {
    uploadPending.value = false
  }
}

/** The products an upload can target. The newest 50 are enough for the panel. */
const { data: products, refresh: refreshProducts } = await useAsyncData<Paginated<Product>>(
  "admin-products",
  () => $fetch<Paginated<Product>>("/api/v1/catalog/products/", { query: { page_size: "50" } }),
  {
    server: false,
    immediate: false,
    default: () => ({ count: 0, next: null, previous: null, results: [] }),
  },
)

/** The destinations the panel offers: wiki articles and products. */
const uploadTargets = computed(() => [
  ...wikiResults.value.map((page) => ({ value: `page:${page.id}`, label: `مقاله: ${page.title}` })),
  ...(products.value?.results ?? []).map((product) => ({
    value: `sku:${product.sku}`,
    label: `محصول: ${product.display_title}`,
  })),
])

useSeoMeta({
  title: "پنل مدیریت | تکبیس",
  description: "مدیریت مقالههای ویکی و پاسخ به تیکتهای کاربران.",
  robots: "noindex, nofollow",
})

/** The CMS addresses come from the backend, which knows the CMS. */
const {
  data: links,
  refresh: refreshLinks,
} = await useFetch<AdminLinks>("/api/v1/wiki/admin-links/", {
  server: false,
  immediate: false,
  default: () => null,
})

const {
  data: pages,
  pending: pagesPending,
  error: pagesError,
  refresh: refreshPages,
} = await useAsyncData<Paginated<WikiPage>>(
  "admin-wiki-pages",
  () =>
    $fetch<Paginated<WikiPage>>("/api/v1/wiki/pages/", {
      query: {
        ...(wikiType.value ? { type: wikiType.value } : {}),
        ...(wikiQuery.value.trim() ? { q: wikiQuery.value.trim() } : {}),
        page_size: "50",
      },
    }),
  {
    server: false,
    immediate: false,
    watch: [wikiQuery, wikiType],
    default: () => ({ count: 0, next: null, previous: null, results: [] }),
  },
)

const wikiResults = computed(() => pages.value?.results ?? [])

const PAGE_TYPES = [
  { value: "", label: "همهٔ مقالهها" },
  { value: "component", label: "قطعات" },
  { value: "guide", label: "راهنمای خرید" },
  { value: "concept", label: "مفاهیم" },
]

const TYPE_LABELS: Record<string, string> = {
  ComponentPage: "قطعه",
  BuyerGuidePage: "راهنمای خرید",
  ConceptPage: "مفهوم",
}

const NEW_PAGE_TYPES = [
  { key: "component", label: "مقالهٔ قطعه" },
  { key: "guide", label: "راهنمای خرید" },
  { key: "concept", label: "مقالهٔ مفهوم" },
]

async function loadWorkspace() {
  if (!isStaff.value) return
  await Promise.all([
    refreshPages().catch(() => undefined),
    refreshLinks().catch(() => undefined),
    refreshProducts().catch(() => undefined),
    support.loadAll().catch(() => undefined),
  ])
}

onMounted(async () => {
  try {
    await account.initialize()
  } catch {
    // The gate below explains the state; nothing else can be done offline.
  }
  await loadWorkspace()
})

/** Ticket counts and the visible list are computed from the loaded set. */
const ticketCounts = computed(() => {
  const counts: Record<string, number> = {}
  for (const ticket of support.allTickets.value) {
    counts[ticket.status] = (counts[ticket.status] ?? 0) + 1
  }
  return counts
})

const visibleTickets = computed(() =>
  ticketFilter.value
    ? support.allTickets.value.filter((ticket) => ticket.status === ticketFilter.value)
    : support.allTickets.value,
)

/** `adminUrl` prefixes a CMS path with the origin the admin is published on. */
function adminUrl(path: string | undefined): string {
  if (!path) return "#"
  return `${adminBase.value}${path}`
}

async function openTicket(ticket: TicketSummary) {
  notice.value = ""
  // Clicking a row toggles the conversation: the same ticket closes the panel,
  // a different one opens that ticket. This is pure view state — it never
  // changes the ticket's status (only the «بستن تیکت» button inside the thread
  // does, and a reply reopens a closed ticket).
  if (support.activeTicket.value?.id === ticket.id) {
    support.close()
    return
  }
  try {
    await support.open(ticket.id)
  } catch {
    // `support.error` carries the message.
  }
}

async function replyAsStaff(body: string) {
  const ticket = support.activeTicket.value
  if (!ticket) return
  await support.reply(ticket.id, body, { staff: true })
  notice.value = "پاسخ ثبت شد و در پنل کاربر نمایش داده میشود."
}

async function moveStatus(status: string) {
  const ticket = support.activeTicket.value
  if (!ticket) return
  const label = TICKET_STATUSES.find((item) => item.value === status)?.label ?? status
  await support.setStatus(ticket.id, status)
  notice.value = `وضعیت تیکت به «${label}» تغییر کرد.`
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-8">
    <header>
      <p class="text-sm font-semibold text-brand-700">ویژهٔ مدیران و تحریریه</p>
      <h1 class="mt-1 text-2xl font-bold">پنل مدیریت</h1>
      <p class="mt-2 text-sm leading-7 text-slate-500">
        این پنل دو کار دارد: مدیریت مقالههای ویکی و پاسخ به تیکتهای کاربران. دسترسی این
        بخش روی سرور بررسی میشود؛ درخواست بدون مجوز مدیریت پاسخ داده نمیشود.
      </p>
    </header>

    <section
      v-if="account.pending.value"
      class="rounded-xl border border-slate-200 bg-surface p-8 text-center text-sm text-slate-500"
    >
      در حال بررسی دسترسی...
    </section>

    <section v-else-if="!account.user.value" class="form-panel">
      <h2 class="font-bold">برای ورود به پنل، وارد حساب مدیر شو</h2>
      <p class="mt-2 text-sm leading-7 text-slate-500">
        این بخش فقط برای حسابهای دارای مجوز مدیریت فعال است.
      </p>
      <NuxtLink
        :to="{ path: '/account', query: { next: '/admin-panel' } }"
        class="btn-primary mt-4 inline-flex"
      >
        ورود به حساب
      </NuxtLink>
    </section>

    <section v-else-if="!isStaff" class="rounded-xl border border-amber-200 bg-amber-50 p-6">
      <h2 class="font-bold text-amber-700">این بخش در دسترس حساب شما نیست</h2>
      <p class="mt-2 text-sm leading-7 text-amber-700">
        حساب «<span dir="ltr">{{ account.user.value.email }}</span>» مجوز مدیریت ندارد. برای
        مدیریت محتوا یا پاسخ به تیکتها باید از حسابی با مجوز تحریریه استفاده کنی.
      </p>
      <NuxtLink to="/account" class="mt-3 inline-flex text-sm font-medium text-amber-700 underline">
        بازگشت به پنل من
      </NuxtLink>
    </section>

    <template v-else>
      <p v-if="notice" class="alert-success">{{ notice }}</p>
      <p v-if="support.error.value" class="alert-error">{{ support.error.value }}</p>

      <!-- The same tab-bar shape the site navigation uses. -->
      <nav
        class="flex flex-wrap gap-1 rounded-xl border border-slate-200 bg-surface p-1.5"
        aria-label="بخشهای پنل مدیریت"
      >
        <button
          v-for="tab in PANEL_TABS"
          :key="tab.key"
          type="button"
          class="rounded-lg px-3 py-2 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-600"
          :class="
            panelTab === tab.key
              ? 'bg-brand-50 font-semibold text-brand-700'
              : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
          "
          :aria-current="panelTab === tab.key ? 'page' : undefined"
          @click="panelTab = tab.key"
        >
          {{ tab.label }}
          <span class="text-xs opacity-80">({{ tab.count }})</span>
        </button>
      </nav>

      <template v-if="panelTab === 'wiki'">
      <section class="form-panel">
        <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div class="min-w-0">
            <h2 class="text-lg font-bold">مدیریت ویکی</h2>
            <p class="mt-1 text-sm leading-7 text-slate-500">
              مقالهٔ تازه بساز یا مقالهٔ موجود را در Wagtail ویرایش کن؛ پیشنویس تا زمان
              انتشار برای بازدیدکنندهها نمایش داده نمیشود.
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <a
              v-for="item in NEW_PAGE_TYPES"
              :key="item.key"
              :href="adminUrl(links?.new_page?.[item.key])"
              target="_blank"
              rel="noopener noreferrer"
              class="btn-secondary"
            >
              {{ item.label }}
            </a>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-[1fr_auto]">
          <input
            v-model="wikiQuery"
            type="search"
            class="form-field"
            placeholder="جستوجو در عنوان و خلاصهٔ مقالهها"
          />
          <select v-model="wikiType" class="form-field sm:w-56">
            <option v-for="option in PAGE_TYPES" :key="option.value" :value="option.value">
              {{ option.label }}
            </option>
          </select>
        </div>

        <ApiErrorNotice
          v-if="pagesError"
          class="mt-4"
          title="فهرست مقالهها دریافت نشد"
          message="ارتباط با سرور برقرار نشد؛ میتوانی دوباره تلاش کنی."
          @retry="refreshPages"
        />
        <p v-else-if="pagesPending" class="mt-4 py-6 text-center text-sm text-slate-500">
          در حال بارگذاری مقالهها...
        </p>
        <ul
          v-else-if="wikiResults.length"
          class="mt-4 divide-y divide-slate-100 overflow-hidden rounded-xl border border-slate-200"
        >
          <li
            v-for="page in wikiResults"
            :key="page.id"
            class="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
          >
            <div class="min-w-0">
              <p class="font-medium leading-7">{{ page.title }}</p>
              <p class="mt-0.5 text-xs text-slate-500">
                {{ TYPE_LABELS[page.page_type] ?? "مقاله" }} ·
                آخرین انتشار: {{ formatDate(page.last_updated) }}
                <span v-if="page.is_stale" class="text-amber-700">· نیازمند بازبینی</span>
              </p>
            </div>
            <div class="flex shrink-0 gap-2 text-xs">
              <NuxtLink
                :to="`/wiki/${page.slug}/`"
                class="rounded-lg border border-slate-200 px-3 py-2 hover:border-brand-300"
              >
                نمایش
              </NuxtLink>
              <a
                :href="adminUrl(`/cms/pages/${page.id}/edit/`)"
                target="_blank"
                rel="noopener noreferrer"
                class="btn-primary px-3 text-xs"
              >
                ویرایش در Wagtail
              </a>
            </div>
          </li>
        </ul>
        <p
          v-else
          class="mt-4 rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
        >
          با این جستوجو مقالهای پیدا نشد.
        </p>

        <p class="mt-3 text-xs text-slate-500">
          {{ pages?.count ?? 0 }} مقاله در نتیجه.
          <a
            :href="adminUrl(links?.explorer)"
            target="_blank"
            rel="noopener noreferrer"
            class="underline underline-offset-2"
          >
            فهرست کامل صفحهها
          </a>
          ·
          <a
            :href="adminUrl(links?.images)"
            target="_blank"
            rel="noopener noreferrer"
            class="underline underline-offset-2"
          >
            کتابخانهٔ تصاویر
          </a>
        </p>
      </section>

      </template>

      <section v-if="panelTab === 'tickets'" class="form-panel">
        <div class="mb-4 flex flex-wrap items-end justify-between gap-3">
          <div class="min-w-0">
            <h2 class="text-lg font-bold">تیکتهای کاربران</h2>
            <p class="mt-1 text-sm leading-7 text-slate-500">
              هر تیکت فقط برای صاحبش و تیم پشتیبانی قابل دیدن است. ثبت پاسخ، وضعیت تیکت را
              به «پاسخ دادهشده» میبرد و همان پاسخ در پنل کاربر نمایش داده میشود.
            </p>
          </div>
          <span class="shrink-0 text-xs text-slate-500">
            {{ support.allTickets.value.length }} تیکت
          </span>
        </div>

        <div class="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            class="min-h-9 rounded-lg border px-3 text-xs transition-colors"
            :class="
              ticketFilter === ''
                ? 'border-brand-300 bg-brand-50 font-semibold text-brand-700'
                : 'border-slate-200 text-slate-600 hover:border-brand-300'
            "
            :aria-pressed="ticketFilter === ''"
            @click="ticketFilter = ''"
          >
            همه ({{ support.allTickets.value.length }})
          </button>
          <button
            v-for="option in TICKET_STATUSES"
            :key="option.value"
            type="button"
            class="min-h-9 rounded-lg border px-3 text-xs transition-colors"
            :class="
              ticketFilter === option.value
                ? 'border-brand-300 bg-brand-50 font-semibold text-brand-700'
                : 'border-slate-200 text-slate-600 hover:border-brand-300'
            "
            :aria-pressed="ticketFilter === option.value"
            @click="ticketFilter = option.value"
          >
            {{ option.label }} ({{ ticketCounts[option.value] ?? 0 }})
          </button>
        </div>

        <p
          v-if="support.pending.value && !support.allTickets.value.length"
          class="py-6 text-center text-sm text-slate-500"
        >
          در حال بارگذاری تیکتها...
        </p>

        <div v-else-if="visibleTickets.length" class="grid gap-4 md:grid-cols-[minmax(0,20rem)_1fr]">
          <ul class="space-y-2">
            <li v-for="ticket in visibleTickets" :key="ticket.id">
              <button
                type="button"
                class="w-full rounded-lg border px-3 py-3 text-start transition-colors"
                :class="
                  support.activeTicket.value?.id === ticket.id
                    ? 'border-brand-300 bg-brand-50'
                    : 'border-slate-200 hover:border-brand-300'
                "
                :aria-expanded="support.activeTicket.value?.id === ticket.id"
                :title="support.activeTicket.value?.id === ticket.id ? 'بستن گفت‌وگو' : 'دیدن گفت‌وگو و پاسخ'"
                @click="openTicket(ticket)"
              >
                <span class="block truncate text-sm font-medium">{{ ticket.subject }}</span>
                <span class="mt-1 block truncate text-xs text-slate-500" dir="ltr">
                  {{ ticket.user.email }}
                </span>
                <span class="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <span
                    class="rounded-full border px-2 py-0.5"
                    :class="TICKET_STATUS_CLASS[ticket.status] ?? TICKET_STATUS_CLASS.open"
                  >
                    {{ ticket.status_label }}
                  </span>
                  <span class="text-slate-500">{{ formatDate(ticket.last_message_at) }}</span>
                </span>
              </button>
            </li>
          </ul>

          <div>
            <TicketThread
              v-if="support.activeTicket.value"
              :key="support.activeTicket.value.id"
              :ticket="support.activeTicket.value"
              :can-change-status="true"
              :submit-reply="replyAsStaff"
              :submit-status="moveStatus"
              :close-view="support.close"
            />
            <p
              v-else
              class="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
            >
              برای دیدن گفتوگو و ثبت پاسخ، یکی از تیکتها را انتخاب کن.
            </p>
          </div>
        </div>

        <p
          v-else
          class="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500"
        >
          تیکتی با این وضعیت وجود ندارد.
        </p>
      </section>

      <section v-if="panelTab === 'wiki'" class="form-panel">
        <h2 class="text-lg font-bold">تصویر مقاله و محصول</h2>
        <p class="mt-1 text-sm leading-7 text-slate-500">
          تصویر را برای یک مقالهٔ ویکی یا یک محصول بارگذاری کن. Wagtail فایل را ذخیره
          میکند و اندازههای لازم را میسازد؛ فقط JPEG، PNG و WebP تا ۵ مگابایت پذیرفته
          میشود و نوع واقعی فایل بررسی میشود. برای جایگزینی یا حذف تصویر، از فرم همان
          مقاله یا محصول در Wagtail استفاده کن.
        </p>

        <div class="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label class="text-sm text-slate-500">
            مقصد تصویر
            <select v-model="uploadTarget" class="form-field mt-1">
              <option value="">— انتخاب کن —</option>
              <option v-for="target in uploadTargets" :key="target.value" :value="target.value">
                {{ target.label }}
              </option>
            </select>
          </label>
          <label class="text-sm text-slate-500">
            فایل تصویر
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              class="form-field mt-1"
              @change="onFilePicked"
            />
          </label>
          <button type="button" class="btn-primary" :disabled="uploadPending" @click="submitUpload">
            {{ uploadPending ? "در حال بارگذاری..." : "بارگذاری" }}
          </button>
        </div>

        <p v-if="uploadNotice" class="alert-success mt-3">{{ uploadNotice }}</p>
        <p v-if="uploadError" class="alert-error mt-3">{{ uploadError }}</p>
      </section>

      <section class="rounded-xl border border-slate-200 bg-surface p-4 text-xs leading-7 text-slate-500">
        میانبرهای مدیریت:
        <a :href="adminUrl('/admin/')" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">مدیریت Django</a>
        ·
        <a :href="adminUrl(links?.tickets)" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">فهرست تیکتها در مدیریت Django</a>
        ·
        <a :href="adminUrl('/api/docs/')" target="_blank" rel="noopener noreferrer" class="underline underline-offset-2">مستندات API</a>
      </section>
    </template>
  </div>
</template>

