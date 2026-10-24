/**
 * Same-origin, streaming API proxy: `/api/**` → Django.
 *
 * H3 forwards cookies and response headers and streams SSE frames through to
 * the browser instead of buffering the assistant's whole answer first.
 */
import { proxyRequest } from "h3"

export default defineEventHandler((event) => {
  // Compose supplies the service DNS name; direct Windows runs use loopback.
  const base = (process.env.API_INTERNAL_BASE || "http://127.0.0.1:8000").replace(/\/+$/, "")
  const target = `${base}${event.path}`

  return proxyRequest(event, target, {
    headers: { accept: event.node.req.headers.accept ?? "*/*" },
    streamRequest: true,
  })
})
