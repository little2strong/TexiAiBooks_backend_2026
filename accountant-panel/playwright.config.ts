import { defineConfig, devices } from '@playwright/test';

// A separate port lets the suite run beside a developer's own Vite server.
const port = process.env.PANEL_TEST_PORT || '5173';
export default defineConfig({
  testDir: './e2e', timeout: 45000, fullyParallel: false, workers: 1,
  reporter: [['list']], use: { baseURL: `http://127.0.0.1:${port}`, trace: 'off', screenshot: 'off', reducedMotion: 'reduce', ...devices['Desktop Chrome'] },
  webServer: { command: `${process.env.PANEL_DIAGNOSTICS ? 'npm run dev' : 'npm run preview'} -- --port ${port}`, url: `http://127.0.0.1:${port}`, reuseExistingServer: false, timeout: 60000,
    env: { API_PROXY_TARGET: process.env.PANEL_API_URL || 'http://127.0.0.1:8000', VITE_UI_DIAGNOSTICS: process.env.PANEL_DIAGNOSTICS ? 'true' : 'false' } },
});
