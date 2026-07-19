"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface ChatMarkdownProps {
  content: string
}

/** Renders AI chat replies as real Markdown — tables, headings, bold labels
 * — styled against the app's own theme vars instead of browser defaults, so
 * a drafted report reads as a professional table, not literal pipe
 * characters. Used for assistant bubbles only; user messages stay plain
 * text (no need to interpret user input as Markdown). */
export default function ChatMarkdown({ content }: ChatMarkdownProps) {
  return (
    <div className="text-sm leading-relaxed break-words [&>*:first-child]:mt-0 [&>*:last-child]:mb-0">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h3 className="text-base font-bold text-[var(--text-primary)] mt-3 mb-1.5">{children}</h3>
          ),
          h2: ({ children }) => (
            <h4 className="text-sm font-bold text-[var(--text-primary)] mt-3 mb-1">{children}</h4>
          ),
          h3: ({ children }) => (
            <h5 className="text-sm font-semibold text-[var(--primary)] mt-2 mb-1">{children}</h5>
          ),
          p: ({ children }) => <p className="mb-2">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-[var(--text-primary)]">{children}</strong>
          ),
          ul: ({ children }) => <ul className="list-disc pl-4 mb-2 space-y-0.5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-4 mb-2 space-y-0.5">{children}</ol>,
          hr: () => <hr className="my-3 border-[var(--text-primary)]/10" />,
          table: ({ children }) => (
            <div className="overflow-x-auto my-2 rounded-lg border border-[var(--text-primary)]/10">
              <table className="w-full text-xs border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-[var(--primary)]/10">{children}</thead>
          ),
          tr: ({ children }) => (
            <tr className="border-b border-[var(--text-primary)]/10 last:border-0">{children}</tr>
          ),
          th: ({ children }) => (
            <th className="text-left font-semibold text-[var(--text-primary)] px-2.5 py-1.5 whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-2.5 py-1.5 text-[var(--text-primary)]/85 align-top">{children}</td>
          ),
          code: ({ children }) => (
            <code className="px-1 py-0.5 rounded bg-[var(--bg-page)] text-[var(--text-primary)] text-[0.85em]">
              {children}
            </code>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
