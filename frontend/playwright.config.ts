import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './browser-tests', fullyParallel: false, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5174', browserName: 'chromium', trace: 'retain-on-failure' },
  webServer: { command: 'npm run dev -- --port 5174 --strictPort', url: 'http://127.0.0.1:5174', reuseExistingServer: false },
})
