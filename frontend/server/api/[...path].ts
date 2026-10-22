/**
 * Same-origin API proxy: `/api/**` → Django.
 *
 * The browser always talks to the Nuxt server, so the app never needs CORS.
 * The upstream base URL is read at request time from the environment, so one
 * build can be pointed at a different API host without rebuilding.
 */
export default defineEventHandler(async (event) => {
  // Read from the environment directly: `runtimeConfig` is populated at build
  // time for some presets, and this must stay a runtime value.
  const base = (process.env.API_INTERNAL_BASE || "http://backend:8000").replace(/\/+$/, "")

  // `event.path` is like "/api/v1/catalog/products/" — the query string is
  // already part of it, so it is forwarded verbatim. Django serves the API
  // under /api/v1/, so the "/api" prefix is kept as-is.
  const path = event.path
  const target = `${base}${path}`

  try {
    return await $fetch(target, {
      method: event.method,
      headers: {
        accept: event.node.req.headers.accept ?? "application/json",
        ...(event.node.req.headers["content-type"]
          ? { "content-type": event.node.req.headers["content-type"] }
          : {}),
      },
      body:
        event.method === "GET" || event.method === "HEAD" ? undefined : await readBody(event),
    })
  } catch (error: unknown) {
    const statusCode =
      typeof error === "object" && error !== null && "statusCode" in error
        ? Number((error as { statusCode: number }).statusCode)
        : 502
    throw createError({
      statusCode,
      statusMessage: `API request failed: ${target}`,
      data: { error: true, url: target },
    })
  }
})
