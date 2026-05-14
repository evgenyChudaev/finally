import { render, screen } from '@testing-library/react';
import WatchlistRow from '../components/WatchlistRow';

function makePrice(direction: 'up' | 'down' | 'flat', overrides: Partial<{ price: number }> = {}) {
  return {
    ticker: 'AAPL',
    price: overrides.price ?? 190.5,
    previousPrice: 190.0,
    timestamp: new Date().toISOString(),
    direction,
    receivedAt: Date.now(),
  };
}

describe('WatchlistRow flash behavior', () => {
  test('renders a price', () => {
    render(
      <WatchlistRow
        ticker="AAPL"
        price={makePrice('up')}
        sparkValues={[1, 2, 3]}
        baseline={189}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />,
    );
    const cell = screen.getByTestId('price-AAPL');
    expect(cell.textContent).toMatch(/\$190\.50/);
  });

  test('applies flash-up class when direction is up', () => {
    render(
      <WatchlistRow
        ticker="AAPL"
        price={makePrice('up')}
        sparkValues={[]}
        baseline={189}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />,
    );
    const cell = screen.getByTestId('price-AAPL');
    expect(cell.className).toContain('flash-up');
  });

  test('applies flash-down class when direction is down', () => {
    render(
      <WatchlistRow
        ticker="AAPL"
        price={makePrice('down')}
        sparkValues={[]}
        baseline={189}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />,
    );
    const cell = screen.getByTestId('price-AAPL');
    expect(cell.className).toContain('flash-down');
  });

  test('no flash class when direction is flat', () => {
    render(
      <WatchlistRow
        ticker="AAPL"
        price={makePrice('flat')}
        sparkValues={[]}
        baseline={189}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />,
    );
    const cell = screen.getByTestId('price-AAPL');
    expect(cell.className).not.toMatch(/flash-(up|down)/);
  });

  test('shows session % using baseline', () => {
    const { container } = render(
      <WatchlistRow
        ticker="AAPL"
        price={makePrice('up', { price: 200 })}
        sparkValues={[]}
        baseline={100}
        selected={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />,
    );
    // 100 -> 200 = +100% (formatted in en-US locale)
    expect(container.textContent).toMatch(/\+?100\.00%/);
  });
});
