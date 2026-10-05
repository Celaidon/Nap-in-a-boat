// The blend slider: pick which model the next message goes to. Writing on the left, code on the right.
import { AnimatePresence, motion } from 'framer-motion'
import { useRef, useState } from 'react'
import { VARIANT_INFO, describeBlend, findBlend, metricsFor, percent, sweepStops, variantBlends } from '../lib/blends.js'
import { ModelChip } from './ModelChip.jsx'

const SPRING = { type: 'spring', stiffness: 520, damping: 38, mass: 0.7 }

function BlendSlider({ stops, selected, onSelect }) {
  const track = useRef(null)
  const [dragT, setDragT] = useState(null) // raw pointer position while dragging, else null
  const index = stops.findIndex((s) => s.id === selected.id) // -1 while a variant is selected
  const position = dragT ?? selected.t

  const pick = (clientX) => {
    const box = track.current.getBoundingClientRect()
    const raw = Math.min(1, Math.max(0, (clientX - box.left) / box.width))
    const nearest = stops.reduce((a, b) => (Math.abs(b.t - raw) < Math.abs(a.t - raw) ? b : a))
    setDragT(raw)
    if (nearest.id !== selected.id) onSelect(nearest.id)
  }

  const step = (delta) => {
    const from = index === -1 ? stops.findIndex((s) => s.t === 0.5) : index
    const next = stops[Math.min(stops.length - 1, Math.max(0, from + delta))]
    if (next) onSelect(next.id)
  }

  const onKeyDown = (e) => {
    const moves = { ArrowLeft: -1, ArrowDown: -1, ArrowRight: 1, ArrowUp: 1 }
    if (e.key in moves) {
      e.preventDefault()
      step(moves[e.key])
    } else if (e.key === 'Home') onSelect(stops[0].id)
    else if (e.key === 'End') onSelect(stops.at(-1).id)
  }

  return (
    <div className="slider">
      <div className="slider-ends" aria-hidden="true">
        <span>Writing</span>
        <span>Code</span>
      </div>
      <div
        className="slider-track"
        ref={track}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          pick(e.clientX)
        }}
        onPointerMove={(e) => e.currentTarget.hasPointerCapture(e.pointerId) && pick(e.clientX)}
        onPointerUp={() => setDragT(null)}
        onPointerCancel={() => setDragT(null)}
      >
        <div className="slider-rail" />
        <motion.div
          className="slider-fill"
          initial={false}
          animate={{ width: `${position * 100}%` }}
          transition={dragT === null ? SPRING : { duration: 0 }}
        />
        {stops.map((s) => (
          <span key={s.id} className={`slider-stop ${s.t <= position ? 'is-passed' : ''}`} style={{ left: `${s.t * 100}%` }} aria-hidden="true" />
        ))}
        <motion.div
          className={`slider-thumb ${index === -1 ? 'is-variant' : ''} ${dragT !== null ? 'is-dragging' : ''}`}
          role="slider"
          tabIndex={0}
          aria-label="Blend between the writing model and the code model"
          aria-valuemin={0}
          aria-valuemax={stops.length - 1}
          aria-valuenow={index === -1 ? stops.findIndex((s) => s.t === 0.5) : index}
          aria-valuetext={describeBlend(selected)}
          onKeyDown={onKeyDown}
          initial={false}
          animate={{ left: `${position * 100}%` }}
          transition={dragT === null ? SPRING : { duration: 0 }}
        />
      </div>
      <div className="slider-ticks" aria-hidden="true">
        {stops.map((s) => (
          <span key={s.id} className={s.id === selected.id ? 'is-on' : ''} style={{ left: `${s.t * 100}%` }}>
            {percent(s.t)}
          </span>
        ))}
      </div>
    </div>
  )
}

function Stat({ label, value }) {
  return (
    <span className="stat">
      <span className="stat-label">{label}</span>
      <AnimatePresence mode="popLayout" initial={false}>
        <motion.span
          key={value}
          className="stat-value"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.16 }}
        >
          {value}
        </motion.span>
      </AnimatePresence>
    </span>
  )
}

export function BlendDock({ blends, blendId, compareId, metrics, onSelect, onCompare }) {
  const selected = findBlend(blends, blendId)
  const stops = sweepStops(blends)
  const variants = variantBlends(blends)
  const comparing = compareId !== null
  if (!selected || stops.length === 0) return null

  const m = metricsFor(metrics, selected.id)
  const others = blends.filter((b) => b.id !== selected.id)

  const toggleCompare = () => {
    if (comparing) return onCompare(null)
    const opposite = selected.t < 0.5 ? stops.at(-1) : stops[0]
    onCompare(opposite.id === selected.id ? others[0].id : opposite.id)
  }

  return (
    <section className="dock" aria-label="Choose a blend">
      <div className="dock-head">
        <ModelChip blend={selected} />
        <button className={`ghost ${comparing ? 'is-active' : ''}`} onClick={toggleCompare} aria-pressed={comparing}>
          {comparing ? 'Comparing' : 'Compare with another'}
        </button>
      </div>

      <BlendSlider stops={stops} selected={selected} onSelect={onSelect} />

      <div className="dock-row">
      <div className="variants" role="group" aria-label="Layer-wise variants">
        <span className="variants-label">Variants</span>
        {variants.map((v) => (
          <motion.button
            key={v.id}
            className={`vchip ${v.id === selected.id ? 'is-on' : ''}`}
            onClick={() => onSelect(v.id)}
            aria-pressed={v.id === selected.id}
            title={VARIANT_INFO[v.variant]?.hint}
            whileTap={{ scale: 0.96 }}
          >
            {VARIANT_INFO[v.variant]?.name ?? v.label}
          </motion.button>
        ))}
      </div>

      {m && (
        <div className="stats" aria-label="Measured results for this blend">
          <Stat label="Code pass" value={`${Math.round(m.code_pass * 100)}%`} />
          <Stat label="Style" value={`${m.style_score.toFixed(1)} / 10`} />
          <Stat label="Speed" value={`${m.tokens_per_sec.toFixed(1)} tok/s`} />
        </div>
      )}
      </div>

      <AnimatePresence initial={false}>
        {comparing && (
          <motion.div
            className="compare-row"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: 'easeOut' }}
          >
            <label className="compare-inner">
              <span>Also send to</span>
              <select value={compareId} onChange={(e) => onCompare(e.target.value)}>
                {others.map((b) => (
                  <option key={b.id} value={b.id}>
                    {describeBlend(b)} ({b.id})
                  </option>
                ))}
              </select>
            </label>
          </motion.div>
        )}
      </AnimatePresence>

    </section>
  )
}
