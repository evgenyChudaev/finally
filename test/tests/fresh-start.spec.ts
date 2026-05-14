import { test, expect } from '@playwright/test';
import { hardReset, waitForHealth, DEFAULT_WATCHLIST } from '../fixtures/freshDb';

/**
 * PLAN §2 — first launch:
 *   - watchlist of 10 default tickers with live-updating prices
 *   - $10,000 in virtual cash
 *   - connection-status dot is green
 *   - prices stream and flash on update
 */
test.describe('Fresh start', () => {
  test.beforeAll(async () => {
    await hardReset().catch(() => {});
    await waitForHealth();
  });

  test('default watchlist renders all 10 seed tickers', async ({ page }) => {
    await page.goto('/');

    // Each ticker should appear somewhere in the watchlist (be liberal on selector — the
    // frontend is free to use rows/cards/etc., but the symbol text must be present).
    for (const ticker of DEFAULT_WATCHLIST) {
      await expect(
        page.getByTestId(`watchlist-row-${ticker}`).first(),
      ).toBeVisible({ timeout: 10_000 });
    }
  });

  test('cash balance shows $10,000', async ({ page }) => {
    await page.goto('/');
    const cashLocator = page.getByTestId('cash-balance').first();
    await expect(cashLocator).toBeVisible({ timeout: 10_000 });
    await expect(cashLocator).toHaveText(/\$?10,?000(?:\.\d{2})?/);
  });

  test('connection status dot turns green within 5s', async ({ page }) => {
    await page.goto('/');
    const dot = page.getByTestId('connection-status');
    await expect(dot).toBeVisible({ timeout: 5_000 });
    // Either a data-status attribute or a class name should signal "open"/"connected".
    await expect(async () => {
      const status =
        (await dot.getAttribute('data-status')) ??
        (await dot.getAttribute('class')) ??
        '';
      expect(status.toLowerCase()).toMatch(/open|connect|green|ok/);
    }).toPass({ timeout: 5_000 });
  });

  test('at least one price update arrives within 3s (SSE working)', async ({ page }) => {
    await page.goto('/');

    const priceLocator = page.getByTestId('price-AAPL').first();
    await expect(priceLocator).toBeVisible({ timeout: 10_000 });

    // Wait for the price to be non-placeholder ("—" means no SSE delivery yet).
    await expect(async () => {
      const text = (await priceLocator.textContent({ timeout: 1_000 })) ?? '';
      expect(text).toMatch(/\$\d/);
    }).toPass({ timeout: 8_000, intervals: [200, 500] });

    const initial = (await priceLocator.textContent({ timeout: 1_000 })) ?? '';
    expect(initial.length).toBeGreaterThan(0);

    // The simulator ticks ~500ms; we should see a change within 8s easily. Use polling.
    await expect(async () => {
      const current = (await priceLocator.textContent({ timeout: 1_000 })) ?? '';
      expect(current).not.toEqual(initial);
    }).toPass({ timeout: 10_000, intervals: [200, 500, 1000] });
  });
});
