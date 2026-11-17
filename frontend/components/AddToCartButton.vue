<script setup lang="ts">
const props = defineProps<{
  sku: string
  inStock: boolean
}>()

const account = useAccount()
const shoppingCart = useCart(false)
const route = useRoute()
const pending = ref(false)
const message = ref("")
const failed = ref(false)

async function addToCart() {
  message.value = ""
  failed.value = false
  pending.value = true
  try {
    await account.initialize()
    if (!account.user.value) {
      await navigateTo({ path: "/account", query: { next: route.fullPath } })
      return
    }
    await shoppingCart.add(props.sku)
    message.value = "به سبد خرید اضافه شد"
  } catch (error) {
    failed.value = true
    message.value = error instanceof Error ? error.message : "افزودن به سبد خرید انجام نشد."
  } finally {
    pending.value = false
  }
}
</script>

<template>
  <div>
    <button
      type="button"
      :disabled="!props.inStock || pending"
      class="btn-primary w-full"
      @click.stop="addToCart"
    >
      {{ pending ? "در حال افزودن…" : props.inStock ? "افزودن به سبد خرید" : "ناموجود" }}
    </button>
    <p v-if="message" role="status" class="mt-1.5 text-xs" :class="failed ? 'text-rose-700' : 'text-emerald-700'">
      {{ message }}
    </p>
  </div>
</template>
