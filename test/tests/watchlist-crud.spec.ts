import { test, expect } from '@playwright/test';
import { hardReset, waitForHealth } from '../fixtures/freshDb';

/**
 * PLAN §8 watchlist endpoints:
 *   POST /api/watchlist → 409 TICKER_ALREADY_WATCHED on dup, 400 UNKNOWN_TICKER on bogus
 *   DELETE /api/watchlist/{ticker} → 404 TICKER_NOT_WATCHED if missing
 *
 * UI: AddTickerInput posts to /api/watchlist; hover-remove on a row deletes.
 */
test.describe('Watchlist CRUD', () => {
  test.beforeAll(async () => {
    await hardReset().catch(() => {});
    await waitForHealth();
  });

  // We add a ticker that is in the simulator's known set but NOT in the default seed.
  // PLAN §6 says the simulator has a fixed seed set; PYPL is a reasonable choice that
  // is unlikely to be in DEFAULT_WATCHLIST. If the simulator rejects it, the test will
  // surface that as a bug (UNKNOWN_TICKER) — file against backend/market-data owner.
  const ADD_TICKER = 'PYPL';

  test('add a known ticker → row appears', async ({ page }) => {
    await page.goto('/');

    // Wait for initial watchlist load.
    await expect(page.getByTestId('watchlist-row-AAPL').first()).toBeVisible({ timeout: 10_000 });

    // Type into the add-ticker input and submit.
    const input = page.getByTestId('add-ticker-input').first();
    await input.fill(ADD_TICKER);
    await input.press('Enter');

    await expect(
      page.getByTestId(`watchlist-row-${ADD_TICKER}`).first(),
    ).toBeVisible({ timeout: 10_000 });
  });

  test('remove a ticker → row disappears', async ({ page }) => {
    await page.goto('/');
    const row = page.getByTestId(`watchlist-row-${ADD_TICKER}`);

    // If the previous test ran in the same browser context the row should still be there;
    // otherwise we re-add it (idempotent setup).
    if ((await row.count()) === 0) {
      const input = page.getByTestId('add-ticker-input').first();
      await input.fill(ADD_TICKER);
      await input.press('Enter');
      await expect(row).toBeVisible({ timeout: 10_000 });
    }

    // Hover to reveal the remove button (per PLAN §10 hover shows remove).
    await row.hover();
    const removeBtn = row.getByTestId('remove-ticker').first();
    await removeBtn.click();

    await expect(row).toHaveCount(0, { timeout: 10_000 });
  });

  test('API: adding an unknown ticker returns 400 UNKNOWN_TICKER', async ({ request }) => {
    const res = await request.post('/api/watchlist', { data: { ticker: 'ZZZZZ' } });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(body.code).toBe('UNKNOWN_TICKER');
  });

  test('API: adding a duplicate ticker returns 409 TICKER_ALREADY_WATCHED', async ({ request }) => {
    const res = await request.post('/api/watchlist', { data: { ticker: 'AAPL' } });
    expect(res.status()).toBe(409);
    const body = await res.json();
    expect(body.code).toBe('TICKER_ALREADY_WATCHED');
  });
});
