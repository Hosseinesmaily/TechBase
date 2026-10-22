export default defineEventHandler((event) => {
  const config = useRuntimeConfig(event)
  const base = String(config.public.siteUrl || "http://localhost:3000").replace(/\/+$/, "")

  setHeader(event, "content-type", "text/plain; charset=utf-8")
  return `User-agent: *
Allow: /
Disallow: /api/
Disallow: /chat

Sitemap: ${base}/sitemap.xml
`
})
