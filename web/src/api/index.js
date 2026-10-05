// Picks the real server layer or the fake one. ?mock=1 in the URL turns the fake one on.
import { createApi } from './api.js'
import { createMock } from './mock.js'

export const useMock = new URLSearchParams(globalThis.location?.search ?? '').get('mock') === '1'

export const api = useMock ? createMock() : createApi()

if (useMock) globalThis.blendlabMock = api // console helpers: blendlabMock.drop(), blendlabMock.restore()
