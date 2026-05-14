import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import TradeBar from '../components/TradeBar';

// Mock the API module so we can simulate an INSUFFICIENT_CASH error.
jest.mock('../lib/api', () => {
  const actual = jest.requireActual('../lib/api');
  return {
    ...actual,
    postTrade: jest.fn(async () => {
      // Throw a typed ApiError
      const { ApiError } = jest.requireActual('../lib/types');
      throw new ApiError('Not enough cash', 'INSUFFICIENT_CASH', 400);
    }),
  };
});

describe('TradeBar', () => {
  test('surfaces INSUFFICIENT_CASH inline', async () => {
    render(<TradeBar defaultTicker="AAPL" />);
    const tickerInput = screen.getByLabelText(/Ticker/);
    const qtyInput = screen.getByLabelText(/Quantity/);
    fireEvent.change(tickerInput, { target: { value: 'AAPL' } });
    fireEvent.change(qtyInput, { target: { value: '5' } });
    const buy = screen.getByRole('button', { name: /Buy/i });
    fireEvent.click(buy);
    const alert = await screen.findByTestId('trade-error');
    expect(alert.textContent).toMatch(/INSUFFICIENT_CASH/);
    expect(alert.textContent).toMatch(/Not enough cash/);
  });

  test('blocks zero-quantity submit with INVALID_QUANTITY', async () => {
    render(<TradeBar defaultTicker="AAPL" />);
    fireEvent.change(screen.getByLabelText(/Ticker/), { target: { value: 'AAPL' } });
    fireEvent.change(screen.getByLabelText(/Quantity/), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: /Buy/i }));
    await waitFor(() => {
      const alert = screen.getByTestId('trade-error');
      expect(alert.textContent).toMatch(/INVALID_QUANTITY/);
    });
  });
});
