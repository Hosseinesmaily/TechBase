import type { AccountResponse } from "~/types/account"
import { useAccount } from "~/composables/useAccount"

export interface ShoppingCartItem {
  sku: string
  title: string
  entity_slug: string
  quantity: number
  price: string
  currency: string
  stock: number
  in_stock: boolean
  subtotal: string
  price_updated_at: string | null
}

export interface ShoppingCart {
  items: ShoppingCartItem[]
  item_count: number
  total: string
  currency: string
}

export function useCart(autoLoad = true) {
  const account = useAccount()
  const cart = useState<ShoppingCart | null>("shopping-cart", () => null)
  const pending = useState("shopping-cart-pending", () => false)
  const error = useState("shopping-cart-error", () => "")

  async function load() {
    await account.initialize()
    if (!account.user.value) {
      cart.value = null
      return null
    }
    pending.value = true
    error.value = ""
    try {
      cart.value = await account.request<ShoppingCart & AccountResponse>("/api/v1/accounts/cart/")
      return cart.value
    } catch (cause) {
      error.value = cause instanceof Error ? cause.message : "سبد خرید بارگذاری نشد."
      throw cause
    } finally {
      pending.value = false
    }
  }

  async function add(sku: string, quantity = 1) {
    const result = await account.request<ShoppingCart & AccountResponse>("/api/v1/accounts/cart/items/", {
      method: "POST",
      body: JSON.stringify({ sku, quantity }),
    })
    cart.value = result
    return result
  }

  async function update(sku: string, quantity: number) {
    const result = await account.request<ShoppingCart & AccountResponse>("/api/v1/accounts/cart/items/", {
      method: "PATCH",
      body: JSON.stringify({ sku, quantity }),
    })
    cart.value = result
    return result
  }

  async function remove(sku: string) {
    const result = await account.request<ShoppingCart & AccountResponse>(
      `/api/v1/accounts/cart/items/?sku=${encodeURIComponent(sku)}`,
      { method: "DELETE" },
    )
    cart.value = result
    return result
  }

  if (autoLoad) {
    onMounted(() => {
      void account.initialize().then(() => {
        if (account.user.value) return load()
        return null
      }).catch(() => undefined)
    })

    watch(() => account.user.value?.id, (userId) => {
      if (!userId) cart.value = null
      else if (import.meta.client) void load().catch(() => undefined)
    })
  }

  return { cart, pending, error, load, add, update, remove }
}
