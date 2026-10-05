import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApi } from './api.js'

class FakeSocket {
  static instances = []
  readyState = 0
  sent = []
  constructor(url) {
    this.url = url
    FakeSocket.instances.push(this)
  }
  send(data) {
    this.sent.push(JSON.parse(data))
  }
  close() {
    this.readyState = 3
    this.onclose?.()
  }
  open() {
    this.readyState = 1
    this.onopen?.()
  }
  receive(obj) {
    this.onmessage?.({ data: JSON.stringify(obj) })
  }
}

let api
const socket = () => FakeSocket.instances.at(-1)

beforeEach(() => {
  vi.useFakeTimers()
  FakeSocket.instances = []
  api = createApi({ WebSocketImpl: FakeSocket, wsUrl: 'ws://test/ws', backoff: { min: 100, max: 1000 } })
  api.connect()
})
afterEach(() => {
  api.close()
  vi.useRealTimers()
})

describe('generate', () => {
  it('sends the contract message and routes tokens, then done', () => {
    socket().open()
    const onToken = vi.fn()
    const onDone = vi.fn()
    const id = api.generate('sweep_050', 'hi', onToken, onDone, vi.fn(), { maxTokens: 64, temperature: 0.2 })

    expect(socket().sent[0]).toEqual({
      type: 'generate', request_id: id, blend_id: 'sweep_050', prompt: 'hi', max_tokens: 64, temperature: 0.2,
    })
    socket().receive({ type: 'token', request_id: id, text: 'Soft' })
    socket().receive({ type: 'token', request_id: id, text: ' rain' })
    socket().receive({ type: 'done', request_id: id, blend_id: 'sweep_050', tokens: 2, tokens_per_sec: 7.5 })

    expect(onToken.mock.calls).toEqual([['Soft'], [' rain']])
    expect(onDone).toHaveBeenCalledWith({ blendId: 'sweep_050', tokens: 2, tokensPerSec: 7.5 })
  })

  it('reports server errors with their code', () => {
    socket().open()
    const onError = vi.fn()
    const id = api.generate('sweep_999', 'hi', vi.fn(), vi.fn(), onError)
    socket().receive({ type: 'error', request_id: id, code: 'unknown_blend', message: 'No blend called sweep_999' })
    expect(onError).toHaveBeenCalledWith({ code: 'unknown_blend', message: 'No blend called sweep_999' })
  })

  it('keeps several requests apart on one socket', () => {
    socket().open()
    const a = vi.fn()
    const b = vi.fn()
    const idA = api.generate('sweep_000', 'x', a, vi.fn(), vi.fn())
    const idB = api.generate('sweep_100', 'x', b, vi.fn(), vi.fn())
    socket().receive({ type: 'token', request_id: idB, text: 'B' })
    socket().receive({ type: 'token', request_id: idA, text: 'A' })
    expect(a).toHaveBeenCalledWith('A')
    expect(b).toHaveBeenCalledWith('B')
  })

  it('ignores messages for unknown requests', () => {
    socket().open()
    expect(() => socket().receive({ type: 'token', request_id: 'ghost', text: 'x' })).not.toThrow()
  })

  it('cancel sends the cancel message and waits for the server reply', () => {
    socket().open()
    const onError = vi.fn()
    const id = api.generate('sweep_050', 'hi', vi.fn(), vi.fn(), onError)
    api.cancel(id)
    expect(socket().sent.at(-1)).toEqual({ type: 'cancel', request_id: id })
    expect(onError).not.toHaveBeenCalled()
    socket().receive({ type: 'error', request_id: id, code: 'cancelled', message: 'Request was cancelled' })
    expect(onError).toHaveBeenCalledWith({ code: 'cancelled', message: 'Request was cancelled' })
  })
})

describe('findBest', () => {
  it('routes progress then result', () => {
    socket().open()
    const onProgress = vi.fn()
    const onResult = vi.fn()
    const tasks = [{ kind: 'style', prompt: 'a poem' }]
    const id = api.findBest(tasks, onProgress, onResult, vi.fn())
    expect(socket().sent[0]).toEqual({ type: 'find_best', request_id: id, tasks })
    socket().receive({ type: 'progress', request_id: id, step: 3, of: 8, blend_id: 'sweep_050' })
    socket().receive({ type: 'result', request_id: id, best_blend_id: 'gradient_mid', scores: { gradient_mid: 0.7 } })
    expect(onProgress).toHaveBeenCalledWith({ step: 3, of: 8, blendId: 'sweep_050' })
    expect(onResult).toHaveBeenCalledWith({ bestBlendId: 'gradient_mid', scores: { gradient_mid: 0.7 } })
  })
})

describe('keep-alive', () => {
  it('answers ping with pong', () => {
    socket().open()
    socket().receive({ type: 'ping' })
    expect(socket().sent).toEqual([{ type: 'pong' }])
  })
})

describe('connection problems (check I5)', () => {
  it('tells the caller immediately when there is no connection', async () => {
    const onError = vi.fn()
    api.generate('sweep_050', 'hi', vi.fn(), vi.fn(), onError) // socket still connecting
    await Promise.resolve()
    expect(onError).toHaveBeenCalledWith({ code: 'offline', message: 'Not connected to the server.' })
  })

  it('fails running requests with connection_lost when the socket drops', () => {
    socket().open()
    const onError = vi.fn()
    api.generate('sweep_050', 'hi', vi.fn(), vi.fn(), onError)
    const statuses = []
    api.onStatus((s) => statuses.push(s))

    socket().close() // server stopped mid-stream

    expect(onError).toHaveBeenCalledTimes(1)
    expect(onError.mock.calls[0][0].code).toBe('connection_lost')
    expect(statuses.at(-1)).toBe('reconnecting')
  })

  it('reconnects with growing delays and goes back online', () => {
    socket().open()
    const statuses = []
    api.onStatus((s) => statuses.push(s))

    socket().close()
    expect(FakeSocket.instances).toHaveLength(1)

    vi.advanceTimersByTime(200) // first retry within the 100 ms +/- 25% window
    expect(FakeSocket.instances).toHaveLength(2)
    socket().close() // server still down

    vi.advanceTimersByTime(200) // second delay is about 200 ms, so not yet
    vi.advanceTimersByTime(200)
    expect(FakeSocket.instances).toHaveLength(3)
    socket().open() // server is back
    expect(statuses.at(-1)).toBe('online')

    const onToken = vi.fn()
    const id = api.generate('sweep_050', 'again', onToken, vi.fn(), vi.fn())
    socket().receive({ type: 'token', request_id: id, text: 'ok' })
    expect(onToken).toHaveBeenCalledWith('ok') // fully working after the outage
  })

  it('closes a link that has gone silent for too long', () => {
    socket().open()
    const first = socket()
    vi.advanceTimersByTime(60000) // no ping from the server for a minute
    expect(first.readyState).toBe(3)
    expect(api.status).toBe('reconnecting')
  })
})

describe('REST', () => {
  it('reads the registry and metrics', async () => {
    const fetchImpl = vi.fn(async (url) => ({ ok: true, json: async () => ({ url }) }))
    const rest = createApi({ WebSocketImpl: FakeSocket, wsUrl: 'ws://test/ws', fetchImpl })
    expect(await rest.getRegistry()).toEqual({ url: '/api/registry' })
    expect(await rest.getMetrics()).toEqual({ url: '/api/metrics' })
    rest.close()
  })

  it('throws a clear error when the server answers with a failure', async () => {
    const fetchImpl = vi.fn(async () => ({ ok: false, status: 500 }))
    const rest = createApi({ WebSocketImpl: FakeSocket, wsUrl: 'ws://test/ws', fetchImpl })
    await expect(rest.getRegistry()).rejects.toThrow('/api/registry returned 500')
    rest.close()
  })
})
