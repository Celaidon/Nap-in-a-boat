// Visible connection state (check I5): slides in when the link drops, confirms when it is back.
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'

export function Banner({ status }) {
  const [recovered, setRecovered] = useState(false)
  const was = useRef(status)

  useEffect(() => {
    let timer
    if (status === 'online' && was.current === 'reconnecting') {
      setRecovered(true)
      timer = setTimeout(() => setRecovered(false), 2500)
    }
    was.current = status
    return () => clearTimeout(timer)
  }, [status])

  const message =
    status === 'reconnecting'
      ? 'Connection lost. Trying to reconnect…'
      : status === 'connecting'
        ? 'Connecting to the server…'
        : recovered
          ? 'Back online.'
          : null
  const tone = status === 'online' ? 'ok' : 'warn'

  return (
    <AnimatePresence initial={false}>
      {message && (
        <motion.div
          key={tone}
          className={`banner banner-${tone}`}
          role="status"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.25, ease: 'easeOut' }}
        >
          <div className="banner-inner">
            <span className="pulse-dot" aria-hidden="true" />
            {message}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
