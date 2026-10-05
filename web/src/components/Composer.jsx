import { AnimatePresence, motion } from 'framer-motion'
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'

export function Composer({ placeholder, ready, streaming, onSend, onStop }) {
  const [value, setValue] = useState('')
  const box = useRef(null)

  // Grow with the text, up to a limit. Measured again when the width changes (text wraps differently).
  const fit = useCallback(() => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [])

  useLayoutEffect(fit, [fit, value, placeholder])

  useEffect(() => {
    let width = box.current.offsetWidth
    const watcher = new ResizeObserver(() => {
      if (box.current.offsetWidth !== width) {
        width = box.current.offsetWidth
        fit()
      }
    })
    watcher.observe(box.current)
    return () => watcher.disconnect()
  }, [fit])

  const submit = () => {
    if (!ready || streaming || !value.trim()) return
    onSend(value.trim())
    setValue('')
  }

  return (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <textarea
        ref={box}
        rows={1}
        value={value}
        placeholder={placeholder}
        aria-label="Message"
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault()
            submit()
          }
        }}
      />
      <AnimatePresence mode="wait" initial={false}>
        {streaming ? (
          <motion.button
            key="stop" type="button" className="send is-stop" onClick={onStop} aria-label="Stop generating"
            initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.6, opacity: 0 }} transition={{ duration: 0.14 }}
          >
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><rect x="5" y="5" width="10" height="10" rx="2" fill="currentColor" /></svg>
          </motion.button>
        ) : (
          <motion.button
            key="send" type="submit" className="send" disabled={!ready || !value.trim()} aria-label="Send"
            initial={{ scale: 0.6, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.6, opacity: 0 }} transition={{ duration: 0.14 }}
            whileTap={{ scale: 0.92 }}
          >
            <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true"><path d="M10 16V4M5 9l5-5 5 5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </motion.button>
        )}
      </AnimatePresence>
    </form>
  )
}
