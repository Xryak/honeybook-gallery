import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// The dev server is same-origin with the API: Vite proxies `/api/*` and
// `/static/*` to the FastAPI backend on :8000, so the frontend only ever
// uses relative URLs (mirrors how nginx proxies them in the Docker build).
// (Test config lives in vitest.config.ts.)
const BACKEND = process.env.VITE_BACKEND_ORIGIN ?? 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/static': { target: BACKEND, changeOrigin: true },
    },
  },
})
