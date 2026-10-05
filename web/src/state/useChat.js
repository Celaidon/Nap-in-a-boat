// Connects the reducer to the API. Tokens are buffered and applied once per animation
// frame, so a fast stream causes one render per frame instead of one per token.
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react'
import { initialState, isStreaming, reducer } from './reducer.js'

let counter = 0
const nextKey = () => `o${++counter}`

export function useChat(api) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [status, setStatus] = useState(api.status)
  const requests = useRef(new Map()) // output key -> request id
  const buffers = useRef(new Map()) // output key -> text waiting for the next frame
  const frame = useRef(0)

  useEffect(() => api.onStatus(setStatus), [api])

  useEffect(() => {
    let alive = true
    api.connect()
    Promise.all([api.getRegistry(), api.getMetrics()])
      .then(([registry, metrics]) => alive && dispatch({ type: 'loaded', registry, metrics }))
      .catch((err) => alive && dispatch({ type: 'load_failed', message: err.message }))
    return () => {
      alive = false
    }
  }, [api])

  const flush = useCallback(() => {
    frame.current = 0
    buffers.current.forEach((text, key) => dispatch({ type: 'append', key, text }))
    buffers.current.clear()
  }, [])

  const run = useCallback(
    (key, blendId, prompt) => {
      const finish = (action) => {
        cancelAnimationFrame(frame.current)
        flush() // apply waiting tokens first so the end never overtakes the text
        requests.current.delete(key)
        dispatch({ ...action, key })
      }
      const id = api.generate(
        blendId,
        prompt,
        (text) => {
          buffers.current.set(key, (buffers.current.get(key) ?? '') + text)
          if (!frame.current) frame.current = requestAnimationFrame(flush)
        },
        ({ tokens, tokensPerSec }) => finish({ type: 'output_done', tokens, tokensPerSec }),
        ({ code, message }) => finish({ type: 'output_error', code, message }),
      )
      requests.current.set(key, id)
    },
    [api, flush],
  )

  const send = useCallback(
    (prompt) => {
      const targets = [state.blendId, state.compareId].filter(Boolean)
      if (!prompt.trim() || targets.length === 0) return
      const outputs = targets.map((blendId) => ({
        key: nextKey(), blendId, text: '', status: 'streaming', error: null, tokens: 0, tokensPerSec: null,
      }))
      dispatch({ type: 'turn_start', turn: { id: nextKey(), prompt, outputs } })
      outputs.forEach((out) => run(out.key, out.blendId, prompt))
    },
    [run, state.blendId, state.compareId],
  )

  const stop = useCallback(() => {
    requests.current.forEach((id) => api.cancel(id))
  }, [api])

  const retry = useCallback(
    (turnId, key) => {
      const turn = state.turns.find((t) => t.id === turnId)
      const out = turn?.outputs.find((o) => o.key === key)
      if (!out) return
      dispatch({ type: 'output_start', key })
      run(key, out.blendId, turn.prompt)
    },
    [run, state.turns],
  )

  useEffect(() => () => cancelAnimationFrame(frame.current), [])

  return useMemo(
    () => ({
      state,
      status,
      streaming: isStreaming(state),
      selectBlend: (id) => dispatch({ type: 'select_blend', id }),
      setCompare: (id) => dispatch({ type: 'set_compare', id }),
      clear: () => dispatch({ type: 'clear' }),
      send,
      stop,
      retry,
    }),
    [state, status, send, stop, retry],
  )
}
