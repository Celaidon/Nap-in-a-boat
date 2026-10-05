// Same surface as api.js, but fake: no server needed. Turn it on with ?mock=1.
// Uses the same mock files as the server tests (contracts/mocks).
// In the browser console, window.blendlabMock.drop() simulates a lost connection
// and window.blendlabMock.restore() brings it back (check I5).
import mockMetrics from '@contracts/mocks/metrics.json'
import mockRegistry from '@contracts/mocks/registry.json'

const WRITING = [
  'Soft rain on the harbour wall,\n',
  'the lamps are low, the boats are small,\n',
  'and every ripple carries slow\n',
  'the hush of all the tides we know.',
]
const CODE = [
  'Here is a small, readable version:\n\n',
  '```python\n',
  'def is_prime(n):\n',
  '    if n < 2:\n',
  '        return False\n',
  '    for i in range(2, int(n ** 0.5) + 1):\n',
  '        if n % i == 0:\n',
  '            return False\n',
  '    return True\n',
  '```\n',
  'It only tests divisors up to the square root of n.',
]
const MIXED = [
  'A prime is a number with no divisors but one and itself,\n',
  'so we test each candidate and stop at its root:\n\n',
  '```python\n',
  'def is_prime(n):\n',
  '    return n > 1 and all(n % d for d in range(2, int(n ** 0.5) + 1))\n',
  '```',
]

export function createMock({ speed: initialSpeed = 1 } = {}) {
  let speed = initialSpeed
  let status = 'online'
  const listeners = new Set()
  const timers = new Map() // request id -> timeout handle
  const pendingErrors = new Map() // request id -> onError, to fail them on drop
  let nextId = 1

  const setStatus = (next) => {
    status = next
    listeners.forEach((l) => l(status))
  }
  const registryById = Object.fromEntries(mockRegistry.blends.map((b) => [b.id, b]))

  function scriptFor(blendId) {
    const t = registryById[blendId]?.t ?? 0.5
    const lines = t < 0.4 ? WRITING : t > 0.6 ? CODE : MIXED
    // Split into word-sized tokens so streaming looks like the real thing.
    return lines.join('').match(/\S+\s*|\s+/g)
  }

  function stream(id, tokens, onToken, finish) {
    let i = 0
    const startedAt = performance.now()
    const tick = () => {
      if (i >= tokens.length) {
        timers.delete(id)
        finish(((tokens.length - 1) / Math.max(0.001, (performance.now() - startedAt) / 1000)) || 0)
        return
      }
      onToken(tokens[i++])
      timers.set(id, setTimeout(tick, (28 + Math.random() * 30) / speed))
    }
    timers.set(id, setTimeout(tick, 350 / speed)) // a short "thinking" pause before the first token
  }

  const api = {
    connect() {},
    getRegistry: async () => structuredClone(mockRegistry),
    getMetrics: async () => structuredClone(mockMetrics),
    getHealth: async () => ({ status: 'ok', loaded: [], simulated: null }),

    generate(blendId, prompt, onToken, onDone, onError) {
      const id = `m${nextId++}`
      if (status !== 'online') {
        queueMicrotask(() => onError?.({ code: 'offline', message: 'Not connected to the server.' }))
        return id
      }
      if (!registryById[blendId]) {
        queueMicrotask(() => onError?.({ code: 'unknown_blend', message: `No blend called ${blendId}` }))
        return id
      }
      pendingErrors.set(id, onError)
      const tokens = scriptFor(blendId)
      stream(id, tokens, onToken, (tps) => {
        pendingErrors.delete(id)
        onDone?.({ blendId, tokens: tokens.length, tokensPerSec: Math.round(tps * 100) / 100 })
      })
      return id
    },

    cancel(id) {
      if (!timers.has(id)) return
      clearTimeout(timers.get(id))
      timers.delete(id)
      pendingErrors.get(id)?.({ code: 'cancelled', message: 'Request was cancelled' })
      pendingErrors.delete(id)
    },

    findBest(tasks, onProgress, onResult, onError) {
      const id = `m${nextId++}`
      const blends = mockRegistry.blends
      pendingErrors.set(id, onError)
      let step = 0
      const scores = {}
      const tick = () => {
        if (step === blends.length) {
          timers.delete(id)
          pendingErrors.delete(id)
          const best = Object.keys(scores).reduce((a, b) => (scores[b] > scores[a] ? b : a))
          onResult?.({ bestBlendId: best, scores })
          return
        }
        const blend = blends[step++]
        onProgress?.({ step, of: blends.length, blendId: blend.id })
        const m = mockMetrics.blends.find((x) => x.blend_id === blend.id)
        const codeWeight = tasks.filter((t) => t.kind === 'code').length / tasks.length
        scores[blend.id] = Math.round((codeWeight * m.code_pass + (1 - codeWeight) * (m.style_score / 10)) * 100) / 100
        timers.set(id, setTimeout(tick, 450 / speed))
      }
      timers.set(id, setTimeout(tick, 200 / speed))
      return id
    },

    onStatus(listener) {
      listeners.add(listener)
      listener(status)
      return () => listeners.delete(listener)
    },

    get status() {
      return status
    },

    // Test hooks for check I5.
    setSpeed(next) {
      speed = next
    },
    drop() {
      timers.forEach(clearTimeout)
      timers.clear()
      const stuck = [...pendingErrors.values()]
      pendingErrors.clear()
      setStatus('reconnecting')
      stuck.forEach((onError) => onError?.({ code: 'connection_lost', message: 'The connection to the server was lost.' }))
    },
    restore() {
      setStatus('online')
    },
    close() {},
  }
  return api
}
