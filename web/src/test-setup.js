import '@testing-library/jest-dom/vitest'

// jsdom lacks these browser features; the app only needs harmless stand-ins.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.matchMedia ??= (query) => ({
  matches: false, media: query, addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {},
})
HTMLCanvasElement.prototype.getContext = () => null // Chart.js is not drawn in tests
