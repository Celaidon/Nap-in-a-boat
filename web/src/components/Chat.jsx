import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { findBlend } from '../lib/blends.js'
import { Boat } from './Boat.jsx'
import { ModelChip } from './ModelChip.jsx'
import { CopyButton, RichText } from './RichText.jsx'

const FRIENDLY = {
  busy: 'This model is busy with other requests. Try again in a moment.',
  connection_lost: 'The connection dropped while this was generating.',
  offline: 'Not connected to the server right now.',
  unknown_blend: 'The server does not know this blend.',
}

const SUGGESTIONS = [
  { tag: 'Writing', text: 'Write an eight-line rhyming poem about a city at night.' },
  { tag: 'Code', text: 'Write a Python function is_prime(n) and explain it in two sentences.' },
  { tag: 'Both', text: 'Explain recursion like a bedtime story, then show it in code.' },
]

function Thinking() {
  return (
    <span className="thinking" aria-label="Thinking">
      <i /> <i /> <i />
    </span>
  )
}

function Output({ out, blend, turnId, onRetry }) {
  const streaming = out.status === 'streaming'
  return (
    <article className={`answer answer-${out.status}`} aria-busy={streaming}>
      <header className="answer-head">
        <span className="avatar" aria-hidden="true">
          <Boat />
        </span>
        <ModelChip blend={blend} size="sm" />
      </header>

      <div className="answer-body">
        {streaming && out.text === '' ? <Thinking /> : <RichText text={out.text} />}
        {streaming && out.text !== '' && <span className="caret" aria-hidden="true" />}
      </div>

      {out.status === 'error' && (
        <div className="problem" role="alert">
          <p>{FRIENDLY[out.error.code] ?? out.error.message}</p>
          <button className="ghost" onClick={() => onRetry(turnId, out.key)}>
            Try again
          </button>
        </div>
      )}

      <footer className="answer-foot">
        {out.status === 'done' && (
          <span className="meta mono">
            {out.tokens} tokens{out.tokensPerSec ? ` · ${out.tokensPerSec} tok/s` : ''}
          </span>
        )}
        {out.status === 'cancelled' && <span className="meta">Stopped</span>}
        {out.text && !streaming && <CopyButton text={out.text} label="Copy answer" />}
      </footer>
    </article>
  )
}

function Turn({ turn, blends, onRetry }) {
  return (
    <motion.section
      className="turn"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.26, ease: [0.22, 0.8, 0.28, 1] }}
    >
      <p className="ask">{turn.prompt}</p>
      <div className={`answers answers-${turn.outputs.length}`}>
        {turn.outputs.map((out) => (
          <Output key={out.key} out={out} blend={findBlend(blends, out.blendId)} turnId={turn.id} onRetry={onRetry} />
        ))}
      </div>
    </motion.section>
  )
}

function EmptyState({ onPick, ready }) {
  return (
    <motion.div className="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.3 }}>
      <motion.div
        className="empty-boat"
        animate={{ y: [0, -7, 0], rotate: [-1.5, 1.5, -1.5] }}
        transition={{ duration: 5.5, repeat: Infinity, ease: 'easeInOut' }}
      >
        <Boat title="A little rowboat" />
      </motion.div>
      <h1 className="display">Pick a blend.<br />Ask anything.</h1>
      <p className="empty-sub">Slide between the writing model and the code model, and watch the same question change.</p>
      <ul className="suggestions">
        {SUGGESTIONS.map((s, i) => (
          <motion.li key={s.text} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.12 + i * 0.07, duration: 0.3 }}>
            <button className="suggestion" disabled={!ready} onClick={() => onPick(s.text)}>
              <span className="suggestion-tag">{s.tag}</span>
              {s.text}
            </button>
          </motion.li>
        ))}
      </ul>
    </motion.div>
  )
}

export function Chat({ turns, blends, ready, onSend, onRetry }) {
  const scroller = useRef(null)
  const [pinned, setPinned] = useState(true) // follow new text unless the reader scrolled up

  useEffect(() => {
    const el = scroller.current
    if (!el) return
    if (turns.length === 0) el.scrollTop = 0 // the empty state starts at the top
    else if (pinned) el.scrollTop = el.scrollHeight
  }, [turns, pinned])

  const onScroll = () => {
    const el = scroller.current
    setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 80)
  }

  return (
    <div className="chat-wrap">
      <div className="chat" ref={scroller} onScroll={onScroll} role="log" aria-live="off" aria-label="Conversation">
        <div className="chat-inner">
          <AnimatePresence mode="wait">
            {turns.length === 0 ? (
              <EmptyState key="empty" onPick={onSend} ready={ready} />
            ) : (
              <motion.div key="turns" className="turns" initial={false}>
                {turns.map((turn) => (
                  <Turn key={turn.id} turn={turn} blends={blends} onRetry={onRetry} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <AnimatePresence>
        {!pinned && turns.length > 0 && (
          <motion.button
            className="jump"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 8 }}
            onClick={() => setPinned(true)}
          >
            Jump to latest
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  )
}
