// Picks the real server layer or the fake one. ?mock=1 in the URL turns the fake one on.
import { createApi } from './api.js'
import { createMock } from './mock.js'

const searchParams = new URLSearchParams(globalThis.location?.search ?? '')
const searchMock = searchParams.get('mock')
const customApiUrl = searchParams.get('api') || import.meta.env?.VITE_API_URL || ''

const isVercel = globalThis.location?.hostname?.includes('vercel.app')
export const useMock = searchMock === '1' || (isVercel && searchMock !== '0' && !customApiUrl)

export const api = useMock ? createMock() : createApi({ baseUrl: customApiUrl })

if (useMock) globalThis.blendlabMock = api
