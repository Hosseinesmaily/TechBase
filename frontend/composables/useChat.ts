/**
 * The chat client: POSTs the question and consumes the SSE stream.
 *
 * The event types mirror the backend: `citations`, `token`, `replace`,
 * `guardrails`, `done` and `error`.
 */

export interface ChatCitation {
  index: number
  page_slug: string
  page_title: string
  section_path: string
  heading: string
  url: string
  entity_slug: string | null
  score: number
}

export interface ChatMessage {
  role: "user" | "assistant"
  text: string
  citations?: ChatCitation[]
  guardrails?: { ok: boolean; note?: string; [key: string]: unknown }
  pending?: boolean
  error?: string
}

interface StreamEvent {
  type: "citations" | "token" | "replace" | "guardrails" | "done" | "error"
  citations?: ChatCitation[]
  text?: string
  guardrails?: { ok: boolean; [key: string]: unknown }
  message?: string
  latency_ms?: number
  query_log_id?: string
}

export function useChat() {
  const messages = useState<ChatMessage[]>("chat-messages", () => [])
  const streaming = useState<boolean>("chat-streaming", () => false)

  function push(message: ChatMessage) {
    messages.value = [...messages.value, message]
  }

  async function send(question: string) {
    const text = question.trim()
    if (!text || streaming.value) return

    push({ role: "user", text })
    const assistant: ChatMessage = { role: "assistant", text: "", pending: true }
    push(assistant)
    streaming.value = true

    try {
      const response = await fetch("/api/v1/ai/chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          accept: "text/event-stream",
        },
        body: JSON.stringify({ query: text, language: "fa", stream: true }),
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
          handleFrame(frame, assistant)
          boundary = buffer.indexOf("\n\n")
        }
      }
    } catch (error) {
      assistant.error =
        error instanceof Error ? error.message : "ارتباط با سرور برقرار نشد."
      assistant.pending = false
    } finally {
      streaming.value = false
    }
  }

  function handleFrame(frame: string, assistant: ChatMessage) {
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
      case "error":
        assistant.error = event.message ?? "خطای ناشناخته"
        break
      case "done":
        break
    }
  }

  function reset() {
    messages.value = []
  }

  return { messages, streaming, send, reset }
}
