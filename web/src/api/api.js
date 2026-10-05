// The only file that talks to the server: REST calls plus one shared WebSocket.
// Matches contracts 4.3 and 4.4. Every request carries a request_id, and one socket
// carries many requests at once.
//
//   api.getRegistry() / api.getMetrics()
//   api.generate(blendId, prompt, onToken, onDone, onError, opts) -> request id
//   api.cancel(id)
//   api.findBest(tasks, onProgress, onResult, onError) -> request id
//   api.onStatus(listener) -> unsubscribe     status: connecting | online | reconnecting
//
// Errors reach onError as { code, message }. Server codes are unknown_blend, busy,
// bad_request, cancelled, internal. This file adds connection_lost and offline.

const WATCHDOG_MS = 5000
const SILENCE_LIMIT_MS = 50000 // the server pings every 20 s, so this much silence means a dead link

export function createApi({
  baseUrl = '',
  WebSocketImpl = globalThis.WebSocket,
  fetchImpl = (...args) => globalThis.fetch(...args),
  backoff = { min: 500, max: 8000 },
  wsUrl,
} = {}) {
  let socket = null
  let status = 'connecting'
  let retryTimer = null
  let attempt = 0
  let lastHeard = 0
  let watchdog = null
  let closedForGood = false
  const pending = new Map() // request id -> handlers
  const listeners = new Set()

  const makeId = () =>
    globalThis.crypto?.randomUUID?.() ?? `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`

  const resolveWsUrl = () => {
    if (wsUrl) return wsUrl
    const loc = globalThis.location
    return `${loc.protocol === 'https:' ? 'wss' : 'ws'}://${loc.host}/ws`
  }

  function setStatus(next) {
    if (next === status) return
    status = next
    listeners.forEach((l) => l(status))
  }

  function failAll(code, message) {
    const stuck = [...pending.values()]
    pending.clear()
    stuck.forEach((h) => h.onError?.({ code, message }))
  }

  function connect() {
    if (closedForGood || socket) return
    setStatus(attempt === 0 ? 'connecting' : 'reconnecting')
    let ws
    try {
      ws = new WebSocketImpl(resolveWsUrl())
    } catch {
      scheduleReconnect()
      return
    }
    socket = ws
    ws.onopen = () => {
      attempt = 0
      lastHeard = Date.now()
      setStatus('online')
    }
    ws.onmessage = (event) => {
      lastHeard = Date.now()
      let msg
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }
      route(msg)
    }
    ws.onclose = () => {
      if (socket === ws) socket = null
      failAll('connection_lost', 'The connection to the server was lost.')
      if (!closedForGood) scheduleReconnect()
    }
    ws.onerror = () => {} // onclose always follows and does the work
  }

  function scheduleReconnect() {
    setStatus('reconnecting')
    clearTimeout(retryTimer)
    const base = Math.min(backoff.max, backoff.min * 2 ** attempt)
    attempt += 1
    retryTimer = setTimeout(connect, base * (0.75 + Math.random() * 0.5)) // jitter so clients do not stampede
  }

  function route(msg) {
    if (msg.type === 'ping') {
      send({ type: 'pong' })
      return
    }
    const h = pending.get(msg.request_id)
    if (!h) return
    switch (msg.type) {
      case 'token':
        h.onToken?.(msg.text)
        break
      case 'done':
        pending.delete(msg.request_id)
        h.onDone?.({ blendId: msg.blend_id, tokens: msg.tokens, tokensPerSec: msg.tokens_per_sec })
        break
      case 'progress':
        h.onProgress?.({ step: msg.step, of: msg.of, blendId: msg.blend_id })
        break
      case 'result':
        pending.delete(msg.request_id)
        h.onResult?.({ bestBlendId: msg.best_blend_id, scores: msg.scores })
        break
      case 'error':
        pending.delete(msg.request_id)
        h.onError?.({ code: msg.code, message: msg.message })
        break
    }
  }

  function send(obj) {
    if (socket && socket.readyState === 1) {
      socket.send(JSON.stringify(obj))
      return true
    }
    return false
  }

  function start(message, handlers) {
    const id = makeId()
    pending.set(id, handlers)
    if (!send({ ...message, request_id: id })) {
      pending.delete(id)
      // Report asynchronously so callers can finish setting up before the error arrives.
      queueMicrotask(() => handlers.onError?.({ code: 'offline', message: 'Not connected to the server.' }))
    }
    return id
  }

  async function getJson(path) {
    const response = await fetchImpl(baseUrl + path)
    if (!response.ok) throw new Error(`${path} returned ${response.status}`)
    return response.json()
  }

  watchdog = setInterval(() => {
    if (socket && socket.readyState === 1 && Date.now() - lastHeard > SILENCE_LIMIT_MS) socket.close()
  }, WATCHDOG_MS)

  return {
    connect,
    getRegistry: () => getJson('/api/registry'),
    getMetrics: () => getJson('/api/metrics'),
    getHealth: () => getJson('/health'),

    generate(blendId, prompt, onToken, onDone, onError, opts = {}) {
      const message = { type: 'generate', blend_id: blendId, prompt }
      if (opts.maxTokens) message.max_tokens = opts.maxTokens
      if (opts.temperature !== undefined) message.temperature = opts.temperature
      return start(message, { onToken, onDone, onError })
    },

    cancel(id) {
      // Only the server's `cancelled` reply ends the request, so late tokens are never shown after it.
      send({ type: 'cancel', request_id: id })
    },

    findBest(tasks, onProgress, onResult, onError) {
      return start({ type: 'find_best', tasks }, { onProgress, onResult, onError })
    },

    onStatus(listener) {
      listeners.add(listener)
      listener(status)
      return () => listeners.delete(listener)
    },

    get status() {
      return status
    },

    close() {
      closedForGood = true
      clearTimeout(retryTimer)
      clearInterval(watchdog)
      socket?.close()
    },
  }
}
