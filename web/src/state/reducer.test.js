import { describe, expect, it } from 'vitest'
import metrics from '../../../contracts/mocks/metrics.json'
import registry from '../../../contracts/mocks/registry.json'
import { initialState, isStreaming, reducer } from './reducer.js'

const out = (key, extra = {}) => ({
  key, blendId: 'sweep_050', text: '', status: 'streaming', error: null, tokens: 0, tokensPerSec: null, ...extra,
})
const withTurn = (outputs) => reducer(initialState, { type: 'turn_start', turn: { id: 't1', prompt: 'hi', outputs } })

describe('reducer', () => {
  it('starts on the middle blend after loading', () => {
    const s = reducer(initialState, { type: 'loaded', registry, metrics })
    expect(s.blendId).toBe('sweep_050')
    expect(s.blends).toHaveLength(8)
  })

  it('keeps a valid earlier choice when data reloads', () => {
    let s = reducer(initialState, { type: 'loaded', registry, metrics })
    s = reducer(s, { type: 'select_blend', id: 'sweep_100' })
    s = reducer(s, { type: 'loaded', registry, metrics })
    expect(s.blendId).toBe('sweep_100')
  })

  it('never compares a blend with itself', () => {
    let s = reducer(initialState, { type: 'loaded', registry, metrics })
    s = reducer(s, { type: 'set_compare', id: 'sweep_000' })
    expect(s.compareId).toBe('sweep_000')
    expect(reducer(s, { type: 'set_compare', id: 'sweep_050' }).compareId).toBeNull()
    expect(reducer(s, { type: 'select_blend', id: 'sweep_000' }).compareId).toBeNull()
  })

  it('appends tokens to the right output only', () => {
    let s = withTurn([out('a'), out('b')])
    s = reducer(s, { type: 'append', key: 'a', text: 'Soft ' })
    s = reducer(s, { type: 'append', key: 'a', text: 'rain' })
    expect(s.turns[0].outputs.map((o) => o.text)).toEqual(['Soft rain', ''])
  })

  it('finishes outputs and reports streaming state', () => {
    let s = withTurn([out('a')])
    expect(isStreaming(s)).toBe(true)
    s = reducer(s, { type: 'output_done', key: 'a', tokens: 5, tokensPerSec: 9.1 })
    expect(s.turns[0].outputs[0]).toMatchObject({ status: 'done', tokens: 5, tokensPerSec: 9.1 })
    expect(isStreaming(s)).toBe(false)
  })

  it('treats cancelled as a quiet stop, but other errors as errors', () => {
    let s = withTurn([out('a', { text: 'partial' }), out('b')])
    s = reducer(s, { type: 'output_error', key: 'a', code: 'cancelled', message: 'x' })
    s = reducer(s, { type: 'output_error', key: 'b', code: 'connection_lost', message: 'lost' })
    const [a, b] = s.turns[0].outputs
    expect(a).toMatchObject({ status: 'cancelled', error: null, text: 'partial' }) // partial text is kept
    expect(b).toMatchObject({ status: 'error', error: { code: 'connection_lost', message: 'lost' } })
  })

  it('restarts an output for retry', () => {
    let s = withTurn([out('a', { text: 'half', status: 'error', error: { code: 'offline', message: 'x' } })])
    s = reducer(s, { type: 'output_start', key: 'a' })
    expect(s.turns[0].outputs[0]).toMatchObject({ text: '', status: 'streaming', error: null })
  })
})
