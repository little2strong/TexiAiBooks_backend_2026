import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', timeout: 45000, fullyParallel: false, workers: 1,
  reporter: [['list']], use: { baseURL: 'http://127.0.0.1:5173', trace: 'off', screenshot: 'off', reducedMotion: 'reduce', ...devices['Desktop Chrome'] },
  webServer: { command: 'npm run preview', url: 'http://127.0.0.1:5173', reuseExistingServer: false, timeout: 60000,
    env: { API_PROXY_TARGET: process.env.PANEL_API_URL || 'http://127.0.0.1:8000' } },
});
