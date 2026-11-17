/** Format a price in tomans for display. Prices arrive as decimal strings. */
export function formatPrice(price: string | number | null | undefined, currency = "IRT"): string {
  if (price === null || price === undefined || price === "") {
    return "—"
  }
  const value = typeof price === "string" ? Number.parseFloat(price) : price
  if (Number.isNaN(value)) {
    return "—"
  }
  const rounded = Math.round(value)
  const formatted = new Intl.NumberFormat("fa-IR").format(rounded)
  return currency === "IRT" ? `${formatted} تومان` : `${formatted} ${currency}`
}

/** Format an ISO timestamp as a Persian date, e.g. "۲۲ مهر ۱۴۰۵". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) {
    return "—"
  }
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) {
    return "—"
  }
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date)
}

/**
 * Format a warranty length in months, Persian-first: 60 → «گارانتی ۶۰ ماهه».
 *
 * The number always comes from the product's own `warranty_months`, so nothing
 * is hard-coded in the UI, and a product without a warranty renders nothing.
 */
export function formatWarranty(months: number | null | undefined): string {
  if (!months || months <= 0) {
    return ""
  }
  const value = new Intl.NumberFormat("fa-IR").format(months)
  return `گارانتی ${value} ماهه`
}
