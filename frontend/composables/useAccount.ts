export interface AccountUser {
  id: number
  email: string
  name: string
  is_staff: boolean
}

interface AccountResponse {
  authenticated?: boolean
  user?: AccountUser | null
  csrf_token?: string
  error?: string
}

let initialization: Promise<void> | null = null

export function useAccount() {
  const user = useState<AccountUser | null>("account-user", () => null)
  const checked = useState("account-checked", () => false)
  const pending = useState("account-pending", () => false)
  const csrfToken = useState("account-csrf", () => "")

  async function refreshCsrf() {
    const response = await fetch("/api/v1/accounts/csrf/")
    const data = (await response.json()) as AccountResponse
    if (!response.ok || !data.csrf_token) throw new Error(data.error || "دریافت مجوز امنیتی انجام نشد.")
    csrfToken.value = data.csrf_token
  }

  async function request<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
    const method = (init.method ?? "GET").toUpperCase()
    const headers = new Headers(init.headers)
    if (method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
      // A session-authenticated write needs the CSRF token. Fetching it lazily
      // keeps this correct even for a request issued before `initialize()`
      // finished — and it is exactly what broke once the visitor signed in:
      // DRF's SessionAuthentication only enforces CSRF for an authenticated
      // request, so a POST that worked as a guest started answering 403.
      if (!csrfToken.value) await refreshCsrf()
      headers.set("X-CSRFToken", csrfToken.value)
    }
    // A FormData body must keep the browser's own multipart boundary, so the JSON
    // content type is only set for a plain body.
    if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
      headers.set("Content-Type", "application/json")
    }

    const response = await fetch(path, { ...init, method, headers, credentials: "same-origin" })
    const data = (await response.json().catch(() => ({}))) as T & {
      csrf_token?: string
      error?: string
    }
    if (!response.ok) throw new Error(data.error || `درخواست با خطای ${response.status} روبه‌رو شد.`)
    if (data.csrf_token) csrfToken.value = data.csrf_token
    return data
  }

  async function refreshUser() {
    const data = await request<AccountResponse>("/api/v1/accounts/me/")
    user.value = data.authenticated ? data.user ?? null : null
    checked.value = true
  }

  function initialize(): Promise<void> {
    if (!import.meta.client) return Promise.resolve()
    if (checked.value) return Promise.resolve()
    if (initialization) return initialization
    pending.value = true
    initialization = (async () => {
      try {
        await refreshCsrf()
        await refreshUser()
      } finally {
        pending.value = false
      }
    })().finally(() => {
      initialization = null
    })
    return initialization
  }

  async function login(email: string, password: string) {
    await initialize()
    const data = await request<AccountResponse>("/api/v1/accounts/login/", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    })
    user.value = data.user ?? null
    checked.value = true
    return user.value
  }

  async function register(email: string, name: string, password: string) {
    await initialize()
    const data = await request<AccountResponse>("/api/v1/accounts/register/", {
      method: "POST",
      body: JSON.stringify({ email, name, password }),
    })
    user.value = data.user ?? null
    checked.value = true
    return user.value
  }

  async function logout() {
    await request<AccountResponse>("/api/v1/accounts/logout/", {
      method: "POST",
      body: JSON.stringify({}),
    })
    user.value = null
    csrfToken.value = ""
    checked.value = true
  }

  return { user, checked, pending, initialize, refreshUser, login, register, logout, request }
}
