import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const root = dirname(fileURLToPath(import.meta.url))
const backendDir = resolve(root, '../backend')
// Isolated DB for E2E so it never touches the dev app.db. The spec reads OTP
// codes straight out of this file (no prod backdoor for "what's the code").
export const E2E_DB = resolve(backendDir, 'e2e.db')

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 30_000,
  expect: { timeout: 7_000 },
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      // Backend on an isolated DB. `make install` provisions the venv.
      command: '.venv/bin/uvicorn app.main:app --port 8000',
      cwd: backendDir,
      env: { HONEYBOOK_DB_URL: `sqlite:///${E2E_DB}` },
      url: 'http://localhost:8000/healthz',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      cwd: root,
      url: 'http://localhost:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
