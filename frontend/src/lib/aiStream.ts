import { apiBase } from "@/lib/api"
import { getAuthHeader } from "@/lib/auth"

export interface StreamHandlers {
  onToken: (text: string) => void
  onToolStart: (label: string) => void
  onToolEnd: () => void
  /** Pipeline-stage progress (e.g. "Routing your question…", "Drafting your
   * report…") — reuses the same evolving single-label slot as tool
   * progress; not a separate multi-row display. */
  onStage: (label: string) => void
  onDone: (sessionId: number, messageId: number, reply: string) => void
  onError: (detail: string) => void
}

export async function streamChat(
  body: { session_id: number; message: string; model?: string | null },
  h: StreamHandlers,
): Promise<void> {
  let terminalFired = false
  try {
    const res = await fetch(`${apiBase}/api/ai/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeader() },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      h.onError((data as { detail?: string }).detail || `HTTP ${res.status}`)
      terminalFired = true
      return
    }
    const reader = res.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ""
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split("\n\n")
      buffer = frames.pop() ?? ""
      for (const frame of frames) {
        const line = frame.trim()
        if (!line.startsWith("data: ")) continue
        const ev = JSON.parse(line.slice(6)) as Record<string, unknown>
        switch (ev.type) {
          case "token": h.onToken(ev.text as string); break
          case "tool_start": h.onToolStart(ev.label as string); break
          case "tool_end": h.onToolEnd(); break
          case "stage": h.onStage(ev.label as string); break
          case "done":
            h.onDone(ev.session_id as number, ev.message_id as number, (ev.reply as string) ?? "")
            terminalFired = true
            break
          case "error":
            h.onError(ev.detail as string)
            terminalFired = true
            break
        }
      }
    }
  } catch {
    // Guard: a connection reset arriving AFTER the terminal frame must not
    // overwrite a successful completion with a spurious error banner.
    if (!terminalFired) {
      h.onError("Connection to the AI service was interrupted. Please try again.")
      terminalFired = true
    }
  }
  if (!terminalFired) {
    h.onError("The AI response ended unexpectedly. Please try again.")
  }
}
