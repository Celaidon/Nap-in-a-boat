// Renders model text: plain paragraphs plus fenced code blocks. Works on half-finished
// text too, so a code block that is still streaming already looks like code.
import { useState } from 'react'

export function parseBlocks(text) {
  const parts = []
  const fence = /```([\w+-]*)\n?([\s\S]*?)(?:```|$)/g
  let last = 0
  let match
  while ((match = fence.exec(text)) !== null) {
    if (match.index > last) parts.push({ type: 'text', value: text.slice(last, match.index) })
    parts.push({ type: 'code', lang: match[1], value: match[2].replace(/\n$/, '') })
    last = fence.lastIndex
  }
  if (last < text.length) parts.push({ type: 'text', value: text.slice(last) })
  // Blank lines around a code block would show as extra gaps, so trim them.
  return parts
    .map((p) => (p.type === 'text' ? { ...p, value: p.value.replace(/^\n+|\n+$/g, '') } : p))
    .filter((p) => p.type === 'code' || p.value !== '')
}

export function CopyButton({ text, label = 'Copy' }) {
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setDone(true)
      setTimeout(() => setDone(false), 1400)
    } catch {
      /* clipboard blocked: nothing useful to show */
    }
  }
  return (
    <button className="copy" onClick={copy} aria-live="polite">
      {done ? 'Copied' : label}
    </button>
  )
}

export function RichText({ text }) {
  return parseBlocks(text).map((part, i) =>
    part.type === 'code' ? (
      <figure className="code" key={i}>
        <figcaption>
          <span className="mono">{part.lang || 'code'}</span>
          <CopyButton text={part.value} />
        </figcaption>
        <pre>
          <code>{part.value}</code>
        </pre>
      </figure>
    ) : (
      <p className="prose" key={i}>
        {part.value}
      </p>
    ),
  )
}
