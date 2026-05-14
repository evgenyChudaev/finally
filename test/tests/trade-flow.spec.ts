import { test, expect } from '@playwright/test';
import { hardReset, waitForHealth } from '../fixtures/freshDb';

/**
 * PLAN §2 trading flow:
 *   - Buy 5 AAPL → cash decreases, position with qty 5 appears.
 *   - Sell 5 AAPL → position disappears, cash returns close to original (within tick drift).
 *
 * PLAN §8 trade endpoint contract:
 *   POST /api/portfolio/trade { ticker, side, quantity }
 *     400 INSUFFICIENT_CASH, 400 INSUFFICIENT_SHARES, 400 UNKNOWN_TICKER, 400 INVALID_QUANTITY
 */
test.describe('Trade flow', () => {
  test.beforeAll(async () => {
    await hardReset().catch(() => {});
    await waitForHealth();
  });

  test('buy 5 AAPL via UI → cash decreases, position appears with qty 5', async ({ page, request }) => {
    await page.goto('/');
    await expect(page.getByTestId('watchlist-row-AAPL').first()).toBeVisible({ timeout: 10_000 });

    // Snapshot starting cash via API to avoid race with display formatting.
    const before = await request.get('/api/portfolio').then((r) => r.json());
    const cashBefore: number = before.cash_balance;
    expect(cashBefore).toBeGreaterThan(0);

    // Submit a buy via the trade bar UI.
    const tickerInput = page.getByTestId('trade-ticker').first();
    const qtyInput = page.getByTestId('trade-quantity').first();
    const buyBtn = page.getByRole('button', { name: /^buy/i }).first();

    await tickerInput.fill('AAPL');
    await qtyInput.fill('5');
    await buyBtn.click();

    // Assert position appears in positions table (qty 5).
    const positionRow = page.getByTestId('position-row-AAPL').first();
    await expect(positionRow).toBeVisible({ timeout: 10_000 });

    // Assert cash decreased.
    const after = await request.get('/api/portfolio').then((r) => r.json());
    expect(after.cash_balance).toBeLessThan(cashBefore);
    const aaplPos = after.positions.find((p: any) => p.ticker === 'AAPL');
    expect(aaplPos).toBeDefined();
    expect(aaplPos.quantity).toBeCloseTo(5, 5);
  });

  test('sell 5 AAPL via UI → position disappears, cash recovers near original', async ({ page, request }) => {
    await page.goto('/');

    const before = await request.get('/api/portfolio').then((r) => r.json());
    const cashBefore: number = before.cash_balance;

    const tickerInput = page.getByTestId('trade-ticker').first();
    const qtyInput = page.getByTestId('trade-quantity').first();
    const sellBtn = page.getByRole('button', { name: /^sell/i }).first();

    await tickerInput.fill('AAPL');
    await qtyInput.fill('5');
    await sellBtn.click();

    // Position row should disappear (full sell deletes the row per PLAN §7 logic).
    await expect(page.getByTestId('position-row-AAPL')).toHaveCount(0, { timeout: 10_000 });

    const after = await request.get('/api/portfolio').then((r) => r.json());
    expect(after.cash_balance).toBeGreaterThan(cashBefore);
    // No AAPL position remains.
    expect(after.positions.find((p: any) => p.ticker === 'AAPL')).toBeUndefined();
  });

  test('API: insufficient cash returns 400 INSUFFICIENT_CASH', async ({ request }) => {
    // 1,000,000 shares at any reasonable simulator price exceeds $10k.
    const res = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'buy', quantity: 1_000_000 },
    });
    expect(res.status()).toBe(400);
    expect((await res.json()).code).toBe('INSUFFICIENT_CASH');
  });

  test('API: insufficient shares returns 400 INSUFFICIENT_SHARES', async ({ request }) => {
    const res = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'sell', quantity: 999 },
    });
    expect(res.status()).toBe(400);
    expect((await res.json()).code).toBe('INSUFFICIENT_SHARES');
  });

  test('API: invalid quantity returns 400 INVALID_QUANTITY', async ({ request }) => {
    const res = await request.post('/api/portfolio/trade', {
      data: { ticker: 'AAPL', side: 'buy', quantity: 0 },
    });
    expect(res.status()).toBe(400);
    expect((await res.json()).code).toBe('INVALID_QUANTITY');
  });

  test('API: unknown ticker returns 400 UNKNOWN_TICKER', async ({ request }) => {
    const res = await request.post('/api/portfolio/trade', {
      data: { ticker: 'ZZZZZ', side: 'buy', quantity: 1 },
    });
    expect(res.status()).toBe(400);
    expect((await res.json()).code).toBe('UNKNOWN_TICKER');
  });
});
