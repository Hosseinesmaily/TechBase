/**
 * Same-origin API access: the browser hits /api/** on the Nuxt server,
 * which Nitro proxies to Django (see nuxt.config.ts routeRules).
 * No CORS involved.
 */
export function useApi<T>() {
  const fetchJson = async (path: string, opts?: RequestInit): Promise<T> => {
    const res = await fetch(path, {
      headers: { accept: "application/json" },
      ...opts,
    })
    if (!res.ok) {
      throw new Error(`API ${path} failed: ${res.status}`)
    }
    return (await res.json()) as T
  }

  return { fetchJson }
}
