// The blend area: writing model (top left), code model (middle right), and a wavy line between
// them that is the slider. A handle moves along the wave and snaps to the real blends.
// The context-window meter sits on the wave. Variants and measured stats live in a popover.
import { AnimatePresence, animate, motion, useMotionValue, useTransform } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { VARIANT_INFO, describeBlend, findBlend, metricsFor, percent, sweepStops, variantBlends } from '../lib/blends.js'
import { ModelChip } from './ModelChip.jsx'

const SPRING = { type: 'spring', stiffness: 380, damping: 34, mass: 0.8 }
const CONTEXT_WINDOW = 4096 // the n_ctx the server loads models with
const AMPLITUDE = 13
const WAVES = 2.5

// Where the wave runs, for a stage of this width. Wide: from under the writing card to beside the code card.
function geometry(width) {
  const compact = width < 700
  return compact
    ? { compact, height: 200, x0: 30, x1: width - 30, y0: 112, y1: 112 }
    : { compact, height: 200, x0: 270, x1: width - 270, y0: 64, y1: 118 }
}

function pointOn(g, u) {
  const baseY = g.y0 + (g.y1 - g.y0) * u
  return { x: g.x0 + (g.x1 - g.x0) * u, y: baseY + AMPLITUDE * Math.sin(u * Math.PI * 2 * WAVES) }
}

function pathBetween(g, from, to) {
  const steps = Math.max(2, Math.round((to - from) * 80))
  let d = ''
  for (let i = 0; i <= steps; i++) {
    const p = pointOn(g, from + ((to - from) * i) / steps)
    d += `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)} ${p.y.toFixed(1)} `
  }
  return d
}

function WaveSlider({ stops, selected, onSelect, width }) {
  const g = geometry(width)
  const svg = useRef(null)
  const dragging = useRef(false)
  const u = useMotionValue(selected.t)
  const cx = useTransform(u, (v) => pointOn(g, v).x)
  const cy = useTransform(u, (v) => pointOn(g, v).y)
  const fill = useTransform(u, (v) => pathBetween(g, 0, Math.max(0.001, v)))
  const index = stops.findIndex((s) => s.id === selected.id) // -1 while a variant is selected

  // Glide to the chosen blend, unless the pointer is carrying the handle.
  useEffect(() => {
    if (dragging.current) return
    const controls = animate(u, selected.t, SPRING)
    return () => controls.stop()
  }, [selected.t, u])

  const pick = (clientX) => {
    const box = svg.current.getBoundingClientRect()
    const raw = Math.min(1, Math.max(0, (clientX - box.left - g.x0) / (g.x1 - g.x0)))
    u.set(raw)
    const nearest = stops.reduce((a, b) => (Math.abs(b.t - raw) < Math.abs(a.t - raw) ? b : a))
    if (nearest.id !== selected.id) onSelect(nearest.id)
  }
  const release = () => {
    if (!dragging.current) return
    dragging.current = false
    animate(u, selected.t, SPRING) // snap to the real blend
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
    <svg
      ref={svg}
      className="wave"
      width={width}
      height={g.height}
      viewBox={`0 0 ${width} ${g.height}`}
      onPointerDown={(e) => {
        dragging.current = true
        e.currentTarget.setPointerCapture(e.pointerId)
        pick(e.clientX)
      }}
      onPointerMove={(e) => dragging.current && pick(e.clientX)}
      onPointerUp={release}
      onPointerCancel={release}
    >
      <path d={pathBetween(g, 0, 1)} className="wave-rail" />
      <motion.path d={fill} className="wave-fill" />
      {stops.map((s) => {
        const p = pointOn(g, s.t)
        return (
          <g key={s.id} aria-hidden="true">
            <circle cx={p.x} cy={p.y} r="6" className={`wave-stop ${s.id === selected.id ? 'is-on' : ''}`} />
            <text x={p.x} y={p.y + 26} textAnchor="middle" className={`wave-label ${s.id === selected.id ? 'is-on' : ''}`}>
              {percent(s.t)}
            </text>
          </g>
        )
      })}
      <motion.circle
        cx={cx}
        cy={cy}
        r="15"
        className={`wave-thumb ${index === -1 ? 'is-variant' : ''}`}
        role="slider"
        tabIndex={0}
        aria-label="Blend between the writing model and the code model"
        aria-valuemin={0}
        aria-valuemax={stops.length - 1}
        aria-valuenow={index === -1 ? stops.findIndex((s) => s.t === 0.5) : index}
        aria-valuetext={describeBlend(selected)}
        onKeyDown={onKeyDown}
      />
    </svg>
  )
}

function ModelCard({ role, title, name, share, active, onPick }) {
  return (
    <button className={`mcard mcard-${role} ${active ? 'is-active' : ''}`} onClick={onPick} aria-pressed={active} title={`Use only the ${title.toLowerCase()}`}>
      <span className="mcard-role">{title}</span>
      <span className="mcard-name">{name}</span>
      <span className="mcard-share">
        <AnimatePresence mode="popLayout" initial={false}>
          <motion.b key={share} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.16 }}>
            {share}%
          </motion.b>
        </AnimatePresence>{' '}
        of the mix
      </span>
    </button>
  )
}

function Stat({ label, value }) {
  return (
    <span className="stat">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </span>
  )
}

export function BlendDock({ blends, pair, blendId, compareId, metrics, contextUsed = 0, onSelect, onCompare }) {
  const [open, setOpen] = useState(false)
  const [width, setWidth] = useState(900)
  const stage = useRef(null)
  const selected = findBlend(blends, blendId)
  const stops = sweepStops(blends)

  useEffect(() => {
    const el = stage.current
    if (!el) return
    setWidth(el.clientWidth || 900)
    const watcher = new ResizeObserver(() => setWidth(el.clientWidth || 900))
    watcher.observe(el)
    return () => watcher.disconnect()
  }, [selected?.id === undefined])

  if (!selected || stops.length === 0) return null

  const comparing = compareId !== null
  const others = blends.filter((b) => b.id !== selected.id)
  const m = metricsFor(metrics, selected.id)
  const g = geometry(width)
  const used = Math.min(contextUsed, CONTEXT_WINDOW)
  const toggleCompare = () => {
    if (comparing) return onCompare(null)
    const opposite = selected.t < 0.5 ? stops.at(-1) : stops[0]
    onCompare(opposite.id === selected.id ? others[0].id : opposite.id)
  }
  const shortName = (id) => (id ? id.split('/').pop() : '')

  return (
    <section className="blendbar" aria-label="Choose a blend">
      <div className="blendbar-inner">
        <div className="blendbar-head">
          <ModelChip blend={selected} />
          <div className="blendbar-actions">
            <button className={`ghost ${comparing ? 'is-active' : ''}`} onClick={toggleCompare} aria-pressed={comparing}>
              {comparing ? 'Comparing' : 'Compare'}
            </button>
            <div className="popwrap">
              <button className={`ghost ${open ? 'is-active' : ''}`} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
                Variants &amp; stats
              </button>
              <AnimatePresence>
                {open && (
                  <>
                    <button className="pop-backdrop" aria-label="Close" onClick={() => setOpen(false)} />
                    <motion.div className="pop" role="dialog" aria-label="Variants and measured results"
                      initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.97 }} transition={{ duration: 0.16 }}>
                      <p className="pop-title">Layer-wise variants</p>
                      <div className="variants" role="group" aria-label="Layer-wise variants">
                        {variantBlends(blends).map((v) => (
                          <motion.button key={v.id} className={`vchip ${v.id === selected.id ? 'is-on' : ''}`} onClick={() => onSelect(v.id)}
                            aria-pressed={v.id === selected.id} title={VARIANT_INFO[v.variant]?.hint} whileTap={{ scale: 0.96 }}>
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
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>

        <AnimatePresence initial={false}>
          {comparing && (
            <motion.div className="compare-row" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22, ease: 'easeOut' }}>
              <label className="compare-inner">
                <span>Also send to</span>
                <select value={compareId} onChange={(e) => onCompare(e.target.value)}>
                  {others.map((b) => (
                    <option key={b.id} value={b.id}>{describeBlend(b)} ({b.id})</option>
                  ))}
                </select>
              </label>
            </motion.div>
          )}
        </AnimatePresence>

        <div className="blend-stage" ref={stage} style={{ height: g.height }}>
          <WaveSlider stops={stops} selected={selected} onSelect={onSelect} width={width} />
          <ModelCard role="writing" title="Writing model" name={shortName(pair?.model_a)} share={Math.round((1 - selected.t) * 100)} active={selected.t === 0} onPick={() => onSelect(stops[0].id)} />
          <ModelCard role="code" title="Code model" name={shortName(pair?.model_b)} share={Math.round(selected.t * 100)} active={selected.t === 1} onPick={() => onSelect(stops.at(-1).id)} />
          <div className="ctx" style={{ top: g.compact ? g.height - 16 : g.height - 26 }} aria-label={`Context window: about ${used} of ${CONTEXT_WINDOW} tokens used`}>
            <span>Context window</span>
            <span className="ctx-bar"><motion.i initial={false} animate={{ width: `${(used / CONTEXT_WINDOW) * 100}%` }} transition={{ duration: 0.4 }} /></span>
            <span className="mono">{used} / {CONTEXT_WINDOW}</span>
          </div>
        </div>
      </div>
    </section>
  )
}
