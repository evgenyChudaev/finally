import { render, screen, waitFor } from '@testing-library/react';
import ChatPanel from '../components/ChatPanel';

jest.mock('../lib/api', () => {
  const actual = jest.requireActual('../lib/api');
  return {
    ...actual,
    getChatHistory: jest.fn(async () => ({
      messages: [
        {
          id: 1,
          role: 'user',
          content: 'buy 3 AAPL',
          actions: null,
          created_at: new Date().toISOString(),
        },
        {
          id: 2,
          role: 'assistant',
          content: 'Bought 3 AAPL for you.',
          actions: {
            trades: [
              {
                id: 99,
                ticker: 'AAPL',
                side: 'buy',
                quantity: 3,
                price: 190.0,
                executed_at: new Date().toISOString(),
              },
            ],
            watchlist_changes: [],
            errors: [],
          },
          created_at: new Date().toISOString(),
        },
        {
          id: 3,
          role: 'assistant',
          content: 'Failed to add ticker.',
          actions: {
            trades: [],
            watchlist_changes: [],
            errors: [
              { action: { ticker: 'NFLX', action: 'add' }, code: 'TICKER_ALREADY_WATCHED', detail: 'Already' },
            ],
          },
          created_at: new Date().toISOString(),
        },
      ],
    })),
    sendChat: jest.fn(),
  };
});

describe('ChatPanel', () => {
  test('rehydrates and renders user / assistant messages and badges', async () => {
    render(<ChatPanel />);
    await waitFor(() => {
      expect(screen.getByText('buy 3 AAPL')).toBeInTheDocument();
    });
    expect(screen.getByText(/Bought 3 AAPL/)).toBeInTheDocument();
    const tradeBadge = screen.getByTestId('chat-trade-badge');
    expect(tradeBadge.textContent).toMatch(/BUY/);
    expect(tradeBadge.textContent).toMatch(/AAPL/);
    const errBadge = screen.getByTestId('chat-error-badge');
    expect(errBadge.textContent).toMatch(/TICKER_ALREADY_WATCHED/);
  });
});
