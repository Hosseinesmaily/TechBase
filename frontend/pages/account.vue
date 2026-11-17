<script setup lang="ts">
import { formatDate, formatPrice } from "~/utils/format"
import { TICKET_STATUS_CLASS } from "~/types/support"

const shelf = useCustomerShelf()
const account = useAccount()
const route = useRoute()
const mode = ref<"login" | "register">("login")
const email = ref("")
const name = ref("")
const password = ref("")
const formPending = ref(false)
const formError = ref("")
const formMessage = ref("")

// --- Support tickets (the customer's side of the desk) ---
const support = useSupport()
const newTicketOpen = ref(false)
const ticketSubject = ref("")
const ticketBody = ref("")
const ticketNotice = ref("")

function startNewTicket() {
  newTicketOpen.value = true
  ticketNotice.value = ""
}

async function submitTicket() {
  ticketNotice.value = ""
  try {
    await support.create(ticketSubject.value, ticketBody.value)
    ticketSubject.value = ""
    ticketBody.value = ""
    newTicketOpen.value = false
    ticketNotice.value = "تیکت ثبت شد؛ پاسخ تیم پشتیبانی همینجا نمایش داده میشود."
  } catch {
    // `support.error` already carries the server's Persian message.
  }
}

async function openTicket(id: string) {
  ticketNotice.value = ""
  // Toggle: clicking the open ticket again only closes the conversation panel.
  // No request is sent here, so the status never changes by opening/closing.
  if (support.activeTicket.value?.id === id) {
    support.close()
    return
  }
  try {
    await support.open(id)
  } catch {
    // `support.error` already carries the message.
  }
}

async function sendTicketReply(body: string) {
  const ticket = support.activeTicket.value
  if (!ticket) return
  await support.reply(ticket.id, body)
  ticketNotice.value = "پاسخ شما ثبت شد."
}

onMounted(() => {
  void account.initialize().catch((error: unknown) => {
    formError.value = error instanceof Error ? error.message : "ارتباط با سرور برقرار نشد."
  })
})

async function submitAccountForm() {
  formPending.value = true
  formError.value = ""
  formMessage.value = ""
  try {
    if (mode.value === "register") await account.register(email.value, name.value, password.value)
    else await account.login(email.value, password.value)

    // The identity comes from the session endpoint (`/api/v1/accounts/me/`), so the
    // destination follows the server's `is_staff` — never the typed name, the email
    // or the password.
    await account.refreshUser()
    const isStaff = Boolean(account.user.value?.is_staff)

    const requested = typeof route.query.next === "string" ? route.query.next : ""
    const safeNext = requested.startsWith("/") && !requested.startsWith("//") ? requested : ""
    if (safeNext) await navigateTo(safeNext)
    else if (isStaff) await navigateTo("/admin-panel")
    else await navigateTo("/account")
  } catch (error) {
    formError.value = error instanceof Error ? error.message : "ورود به حساب انجام نشد."
  } finally {
    formPending.value = false
  }
}

async function signOut() {
  formError.value = ""
  try {
    await account.logout()
    formMessage.value = "از حساب خارج شدی."
  } catch (error) {
    formError.value = error instanceof Error ? error.message : "خروج از حساب انجام نشد."
  }
}

useSeoMeta({
  title: "پنل من | تک‌بیس",
  description: "علاقهمندیها، تیکتهای پشتیبانی، سیستمهای ذخیرهشده و فهرست مقایسهٔ شما.",
})
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-8">
    <header>
      <p class="text-sm font-semibold text-brand-700">حساب کاربری تک‌بیس</p>
      <h1 class="mt-1 text-2xl font-bold">پنل من</h1>
      <p class="mt-2 text-sm leading-7 text-slate-500">با حساب کاربری، سبد خریدت به همان حساب متصل میماند. تیکتهای پشتیبانی و پاسخهای تیم پشتیبانی همینجا دیده میشوند؛ علاقهمندیها، مقایسه و سیستمهای ذخیرهشده فعلاً روی همین مرورگر نگهداری میشوند.</p>
    </header>

    <section class="form-panel">
      <div v-if="account.pending.value" class="py-4 text-sm text-slate-500">در حال بررسی حساب…</div>
      <div v-else-if="account.user.value" class="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p class="text-xs text-slate-500">واردشده با حساب</p>
          <p class="mt-1 font-semibold">{{ account.user.value.name }}</p>
          <p class="text-sm text-slate-500" dir="ltr">{{ account.user.value.email }}</p>
          <p v-if="account.user.value.is_staff" class="mt-2 inline-flex rounded-full bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">دسترسی تحریریه</p>
        </div>
        <div class="flex gap-2">
          <NuxtLink to="/cart" class="btn-primary">رفتن به سبد خرید</NuxtLink>
          <NuxtLink v-if="account.user.value?.is_staff" to="/admin-panel" class="btn-secondary">
            پنل مدیریت
          </NuxtLink>
          <button type="button" class="rounded-lg border border-slate-200 px-4 py-2 text-sm" @click="signOut">خروج</button>
        </div>
      </div>
      <form v-else class="mx-auto max-w-md" @submit.prevent="submitAccountForm">
        <div class="segmented mb-5">
          <button type="button" class="segmented-item" :class="mode === 'login' ? 'segmented-item-active' : 'text-slate-500'" @click="mode = 'login'; formError = ''">ورود</button>
          <button type="button" class="segmented-item" :class="mode === 'register' ? 'segmented-item-active' : 'text-slate-500'" @click="mode = 'register'; formError = ''">ساخت حساب</button>
        </div>
        <label v-if="mode === 'register'" class="form-label mb-3">نام
          <input v-model="name" autocomplete="name" class="form-field" required maxlength="150" />
        </label>
        <label class="form-label mb-3">ایمیل یا نام کاربری
          <input
            v-model="email"
            type="text"
            inputmode="email"
            autocomplete="username"
            class="form-field"
            required
            dir="ltr"
          />
        </label>
        <label class="form-label mb-4">گذرواژه
          <input v-model="password" type="password" :autocomplete="mode === 'register' ? 'new-password' : 'current-password'" class="form-field" required minlength="8" dir="ltr" />
        </label>
        <p v-if="formError" role="alert" class="alert-error mb-3">{{ formError }}</p>
        <p v-if="formMessage" role="status" class="alert-success mb-3">{{ formMessage }}</p>
        <button type="submit" :disabled="formPending" class="btn-primary w-full">
          {{ formPending ? "در حال انجام…" : mode === "register" ? "ساخت حساب و ورود" : "ورود به حساب" }}
        </button>
      </form>
    </section>

    <section class="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-brand-100 bg-brand-50/60 p-5">
      <div>
        <h2 class="font-bold">سبد خرید</h2>
        <p class="mt-1 text-sm text-slate-600">سبد خرید مخصوص همین حساب است و تعداد و قیمت را از کاتالوگ فعلی می‌خواند.</p>
      </div>
      <NuxtLink to="/cart" class="btn-secondary">مشاهدهٔ سبد خرید</NuxtLink>
    </section>

    <section class="form-panel">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 class="font-bold">فهرست مقایسه</h2>
          <p class="mt-1 text-xs text-slate-500">{{ shelf.compareItems.value.length }} محصول، حداکثر ۴ محصول</p>
        </div>
        <NuxtLink to="/compare" class="text-sm font-semibold text-brand-700 hover:underline">رفتن به مقایسه</NuxtLink>
      </div>
      <ul v-if="shelf.compareItems.value.length" class="divide-y divide-slate-100 rounded-lg border border-slate-200">
        <li v-for="product in shelf.compareItems.value" :key="product.sku" class="flex items-center justify-between gap-3 p-3">
          <NuxtLink :to="`/entity/${product.entity_slug}/`" class="min-w-0 truncate font-medium hover:text-brand-700">{{ product.title }}</NuxtLink>
          <div class="flex shrink-0 items-center gap-3 text-sm">
            <span>{{ formatPrice(product.price, product.currency) }}</span>
            <button type="button" class="text-xs text-rose-700" @click="shelf.removeCompare(product.sku)">حذف</button>
          </div>
        </li>
      </ul>
      <p v-else class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">در کاتالوگ یا نتایج جست‌وجو محصولی را به مقایسه اضافه کنید.</p>
      <NuxtLink v-if="shelf.compareItems.value.length >= 2" to="/compare" class="btn-primary mt-4">مقایسهٔ محصولات انتخاب‌شده</NuxtLink>
    </section>

    <section class="form-panel">
      <div class="mb-4 flex items-center justify-between gap-3">
        <h2 class="font-bold">علاقه‌مندی‌ها</h2>
        <NuxtLink to="/catalog" class="text-sm text-brand-700 hover:underline">مرور کاتالوگ</NuxtLink>
      </div>
      <ul v-if="shelf.favorites.value.length" class="grid gap-3 sm:grid-cols-2">
        <li v-for="product in shelf.favorites.value" :key="product.sku" class="rounded-lg border border-slate-200 p-4">
          <NuxtLink :to="`/entity/${product.entity_slug}/`" class="font-semibold hover:text-brand-700">{{ product.title }}</NuxtLink>
          <p class="mt-2 font-bold">{{ formatPrice(product.price, product.currency) }}</p>
          <p class="mt-1 text-xs text-slate-500">{{ product.in_stock ? "هنگام ذخیره موجود بود" : "هنگام ذخیره ناموجود بود" }} · به‌روزرسانی داده: {{ formatDate(product.updated_at) }}</p>
          <div class="mt-3 flex gap-3 text-xs">
            <button type="button" class="text-brand-700 underline" @click="shelf.toggleCompare(product)">افزودن/حذف از مقایسه</button>
            <button type="button" class="text-rose-700 underline" @click="shelf.removeFavorite(product.sku)">حذف علاقه‌مندی</button>
          </div>
        </li>
      </ul>
      <p v-else class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">هنوز محصولی ذخیره نکرده‌اید. از کارت محصول دکمهٔ «علاقه‌مندی» را بزنید.</p>
    </section>

    <section class="form-panel">
      <div class="mb-4 flex items-center justify-between gap-3">
        <h2 class="font-bold">سیستم‌های ذخیره‌شده</h2>
        <NuxtLink to="/configurator" class="text-sm text-brand-700 hover:underline">ساخت سیستم</NuxtLink>
      </div>
      <ul v-if="shelf.builds.value.length" class="space-y-3">
        <li v-for="build in shelf.builds.value" :key="build.id" class="rounded-lg border border-slate-200 p-4">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="font-semibold">{{ build.name }}</h3>
              <p class="mt-1 text-xs text-slate-500">ذخیره‌شده در {{ formatDate(build.saved_at) }} · {{ build.products.length }} قطعه</p>
            </div>
            <button type="button" class="text-xs text-rose-700 underline" @click="shelf.removeBuild(build.id)">حذف سیستم</button>
          </div>
          <ul class="mt-3 flex flex-wrap gap-2">
            <li v-for="product in build.products" :key="product.sku" class="rounded-full bg-slate-100 px-3 py-1 text-xs">{{ product.title }}</li>
          </ul>
          <p class="mt-3 text-xs text-amber-700">قیمت و موجودی این نسخه، تصویر زمان ذخیره است؛ برای دادهٔ فعلی کاتالوگ را بررسی کنید.</p>
        </li>
      </ul>
      <p v-else class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500">بعد از انتخاب همهٔ قطعات سازگار، سیستم را از صفحهٔ اسمبل اینجا ذخیره کنید.</p>
    </section>

<section class="form-panel">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 class="font-bold">پشتیبانی</h2>
        <button
          v-if="account.user.value && !newTicketOpen"
          type="button"
          class="btn-secondary"
          @click="startNewTicket"
        >
          ثبت تیکت جدید
        </button>
      </div>

      <p v-if="!account.user.value" class="text-sm text-slate-500">
        برای ثبت تیکت و دیدن پاسخهای تیم پشتیبانی، ابتدا وارد حساب شو.
      </p>

      <template v-else>
        <p v-if="ticketNotice" class="alert-success mb-3">{{ ticketNotice }}</p>
        <p v-if="support.error.value" class="alert-error mb-3">{{ support.error.value }}</p>

        <form v-if="newTicketOpen" class="mb-5 rounded-lg border border-slate-200 p-4" @submit.prevent="submitTicket">
          <label class="form-label" for="ticket-subject">عنوان</label>
          <input
            id="ticket-subject"
            v-model="ticketSubject"
            class="form-field mt-1"
            maxlength="200"
            placeholder="موضوع پرسش، مثلاً گارانتی کارت گرافیک"
          />
          <label class="form-label mt-4" for="ticket-body">متن پیام</label>
          <textarea
            id="ticket-body"
            v-model="ticketBody"
            class="form-field mt-1 min-h-28"
            maxlength="4000"
            placeholder="پرسش یا مشکل خود را کامل بنویسید."
          />
          <div class="mt-3 flex gap-2">
            <button type="submit" class="btn-primary" :disabled="support.pending.value">
              {{ support.pending.value ? "در حال ثبت..." : "ثبت تیکت" }}
            </button>
            <button type="button" class="btn-secondary" @click="newTicketOpen = false">انصراف</button>
          </div>
        </form>

        <ul v-if="support.myTickets.value.length" class="mb-5 space-y-2">
          <li v-for="ticket in support.myTickets.value" :key="ticket.id">
            <button
              type="button"
              class="flex w-full flex-wrap items-center justify-between gap-2 rounded-lg border px-4 py-3 text-start text-sm transition-colors"
              :class="
                support.activeTicket.value?.id === ticket.id
                  ? 'border-brand-300 bg-brand-50'
                  : 'border-slate-200 hover:border-brand-300'
              "
              :aria-expanded="support.activeTicket.value?.id === ticket.id"
              @click="openTicket(ticket.id)"
            >
              <span class="font-medium">{{ ticket.subject }}</span>
              <span class="flex items-center gap-2 text-xs text-slate-500">
                <span class="rounded-full border px-2 py-0.5" :class="TICKET_STATUS_CLASS[ticket.status] ?? ''">
                  {{ ticket.status_label }}
                </span>
                <span>{{ formatDate(ticket.last_message_at) }}</span>
              </span>
            </button>
          </li>
        </ul>

        <TicketThread
          v-if="support.activeTicket.value"
          :key="support.activeTicket.value.id"
          :ticket="support.activeTicket.value"
          :submit-reply="sendTicketReply"
          :close-view="support.close"
        />

        <p
          v-else
          class="rounded-lg border border-dashed border-slate-300 p-5 text-center text-sm text-slate-500"
        >
          {{ support.myTickets.value.length ? "برای دیدن گفتوگو، یکی از تیکتها را انتخاب کنید." : "هنوز تیکتی ثبت نکردهای. اگر پرسشی دربارهٔ یک محصول یا سفارش داری، تیکت بفرست." }}
        </p>
      </template>
    </section>
  </div>
</template>
