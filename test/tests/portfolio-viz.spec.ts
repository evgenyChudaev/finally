import { test, expect } from '@playwright/test';
import { hardReset, waitForHealth } from '../fixtures/freshDb';

/**
 * PLAN §2/§10:
 *   - Portfolio heatmap: each rectangle is a position, sized by weight, colored by P&L.
 *   - P&L chart (Lightweight Charts canvas): points from /api/portfolio/history.
 *
 * After a buy we should see at least one heatmap tile for the new position and at least
 * one data point in the P&L chart history.
 */
test.describe('Portfolio visualizations', () => {
  test.beforeAll(async () => {
    await hardReset().catch(() => {});
    await waitForHealth();
  });

  test('after a buy → heatmap tile for the new position; P&L chart has data points', async ({
    page,
    request,
  }) => {
    await page.goto('/');
    await expect(page.getByTestId('watchlist-row-AAPL').first()).toBeVisible({ timeout: 10_000 });

    // Buy 2 TSLA via the API (faster and more reliable than driving the UI here; the
    // trade UI is exercised separately in trade-flow.spec.ts).
    const buyRes = await request.post('/api/portfolio/trade', {
      data: { ticker: 'TSLA', side: 'buy', quantity: 2 },
    });
    expect(buyRes.ok(), `buy failed: ${buyRes.status()} ${await buyRes.text()}`).toBe(true);

    // Heatmap tile for TSLA appears.
    await expect(
      page.getByTestId('heatmap-tile-TSLA').first(),
    ).toBeVisible({ timeout: 15_000 });

    // P&L chart container is rendered.
    const pnlChart = page.getByTestId('pnl-chart').first();
    await expect(pnlChart).toBeVisible({ timeout: 10_000 });

    // P&L chart has data: assert via the history endpoint (canvas pixel inspection is
    // fragile; the contract is that snapshots are recorded on app start and on every trade).
    const history = await request.get('/api/portfolio/history?limit=500').then((r) => r.json());
    expect(history.snapshots.length).toBeGreaterThanOrEqual(2); // app-start anchor + trade
  });

  test('positions table reflects the new position', async ({ page, request }) => {
    await page.goto('/');
    const portfolio = await request.get('/api/portfolio').then((r) => r.json());
    const tsla = portfolio.positions.find((p: any) => p.ticker === 'TSLA');
    expect(tsla).toBeDefined();
    expect(tsla.quantity).toBeCloseTo(2, 5);

    // Positions table row should render with the ticker and quantity.
    const row = page.getByTestId('position-row-TSLA').first();
    await expect(row).toBeVisible({ timeout: 10_000 });
  });
});
