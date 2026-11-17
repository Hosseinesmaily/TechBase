export interface SavedProduct {
  sku: string
  title: string
  price: string
  currency: string
  entity_type: string
  entity_slug: string
  in_stock: boolean
  updated_at: string
}

export interface SavedBuild {
  id: string
  name: string
  saved_at: string
  products: SavedProduct[]
}

export type ProductSnapshot = SavedProduct

const STORAGE_KEY = "techbase-customer-shelf-v1"
const MAX_COMPARE_ITEMS = 4

export function useCustomerShelf() {
  const favorites = useState<SavedProduct[]>("customer-favorites", () => [])
  const builds = useState<SavedBuild[]>("customer-builds", () => [])
  const compareItems = useState<SavedProduct[]>("customer-compare", () => [])
  const recentSearches = useState<string[]>("customer-searches", () => [])
  const loaded = useState<boolean>("customer-shelf-loaded", () => false)

  onMounted(() => {
    if (loaded.value) return
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}") as {
        favorites?: SavedProduct[]
        builds?: SavedBuild[]
        compareItems?: SavedProduct[]
        recentSearches?: string[]
      }
      favorites.value = saved.favorites ?? []
      builds.value = saved.builds ?? []
      compareItems.value = (saved.compareItems ?? []).slice(0, MAX_COMPARE_ITEMS)
      recentSearches.value = (saved.recentSearches ?? []).slice(0, 8)
    } catch {
      try {
        localStorage.removeItem(STORAGE_KEY)
      } catch {
        // Storage can be disabled by the browser; the guest shelf remains usable in memory.
      }
    }
    loaded.value = true
  })

  function persist() {
    if (!import.meta.client) return
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          favorites: favorites.value,
          builds: builds.value,
          compareItems: compareItems.value,
          recentSearches: recentSearches.value,
        }),
      )
    } catch {
      // Keep current state usable even when browser storage is unavailable/full.
    }
  }

  function isFavorite(sku: string) {
    return favorites.value.some((item) => item.sku === sku)
  }

  function toggleFavorite(product: ProductSnapshot) {
    favorites.value = isFavorite(product.sku)
      ? favorites.value.filter((item) => item.sku !== product.sku)
      : [product, ...favorites.value]
    persist()
  }

  function removeFavorite(sku: string) {
    favorites.value = favorites.value.filter((item) => item.sku !== sku)
    persist()
  }

  function isCompared(sku: string) {
    return compareItems.value.some((item) => item.sku === sku)
  }

  function toggleCompare(product: ProductSnapshot) {
    if (isCompared(product.sku)) {
      compareItems.value = compareItems.value.filter((item) => item.sku !== product.sku)
      persist()
      return true
    }
    if (compareItems.value.length >= MAX_COMPARE_ITEMS) return false
    compareItems.value = [...compareItems.value, product]
    persist()
    return true
  }

  function removeCompare(sku: string) {
    compareItems.value = compareItems.value.filter((item) => item.sku !== sku)
    persist()
  }

  function clearCompare() {
    compareItems.value = []
    persist()
  }

  function saveBuild(name: string, products: ProductSnapshot[]) {
    const uniqueProducts = [...new Map(products.map((item) => [item.sku, item])).values()]
    if (!uniqueProducts.length) return
    const id = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}`
    builds.value = [
      { id, name: name.trim() || "سیستم من", saved_at: new Date().toISOString(), products: uniqueProducts },
      ...builds.value,
    ]
    persist()
  }

  function removeBuild(id: string) {
    builds.value = builds.value.filter((build) => build.id !== id)
    persist()
  }

  function saveSearch(query: string) {
    const value = query.trim()
    if (!value) return
    recentSearches.value = [value, ...recentSearches.value.filter((item) => item !== value)].slice(0, 8)
    persist()
  }

  function removeSearch(query: string) {
    recentSearches.value = recentSearches.value.filter((item) => item !== query)
    persist()
  }

  function clearSearches() {
    recentSearches.value = []
    persist()
  }

  return {
    favorites,
    builds,
    compareItems,
    recentSearches,
    isFavorite,
    toggleFavorite,
    removeFavorite,
    isCompared,
    toggleCompare,
    removeCompare,
    clearCompare,
    saveBuild,
    removeBuild,
    saveSearch,
    removeSearch,
    clearSearches,
  }
}
