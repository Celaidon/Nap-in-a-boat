import path from 'node:path'
import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const here = path.dirname(fileURLToPath(import.meta.url))
const backend = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  resolve: {
    // The mock layer reads the same mock files the server tests use.
    alias: { '@contracts': path.resolve(here, '../contracts') },
  },
  server: {
    port: 5173,
    fs: { allow: ['..'] },
    // npm run dev talks to `uvicorn src.server.main:app --port 8000`.
    proxy: {
      '/api': backend,
      '/health': backend,
      '/ws': { target: backend.replace('http', 'ws'), ws: true },
    },
  },
  build: { outDir: 'dist', chunkSizeWarningLimit: 700 },
  test: { environment: 'jsdom', setupFiles: './src/test-setup.js', globals: true },
})
