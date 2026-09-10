import { defineConfig } from 'vitest/config'
export default defineConfig({ test: { environment: 'jsdom', pool: 'threads', maxWorkers: 1, include: ['src/**/*.test.tsx'], restoreMocks: true } })
