// Best Blend Finder: up to 3 example tasks, the server tests every blend and recommends one.
import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { describeBlend, findBlend } from '../lib/blends.js'

const MAX_TASKS = 3
const blank = () => ({ kind: 'style', prompt: '', entry_point: '', tests: '' })
const EXAMPLE = [
  { kind: 'code', prompt: 'Write a function is_prime(n) that returns True for prime numbers.', entry_point: 'is_prime', tests: 'assert is_prime(7)\nassert not is_prime(8)' },
  { kind: 'style', prompt: 'Write a short poem about the sea.', entry_point: '', tests: '' },
]

const FRIENDLY = {
  busy: 'Another finder run is in progress. Try again shortly.',
  connection_lost: 'The connection dropped during the run.',
  offline: 'Not connected to the server right now.',
}

function problemWith(tasks) {
  for (const [i, t] of tasks.entries()) {
    if (!t.prompt.trim()) return `Task ${i + 1} needs a prompt.`
    if (t.kind === 'code' && (!t.entry_point.trim() || !t.tests.trim())) return `Task ${i + 1} is a code task: add the function name and its test lines.`
  }
  return null
}

const clean = (t) =>
  t.kind === 'code'
    ? { kind: 'code', prompt: t.prompt.trim(), entry_point: t.entry_point.trim(), tests: t.tests.trim() }
    : { kind: 'style', prompt: t.prompt.trim() }

export function FinderPanel({ api, blends, ready, onUse }) {
  const [tasks, setTasks] = useState([blank()])
  const [phase, setPhase] = useState('idle') // idle | running | done | error
  const [progress, setProgress] = useState(null)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const request = useRef(null)

  useEffect(() => () => request.current && api.cancel(request.current), [api])

  const update = (i, change) => setTasks((all) => all.map((t, j) => (j === i ? { ...t, ...change } : t)))
  const invalid = problemWith(tasks)

  const run = () => {
    setPhase('running')
    setProgress(null)
    setResult(null)
    setError(null)
    request.current = api.findBest(
      tasks.map(clean),
      (p) => setProgress(p),
      (r) => { request.current = null; setResult(r); setPhase('done') },
      (e) => { request.current = null; if (e.code === 'cancelled') return setPhase('idle'); setError(FRIENDLY[e.code] ?? e.message); setPhase('error') },
    )
  }

  const running = phase === 'running'
  const ranked = result ? Object.entries(result.scores).sort((a, b) => b[1] - a[1]) : []
  const label = (id) => describeBlend(findBlend(blends, id)) || id

  return (
    <div className="finder">
      <p className="lead">Give up to three example tasks. The server runs every blend on them and recommends the best one for your use.</p>

      <div className="tasks">
        <AnimatePresence initial={false}>
          {tasks.map((t, i) => (
            <motion.fieldset key={i} className="task" disabled={running}
              initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} transition={{ duration: 0.2 }}>
              <legend className="sr-only">Task {i + 1}</legend>
              <div className="task-head">
                <span className="task-n">{i + 1}</span>
                <div className="seg" role="group" aria-label={`Kind of task ${i + 1}`}>
                  {['style', 'code'].map((k) => (
                    <button key={k} type="button" className={t.kind === k ? 'is-on' : ''} aria-pressed={t.kind === k} onClick={() => update(i, { kind: k })}>
                      {k === 'style' ? 'Writing' : 'Code'}
                    </button>
                  ))}
                </div>
                {tasks.length > 1 && (
                  <button type="button" className="link" onClick={() => setTasks((all) => all.filter((_, j) => j !== i))}>Remove</button>
                )}
              </div>
              <textarea rows={2} placeholder={t.kind === 'code' ? 'Describe the function to write…' : 'What should it write?'} value={t.prompt} onChange={(e) => update(i, { prompt: e.target.value })} aria-label={`Prompt for task ${i + 1}`} />
              {t.kind === 'code' && (
                <>
                  <input placeholder="Function name, e.g. is_prime" value={t.entry_point} onChange={(e) => update(i, { entry_point: e.target.value })} aria-label="Function name" />
                  <textarea className="mono" rows={2} placeholder={'assert is_prime(7)\nassert not is_prime(8)'} value={t.tests} onChange={(e) => update(i, { tests: e.target.value })} aria-label="Test lines" />
                </>
              )}
            </motion.fieldset>
          ))}
        </AnimatePresence>
      </div>

      <div className="finder-actions">
        {tasks.length < MAX_TASKS && !running && <button className="ghost" onClick={() => setTasks((a) => [...a, blank()])}>Add task</button>}
        {!running && <button className="link" onClick={() => setTasks(EXAMPLE)}>Fill an example</button>}
      </div>

      {invalid && phase === 'idle' && tasks.some((t) => t.prompt) && <p className="hint">{invalid}</p>}

      {running ? (
        <button className="primary" onClick={() => request.current && api.cancel(request.current)}>Cancel</button>
      ) : (
        <button className="primary" disabled={!ready || Boolean(invalid)} onClick={run}>Find the best blend</button>
      )}

      <AnimatePresence mode="wait">
        {running && (
          <motion.div key="progress" className="progress" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="bar"><motion.i animate={{ width: `${progress ? (progress.step / progress.of) * 100 : 4}%` }} transition={{ type: 'spring', stiffness: 120, damping: 20 }} /></div>
            <p>{progress ? <>Testing <strong>{label(progress.blendId)}</strong> · {progress.step} of {progress.of}</> : 'Starting…'}</p>
            <p className="hint">Every blend generates real answers, so this can take a while.</p>
          </motion.div>
        )}
        {phase === 'error' && (
          <motion.p key="error" className="problem inline" role="alert" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{error}</motion.p>
        )}
        {phase === 'done' && result && (
          <motion.div key="result" className="result" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <p className="eyebrow">Recommended</p>
            <h3 className="display">{label(result.bestBlendId)}</h3>
            <p className="mono">{result.bestBlendId}</p>
            <button className="primary" onClick={() => onUse(result.bestBlendId)}>Use this blend</button>
            <ol className="scores">
              {ranked.map(([id, score], i) => (
                <li key={id} className={id === result.bestBlendId ? 'is-best' : ''}>
                  <span>{label(id)}</span>
                  <span className="bar"><motion.i initial={{ width: 0 }} animate={{ width: `${score * 100}%` }} transition={{ delay: i * 0.04, duration: 0.5, ease: 'easeOut' }} /></span>
                  <span className="mono">{score.toFixed(2)}</span>
                </li>
              ))}
            </ol>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
