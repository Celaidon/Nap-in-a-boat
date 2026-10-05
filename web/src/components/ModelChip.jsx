// Shows which model a message goes to (or came from). The label crossfades when the blend changes.
import { AnimatePresence, motion } from 'framer-motion'
import { describeBlend, percent } from '../lib/blends.js'

// A small dial: how much of the code model is in the mix (empty = writing, full = code).
export function Dial({ t, size = 16 }) {
  const r = size / 2 - 2
  const c = 2 * Math.PI * r
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" className="dial">
      <circle cx={size / 2} cy={size / 2} r={r} fill="var(--blush)" stroke="var(--maroon)" strokeWidth="2" />
      <motion.circle
        cx={size / 2} cy={size / 2} r={r / 2} fill="none" stroke="var(--maroon)" strokeWidth={r}
        strokeDasharray={c / 2}
        initial={false}
        animate={{ strokeDashoffset: (c / 2) * (1 - t) }}
        transition={{ type: 'spring', stiffness: 260, damping: 28 }}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  )
}

export function ModelChip({ blend, size = 'md' }) {
  if (!blend) return null
  return (
    <span className={`chip chip-${size}`} title={blend.description}>
      <Dial t={blend.t} size={size === 'sm' ? 14 : 18} />
      <span className="chip-text">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.span
            key={blend.id}
            className="chip-name"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
          >
            {describeBlend(blend)}
          </motion.span>
        </AnimatePresence>
        <span className="chip-id mono">
          {blend.id} · {blend.quant}
          {blend.variant === 'uniform' ? ` · t=${percent(blend.t)}` : ''}
        </span>
      </span>
    </span>
  )
}
