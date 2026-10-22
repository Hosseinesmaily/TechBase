/**
 * XML sitemap for the public site.
 *
 * Lists the wiki pages and the catalog, so search engines can find the
 * content. The base URL comes from the runtime config.
 */
export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig(event)
  const base = String(config.public.siteUrl || "http://localhost:3000").replace(/\/+$/, "")

  const urls: { loc: string; lastmod?: string | null; priority?: string }[] = [
    { loc: `${base}/`, priority: "1.0" },
    { loc: `${base}/wiki/`, priority: "0.8" },
    { loc: `${base}/catalog/`, priority: "0.8" },
  ]

  try {
    // Read the upstream from the environment directly: `runtimeConfig` values
    // are overridden at runtime with the `NUXT_` prefix, so `API_INTERNAL_BASE`
    // would not apply here.
    const apiBase = (
      process.env.API_INTERNAL_BASE || String(config.apiInternalBase)
    ).replace(/\/+$/, "")

    const pages = await $fetch<{ results: { slug: string; last_updated: string | null }[] }>(
      `${apiBase}/api/v1/wiki/pages/`,
      { query: { page_size: "500" } },
    )
    for (const page of pages.results ?? []) {
      urls.push({
        loc: `${base}/wiki/${page.slug}/`,
        lastmod: page.last_updated,
        priority: "0.6",
      })
    }
  } catch {
    // The sitemap must still render when the API is down.
  }

  const body = urls
    .map((url) => {
      const parts = [`    <loc>${url.loc}</loc>`]
      if (url.lastmod) parts.push(`    <lastmod>${url.lastmod.slice(0, 10)}</lastmod>`)
      if (url.priority) parts.push(`    <priority>${url.priority}</priority>`)
      return `  <url>\n${parts.join("\n")}\n  </url>`
    })
    .join("\n")

  setHeader(event, "content-type", "application/xml; charset=utf-8")
  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${body}
</urlset>
`
})
