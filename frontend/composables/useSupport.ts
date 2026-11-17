import type { AccountResponse } from "~/types/account"
import { useAccount } from "~/composables/useAccount"
import type { TicketListResponse, TicketSummary } from "~/types/support"

/**
 * Support tickets, from both sides of the desk.
 *
 * The composable only *asks*: every rule about who may read or answer a ticket is
 * enforced by the API on the server (`apps/support/api.py`). A customer's request
 * can never return somebody else's thread, whatever the UI does.
 */
export function useSupport() {
  const account = useAccount()
  const myTickets = useState<TicketSummary[]>("support-my-tickets", () => [])
  const allTickets = useState<TicketSummary[]>("support-all-tickets", () => [])
  const activeTicket = useState<TicketSummary | null>("support-active-ticket", () => null)
  const pending = useState("support-pending", () => false)
  const error = useState("support-error", () => "")

  function fail(cause: unknown, fallback: string): never {
    const message = cause instanceof Error ? cause.message : fallback
    error.value = message
    throw cause instanceof Error ? cause : new Error(fallback)
  }

  async function loadMine() {
    await account.initialize()
    if (!account.user.value) {
      myTickets.value = []
      return myTickets.value
    }
    pending.value = true
    error.value = ""
    try {
      const data = await account.request<TicketListResponse & AccountResponse>(
        "/api/v1/support/tickets/?scope=mine",
      )
      myTickets.value = data.results
      return data.results
    } catch (cause) {
      return fail(cause, "فهرست تیکتها دریافت نشد.")
    } finally {
      pending.value = false
    }
  }

  async function loadAll(status = "") {
    pending.value = true
    error.value = ""
    try {
      const query = status ? `?status=${encodeURIComponent(status)}` : ""
      const data = await account.request<TicketListResponse & AccountResponse>(
        `/api/v1/support/tickets/${query}`,
      )
      allTickets.value = data.results
      return data.results
    } catch (cause) {
      return fail(cause, "فهرست تیکتها دریافت نشد.")
    } finally {
      pending.value = false
    }
  }

  async function open(id: string) {
    pending.value = true
    error.value = ""
    try {
      const ticket = await account.request<TicketSummary & AccountResponse>(
        `/api/v1/support/tickets/${id}/`,
      )
      activeTicket.value = ticket
      return ticket
    } catch (cause) {
      return fail(cause, "این تیکت باز نشد.")
    } finally {
      pending.value = false
    }
  }

  async function create(subject: string, body: string) {
    pending.value = true
    error.value = ""
    try {
      const ticket = await account.request<TicketSummary & AccountResponse>(
        "/api/v1/support/tickets/",
        { method: "POST", body: JSON.stringify({ subject, body }) },
      )
      activeTicket.value = ticket
      await loadMine()
      return ticket
    } catch (cause) {
      return fail(cause, "ثبت تیکت انجام نشد.")
    } finally {
      pending.value = false
    }
  }

  async function reply(id: string, body: string, { staff = false } = {}) {
    pending.value = true
    error.value = ""
    try {
      const ticket = await account.request<TicketSummary & AccountResponse>(
        `/api/v1/support/tickets/${id}/messages/`,
        { method: "POST", body: JSON.stringify({ body }) },
      )
      activeTicket.value = ticket
      if (staff) await loadAll()
      else await loadMine()
      return ticket
    } catch (cause) {
      return fail(cause, "ثبت پاسخ انجام نشد.")
    } finally {
      pending.value = false
    }
  }

  async function setStatus(id: string, status: string) {
    error.value = ""
    try {
      const ticket = await account.request<TicketSummary & AccountResponse>(
        `/api/v1/support/tickets/${id}/`,
        { method: "PATCH", body: JSON.stringify({ status }) },
      )
      activeTicket.value = ticket
      await loadAll()
      return ticket
    } catch (cause) {
      return fail(cause, "تغییر وضعیت انجام نشد.")
    }
  }

  /**
   * Close the detail *view*. It only clears client state and issues no request,
   * so opening or closing the conversation can never change a ticket's status —
   * only an explicit `setStatus` does that.
   */
  function close() {
    activeTicket.value = null
  }

  return {
    myTickets,
    allTickets,
    activeTicket,
    pending,
    error,
    loadMine,
    loadAll,
    open,
    close,
    create,
    reply,
    setStatus,
  }
}
