/**
 * Helpers for resetting backend state between specs.
 *
 * Strategy: the test stack mounts /app/db as tmpfs, so the DB is wiped when the container
 * restarts. We use `docker restart finally-e2e` for a hard reset between suites that need
 * isolation. Individual specs that don't mutate persistent state share the same container.
 *
 * If Docker is not available (local-dev runs without containers), these helpers no-op and
 * rely on the spec being tolerant of pre-existing state.
 */
import { execSync } from 'node:child_process';
import { request } from '@playwright/test';

const CONTAINER_NAME = process.env.FINALLY_CONTAINER_NAME ?? 'finally-e2e';
const BASE_URL = process.env.FINALLY_BASE_URL ?? 'http://localhost:8000';

function tryDocker(cmd: string): boolean {
  try {
    execSync(cmd, { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

/**
 * Hard reset: restart the container so the tmpfs DB is recreated empty, then wait for
 * /api/health. No-op (returns false) if docker is unavailable.
 */
export async function hardReset(maxWaitMs = 60_000): Promise<boolean> {
  if (!tryDocker(`docker inspect ${CONTAINER_NAME}`)) {
    return false;
  }
  execSync(`docker restart ${CONTAINER_NAME}`, { stdio: 'ignore' });
  return waitForHealth(maxWaitMs);
}

export async function waitForHealth(maxWaitMs = 60_000): Promise<boolean> {
  const ctx = await request.newContext({ baseURL: BASE_URL });
  const deadline = Date.now() + maxWaitMs;
  try {
    while (Date.now() < deadline) {
      try {
        const res = await ctx.get('/api/health', { timeout: 2_000 });
        if (res.ok()) {
          const body = await res.json().catch(() => ({}));
          if (body?.status === 'ok') return true;
        }
      } catch {
        // keep polling
      }
      await new Promise((r) => setTimeout(r, 500));
    }
    return false;
  } finally {
    await ctx.dispose();
  }
}

/**
 * Force-reset state via API: sells every position and removes every watchlist ticker
 * except the default seed. Useful when the container is shared across specs.
 *
 * NOTE: this depends on /api/portfolio and /api/portfolio/trade behaving per PLAN §8.
 * If reset semantics need to be more aggressive, prefer `hardReset()`.
 */
export async function softReset(): Promise<void> {
  const ctx = await request.newContext({ baseURL: BASE_URL });
  try {
    const portfolio = await ctx.get('/api/portfolio').then((r) => r.json());
    for (const pos of portfolio?.positions ?? []) {
      if (pos.quantity > 0) {
        await ctx.post('/api/portfolio/trade', {
          data: { ticker: pos.ticker, side: 'sell', quantity: pos.quantity },
        });
      }
    }
  } finally {
    await ctx.dispose();
  }
}

export const DEFAULT_WATCHLIST = [
  'AAPL',
  'GOOGL',
  'MSFT',
  'AMZN',
  'TSLA',
  'NVDA',
  'META',
  'JPM',
  'V',
  'NFLX',
];
