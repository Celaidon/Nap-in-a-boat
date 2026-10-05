// Picks the real server layer or the fake one.
// Demo mode: ?mock=1 in the URL, or VITE_FORCE_MOCK=1 at build time (for a static host with no backend).
// Remote backend: VITE_API_BASE=https://your-server (the page and the server are on different hosts).
import { createApi } from './api.js'
import { createMock } from './mock.js'

export const useMock =
  import.meta.env.VITE_FORCE_MOCK === '1' || new URLSearchParams(globalThis.location?.search ?? '').get('mock') === '1'

const base = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export const api = useMock
  ? createMock()
  : createApi(base ? { baseUrl: base, wsUrl: `${base.replace(/^http/, 'ws')}/ws` } : {})

if (useMock) globalThis.blendlabMock = api // console helpers: blendlabMock.drop(), blendlabMock.restore()
