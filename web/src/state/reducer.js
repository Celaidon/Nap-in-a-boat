// Pure state for the chat. No network in here, so it is easy to test.
//
// A "turn" is one prompt and its answer(s): one output normally, two in compare mode.
// An output's status: streaming | done | cancelled | error.

export const initialState = {
  blends: [],
  pair: null,
  metrics: null,
  loadError: null,
  blendId: null,
  compareId: null,
  turns: [],
}

const mapOutput = (state, key, change) => ({
  ...state,
  turns: state.turns.map((turn) => ({
    ...turn,
    outputs: turn.outputs.map((out) => (out.key === key ? { ...out, ...change(out) } : out)),
  })),
})

export function reducer(state, action) {
  switch (action.type) {
    case 'loaded': {
      const stops = action.registry.blends
      // Keep an earlier choice if it is still valid, else start at the middle blend.
      const keep = stops.some((b) => b.id === state.blendId) ? state.blendId : null
      const middle = stops.find((b) => b.id === 'sweep_050') ?? stops[0]
      return { ...state, blends: stops, pair: action.registry.pair, metrics: action.metrics, loadError: null, blendId: keep ?? middle?.id ?? null }
    }
    case 'load_failed':
      return { ...state, loadError: action.message }
    case 'select_blend':
      return { ...state, blendId: action.id, compareId: state.compareId === action.id ? null : state.compareId }
    case 'set_compare':
      return { ...state, compareId: action.id === state.blendId ? null : action.id }
    case 'turn_start':
      return { ...state, turns: [...state.turns, action.turn] }
    case 'append':
      return mapOutput(state, action.key, (out) => ({ text: out.text + action.text }))
    case 'output_start': // used by retry: wipe the old attempt and stream again
      return mapOutput(state, action.key, () => ({ text: '', status: 'streaming', error: null, tokens: 0, tokensPerSec: null }))
    case 'output_done':
      return mapOutput(state, action.key, () => ({ status: 'done', tokens: action.tokens, tokensPerSec: action.tokensPerSec }))
    case 'output_error': {
      const status = action.code === 'cancelled' ? 'cancelled' : 'error'
      return mapOutput(state, action.key, () => ({
        status,
        error: status === 'error' ? { code: action.code, message: action.message } : null,
      }))
    }
    case 'clear':
      return { ...state, turns: [] }
    default:
      return state
  }
}

export const isStreaming = (state) =>
  state.turns.some((turn) => turn.outputs.some((out) => out.status === 'streaming'))
