import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for FinAlly E2E tests.
 *
 * The test stack is brought up externally via `docker compose -f docker-compose.test.yml up -d`
 * before invoking the test runner; we do NOT use Playwright's `webServer` here because we want
 * tear-down to be controlled by the CI/orchestration script (and ephemeral DB cleanup is
 * easier with explicit compose down -v).
 *
 * baseURL is overridable via FINALLY_BASE_URL (default http://localhost:8000).
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false, // shared backend DB state — keep serial for determinism
  workers: 1,
  retries: process.env.CI ? 1 : 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  timeout: 30_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: process.env.FINALLY_BASE_URL ?? 'http://localhost:8000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
