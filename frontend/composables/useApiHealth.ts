/**
 * The real API reachability check.
 *
 * The state comes from an actual request to `/api/v1/health/` — never from a
 * guess. A failure is captured, never thrown, so a single unreachable request
 * can not break the page (or the SSR render) that uses it.
 */

export type ApiHealthState = "loading" | "ok" | "error"

interface HealthPayload {
  status?: string
}

export function useApiHealth() {
  const state = useState<ApiHealthState>("api-health-state", () => "loading")
  const checkedAt = useState<string>("api-health-checked-at", () => "")

  async function check(): Promise<ApiHealthState> {
    state.value = "loading"
    try {
      const data = await $fetch<HealthPayload>("/api/v1/health/", { timeout: 8000 })
      state.value = data?.status === "ok" ? "ok" : "error"
    } catch {
      // Transport errors, timeouts and non-2xx answers are all "unreachable".
      state.value = "error"
    } finally {
      checkedAt.value = new Date().toISOString()
    }
    return state.value
  }

  return { state, checkedAt, check, retry: check }
}
