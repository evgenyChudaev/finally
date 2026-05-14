'use client';

import { fmtPct, fmtQty, fmtUsd } from '@/lib/format';
import type { Position } from '@/lib/types';
import type { PriceState } from '@/hooks/usePriceStream';

interface PositionsTableProps {
  positions: Position[];
  livePrices: Record<string, PriceState>;
  onSelect?: (ticker: string) => void;
}

export default function PositionsTable({
  positions,
  livePrices,
  onSelect,
}: PositionsTableProps) {
  return (
    <section className="panel flex flex-col h-full min-h-0">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <h2 className="panel-title">Positions</h2>
        <span className="text-[10px] text-muted">{positions.length}</span>
      </div>
      <div className="flex-1 min-h-0 overflow-y-auto">
        <table className="w-full text-xs tabular">
          <thead className="sticky top-0 bg-bg-panel/95 backdrop-blur">
            <tr className="text-left text-[10px] uppercase tracking-wider text-muted">
              <th className="px-3 py-1.5 font-normal">Ticker</th>
              <th className="px-3 py-1.5 font-normal text-right">Qty</th>
              <th className="px-3 py-1.5 font-normal text-right">Avg Cost</th>
              <th className="px-3 py-1.5 font-normal text-right">Price</th>
              <th className="px-3 py-1.5 font-normal text-right">P&amp;L</th>
              <th className="px-3 py-1.5 font-normal text-right">%</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-muted">
                  No positions.
                </td>
              </tr>
            )}
            {positions.map((p) => {
              const live = livePrices[p.ticker];
              const price = live?.price ?? p.current_price;
              const value = price * p.quantity;
              const cost = p.avg_cost * p.quantity;
              const pl = value - cost;
              const pctChange = cost > 0 ? (pl / cost) * 100 : 0;
              const tone = pl >= 0 ? 'text-up' : 'text-down';
              return (
                <tr
                  key={p.ticker}
                  onClick={() => onSelect?.(p.ticker)}
                  className="border-t border-bg-border/60 hover:bg-bg-panelAlt/50 cursor-pointer"
                  data-testid={`position-row-${p.ticker}`}
                >
                  <td className="px-3 py-1.5 font-mono font-semibold text-accent-yellow">
                    {p.ticker}
                  </td>
                  <td className="px-3 py-1.5 text-right">{fmtQty(p.quantity)}</td>
                  <td className="px-3 py-1.5 text-right text-muted">{fmtUsd(p.avg_cost)}</td>
                  <td className="px-3 py-1.5 text-right">{fmtUsd(price)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone}`}>{fmtUsd(pl)}</td>
                  <td className={`px-3 py-1.5 text-right ${tone}`}>
                    {fmtPct(pctChange / 100)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
