import { test, expect } from '@playwright/test';
import { hardReset, waitForHealth } from '../fixtures/freshDb';

/**
 * PLAN §9 LLM_MOCK=true keyword table:
 *   "buy N TICKER"  → trade {side:buy, ticker, quantity:N}
 *   "sell N TICKER" → trade {side:sell, ticker, quantity:N}
 *   "add TICKER"    → watchlist_changes [{ticker, action:add}]
 *   "remove TICKER" → watchlist_changes [{ticker, action:remove}]
 *   anything else   → "Mock LLM response. Try 'buy 5 AAPL' or ask for analysis."
 *
 * The mock goes through the same execution path as real LLM responses, so we should see
 * trades auto-execute and watchlist changes apply (or be captured in errors[] on failure).
 */
test.describe('Chat (LLM mock mode)', () => {
  test.beforeAll(async () => {
    await hardReset().catch(() => {});
    await waitForHealth();
  });

  async function sendChat(page: import('@playwright/test').Page, message: string) {
    const input = page.getByTestId('chat-input').first();
    await input.fill(message);

    // Send via Enter or button — try both forgivingly.
    const sendBtn = page.getByRole('button', { name: /send|submit/i }).last();
    if ((await sendBtn.count()) > 0) {
      await sendBtn.click();
    } else {
      await input.press('Enter');
    }
  }

  test('"buy 3 MSFT" → assistant reply, trade badge inline, MSFT position appears', async ({ page, request }) => {
    await page.goto('/');
    await expect(page.getByTestId('watchlist-row-MSFT').first()).toBeVisible({ timeout: 10_000 });

    await sendChat(page, 'buy 3 MSFT');

    // Assistant reply text matches the mock template (case-insensitive contains).
    await expect(page.getByText(/buying 3 MSFT/i).first()).toBeVisible({ timeout: 15_000 });

    // Trade badge / chip should appear inline below the assistant message.
    await expect(
      page.getByTestId('chat-trade-badge').first(),
    ).toBeVisible({ timeout: 10_000 });

    // Verify backend state via API.
    const portfolio = await request.get('/api/portfolio').then((r) => r.json());
    const msft = portfolio.positions.find((p: any) => p.ticker === 'MSFT');
    expect(msft, 'MSFT position should exist after mock chat-driven buy').toBeDefined();
    expect(msft.quantity).toBeCloseTo(3, 5);
  });

  test('"add NFLX" → NFLX already watched, error badge appears', async ({ page, request }) => {
    await page.goto('/');
    await sendChat(page, 'add NFLX');

    // The mock returns a watchlist_change to add NFLX; the executor will fail because NFLX
    // is already in the default seed → response.errors contains TICKER_ALREADY_WATCHED.
    await expect(
      page.getByTestId('chat-error-badge').first(),
    ).toBeVisible({ timeout: 15_000 });

    // Backend response confirms.
    const res = await request.post('/api/chat', { data: { message: 'add NFLX' } });
    const body = await res.json();
    expect(body.errors?.length ?? 0).toBeGreaterThan(0);
    expect(body.errors.some((e: any) => e.code === 'TICKER_ALREADY_WATCHED')).toBe(true);
  });

  test('"remove NFLX" → NFLX disappears from watchlist (confirmation)', async ({ page, request }) => {
    await page.goto('/');
    await expect(page.getByTestId('watchlist-row-NFLX').first()).toBeVisible({ timeout: 10_000 });

    await sendChat(page, 'remove NFLX');

    // Assistant message should appear; the watchlist row should disappear.
    await expect(
      page.getByTestId('watchlist-row-NFLX'),
    ).toHaveCount(0, { timeout: 15_000 });

    // Backend confirms.
    const watchlist = await request.get('/api/watchlist').then((r) => r.json());
    expect(watchlist.tickers.find((t: any) => t.ticker === 'NFLX')).toBeUndefined();
  });

  test('chat history rehydrates on page reload', async ({ page }) => {
    await page.goto('/');
    await sendChat(page, 'buy 1 GOOGL');
    await expect(page.getByText(/buying 1 GOOGL/i).first()).toBeVisible({ timeout: 15_000 });

    // Reload — chat history should rehydrate from /api/chat/history.
    await page.reload();
    await expect(page.getByText(/buying 1 GOOGL/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test('API: fall-through message returns the default mock reply', async ({ request }) => {
    const res = await request.post('/api/chat', { data: { message: 'hello there friend' } });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.message.toLowerCase()).toContain('mock llm response');
    expect(body.trades).toEqual([]);
    expect(body.watchlist_changes).toEqual([]);
  });
});
