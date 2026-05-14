'use client';

import AddTickerInput from './AddTickerInput';
import WatchlistRow from './WatchlistRow';
import type { WatchlistEntry } from '@/lib/types';
import type { PriceState } from '@/hooks/usePriceStream';

interface WatchlistProps {
  entries: WatchlistEntry[];
  prices: Record<string, PriceState>;
  history: Record<string, number[]>;
  baselines: Record<string, number>;
  selected: string | null;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => Promise<boolean>;
  onAdd: (ticker: string) => Promise<boolean>;
  addError: { message: string; code: string } | null;
  clearAddError: () => void;
}

export default function Watchlist({
  entries,
  prices,
  history,
  baselines,
  selected,
  onSelect,
  onRemove,
  onAdd,
  addError,
  clearAddError,
}: WatchlistProps) {
  return (
    <section className="panel flex flex-col min-h-0 h-full">
      <div className="px-3 pt-3 pb-1 flex items-center justify-between">
        <h2 className="panel-title">Watchlist</h2>
        <span className="text-[10px] text-muted tabular">{entries.length}</span>
      </div>
      <AddTickerInput onAdd={onAdd} error={addError} clearError={clearAddError} />
      <div className="px-3 pb-1 grid grid-cols-[64px_1fr_72px_92px_28px] gap-2 text-[10px] uppercase tracking-wider text-muted">
        <span>Symbol</span>
        <span>Price</span>
        <span>Session</span>
        <span className="text-right">Trend</span>
        <span />
      </div>
      <div className="flex-1 overflow-y-auto pb-2">
        {entries.length === 0 && (
          <div className="px-3 py-6 text-xs text-muted text-center">No tickers watched.</div>
        )}
        {entries.map((e) => (
          <WatchlistRow
            key={e.ticker}
            ticker={e.ticker}
            price={prices[e.ticker]}
            sparkValues={history[e.ticker] ?? []}
            baseline={baselines[e.ticker]}
            selected={selected === e.ticker}
            onSelect={() => onSelect(e.ticker)}
            onRemove={() => {
              void onRemove(e.ticker);
            }}
          />
        ))}
      </div>
    </section>
  );
}
