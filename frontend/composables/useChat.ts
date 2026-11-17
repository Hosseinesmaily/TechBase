/**
 * The chat client: POSTs the question and consumes the SSE stream.
 *
 * The event types mirror the backend: `citations`, `token`, `replace`,
 * `guardrails`, `done` and `error` — plus `clarifying_question` for the
 * agentic flow.
 */

import type { AgentCitation, ProductCardData, Understanding } from "~/types/agent"

export interface ChatMessage {
  role: "user" | "assistant"
  text: string
  citations?: AgentCitation[]
  cards?: ProductCardData[]
  understanding?: Understanding
  guardrails?: { ok: boolean; note?: string; [key: string]: unknown }
  clarifyingQuestion?: string
  pending?: boolean
  error?: string
}

interface StreamEvent {
  type:
    | "citations"
    | "token"
    | "replace"
    | "guardrails"
    | "done"
    | "error"
    | "clarifying_question"
  citations?: AgentCitation[]
  cards?: ProductCardData[]
  understanding?: Understanding
  text?: string
  question?: string
  guardrails?: { ok: boolean; [key: string]: unknown }
  message?: string
  latency_ms?: number
  query_log_id?: string
}

export function useChat() {
  const messages = useState<ChatMessage[]>("chat-messages", () => [])
  const streaming = useState<boolean>("chat-streaming", () => false)
  const clarificationContext = useState<string | null>("chat-clarification-context", () => null)

  function push(message: ChatMessage) {
    messages.value = [...messages.value, message]
  }

  async function send(question: string) {
    const text = question.trim()
    if (!text || streaming.value) return

    // The conversation so far, captured *before* this turn is added: the backend
    // uses it to remember what the user already said (a budget, a use case) and
    // to keep a short follow-up on the same topic.
    const history = messages.value
      .filter((message) => message.role === "user" && message.text)
      .map((message) => ({ role: "user", content: message.text }))
      .slice(-6)

    const queryForAgent = text
    clarificationContext.value = null

    push({ role: "user", text })
    const assistant: ChatMessage = { role: "assistant", text: "", pending: true }
    push(assistant)
    streaming.value = true

    try {
      const response = await fetch("/api/v1/ai/chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ query: queryForAgent, language: "fa", stream: true, history }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`the server answered ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ""

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // SSE frames are separated by a blank line.
        let boundary = buffer.indexOf("\n\n")
        while (boundary !== -1) {
          const frame = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          handleFrame(frame, assistant, () => {
            clarificationContext.value = queryForAgent
          })
          boundary = buffer.indexOf("\n\n")
        }
      }
    } catch (error) {
      assistant.error =
        error instanceof Error ? error.message : "ارتباط با سرور برقرار نشد."
    } finally {
      assistant.pending = false
      streaming.value = false
    }
  }

  function handleFrame(frame: string, assistant: ChatMessage, saveClarification: () => void) {
    const dataLine = frame
      .split("\n")
      .find((line) => line.startsWith("data: "))
    if (!dataLine) return

    let event: StreamEvent
    try {
      event = JSON.parse(dataLine.slice(6)) as StreamEvent
    } catch {
      return
    }

    switch (event.type) {
      case "citations":
        assistant.citations = event.citations ?? []
        assistant.cards = event.cards ?? []
        assistant.understanding = event.understanding
        break
      case "token":
        assistant.text += event.text ?? ""
        break
      case "replace":
        // The guardrail rejected the draft — swap in the honest message.
        assistant.text = event.text ?? assistant.text
        break
      case "guardrails":
        assistant.guardrails = event.guardrails
        break
      case "clarifying_question":
        assistant.clarifyingQuestion = event.question ?? ""
        saveClarification()
        break
      case "error":
        assistant.error = event.message ?? "خطای ناشناخته"
        break
      case "done":
        break
    }
  }

  function reset() {
    messages.value = []
    clarificationContext.value = null
  }

  return { messages, streaming, send, reset }
}
