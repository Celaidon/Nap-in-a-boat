// Picks the real server layer or the fake one. ?mock=1 in the URL turns the fake one on.
import { createApi } from './api.js'
import { createMock } from './mock.js'

const searchMock = new URLSearchParams(globalThis.location?.search ?? '').get('mock')
const isVercel = globalThis.location?.hostname?.includes('vercel.app')
export const useMock = searchMock === '1' || (isVercel && searchMock !== '0')

export const api = useMock ? createMock() : createApi()

if (useMock) globalThis.blendlabMock = api // console helpers: blendlabMock.drop(), blendlabMock.restore()
