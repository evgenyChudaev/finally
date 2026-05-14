'use client';

import { useEffect, useMemo, useState } from 'react';
import ChatPanel from '@/components/ChatPanel';
import Header from '@/components/Header';
import MainChart from '@/components/MainChart';
import PnLChart from '@/components/PnLChart';
import PortfolioHeatmap from '@/components/PortfolioHeatmap';
import PositionsTable from '@/components/PositionsTable';
import TradeBar from '@/components/TradeBar';
import Watchlist from '@/components/Watchlist';
import { usePortfolio } from '@/hooks/usePortfolio';
import { usePriceStream } from '@/hooks/usePriceStream';
import { useWatchlist } from '@/hooks/useWatchlist';

export default function HomePage() {
  const stream = usePriceStream();
  const portfolio = usePortfolio(5000);
  const wl = useWatchlist();
  const [selected, setSelected] = useState<string | null>(null);
  const [pnlRefreshKey, setPnlRefreshKey] = useState(0);

  // Auto-select first watchlist ticker on first load.
  useEffect(() => {
    if (selected) return;
    if (wl.entries.length === 0) return;
    setSelected(wl.entries[0].ticker);
  }, [wl.entries, selected]);

  // After a trade or chat action, refetch portfolio + P&L history.
  const handleActivity = () => {
    void portfolio.refresh();
    void wl.refresh();
    setPnlRefreshKey((k) => k + 1);
  };

  // Use live cash + total when available, else last polled value.
  const totalValue = useMemo(() => {
    if (!portfolio.portfolio) return null;
    const { cash_balance, positions } = portfolio.portfolio;
    const positionsValue = positions.reduce((acc, p) => {
      const live = stream.prices[p.ticker]?.price ?? p.current_price;
      return acc + live * p.quantity;
    }, 0);
    return cash_balance + positionsValue;
  }, [portfolio.portfolio, stream.prices]);

  return (
    <div className="h-screen flex flex-col">
      <Header
        totalValue={totalValue}
        cashBalance={portfolio.portfolio?.cash_balance ?? null}
        connectionStatus={stream.connectionStatus}
      />

      <main className="flex-1 min-h-0 grid grid-cols-12 grid-rows-12 gap-3 p-3">
        {/* Watchlist - left column */}
        <div className="col-span-3 row-span-12 min-h-0">
          <Watchlist
            entries={wl.entries}
            prices={stream.prices}
            history={stream.history}
            baselines={stream.sessionBaselines}
            selected={selected}
            onSelect={setSelected}
            onRemove={async (t) => {
              const ok = await wl.remove(t);
              if (ok && selected === t) setSelected(null);
              return ok;
            }}
            onAdd={wl.add}
            addError={wl.error}
            clearAddError={wl.clearError}
          />
        </div>

        {/* Main column */}
        <div className="col-span-6 row-span-8 min-h-0 relative">
          <MainChart
            ticker={selected}
            price={selected ? stream.prices[selected] : undefined}
            history={selected ? stream.history[selected] ?? [] : []}
          />
        </div>

        <div className="col-span-6 row-span-4 min-h-0 grid grid-cols-2 gap-3">
          <PortfolioHeatmap positions={portfolio.portfolio?.positions ?? []} />
          <PnLChart totalValue={totalValue} refreshKey={pnlRefreshKey} />
        </div>

        {/* Right column */}
        <div className="col-span-3 row-span-12 min-h-0 flex flex-col gap-3">
          <TradeBar
            defaultTicker={selected}
            onExecuted={() => handleActivity()}
          />
          <div className="flex-1 min-h-0">
            <ChatPanel onActivity={handleActivity} />
          </div>
        </div>

      </main>

      <section className="px-3 pb-3">
        <PositionsTableWrapper
          positions={portfolio.portfolio?.positions ?? []}
          prices={stream.prices}
          onSelect={(t) => setSelected(t)}
        />
      </section>
    </div>
  );
}

function PositionsTableWrapper({
  positions,
  prices,
  onSelect,
}: {
  positions: import('@/lib/types').Position[];
  prices: Record<string, import('@/hooks/usePriceStream').PriceState>;
  onSelect: (ticker: string) => void;
}) {
  return (
    <div className="h-44">
      <PositionsTable positions={positions} livePrices={prices} onSelect={onSelect} />
    </div>
  );
}
