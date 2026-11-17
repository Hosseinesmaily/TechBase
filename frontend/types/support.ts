/** Types for the support ticket API (see backend/apps/support/api.py). */

export interface TicketMessage {
  id: string
  body: string
  from_staff: boolean
  author: string
  created_at: string
}

export interface TicketSummary {
  id: string
  subject: string
  status: string
  status_label: string
  created_at: string
  last_message_at: string
  message_count: number
  has_staff_reply: boolean
  user: { name: string; email: string }
  /** Present on the detail endpoints only. */
  messages?: TicketMessage[]
}

export interface TicketListResponse {
  count: number
  results: TicketSummary[]
}

/** The four statuses, in the order the panels offer them. */
export const TICKET_STATUSES: { value: string; label: string }[] = [
  { value: "open", label: "باز" },
  { value: "in_progress", label: "در حال بررسی" },
  { value: "answered", label: "پاسخ دادهشده" },
  { value: "closed", label: "بسته" },
]

/** The badge style of a status; colour is a hint, the label is the statement.
 *
 * Only the remapped theme tokens are used (see `tailwind.config.ts`): a default
 * Tailwind shade such as `bg-sky-50` is a near-white block on this dark canvas,
 * and `text-amber-900` is a dark brown — both were reading as "off".
 */
export const TICKET_STATUS_CLASS: Record<string, string> = {
  open: "border-brand-300 bg-brand-50 text-brand-700",
  in_progress: "border-amber-200 bg-amber-50 text-amber-700",
  answered: "border-emerald-200 bg-emerald-50 text-emerald-700",
  closed: "border-slate-200 bg-slate-100 text-slate-600",
}
