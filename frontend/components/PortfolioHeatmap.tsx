'use client';

import { fmtPct, fmtUsdCompact } from '@/lib/format';
import type { Position } from '@/lib/types';

interface PortfolioHeatmapProps {
  positions: Position[];
}

interface Tile {
  ticker: string;
  weight: number; // 0..1
  pl: number;
  pctChange: number;
  marketValue: number;
}

// Simple squarified-ish layout via flex rows — good enough for ~20 positions.
function makeRows(tiles: Tile[]): Tile[][] {
  if (!tiles.length) return [];
  const sorted = [...tiles].sort((a, b) => b.weight - a.weight);
  // Two-column layout for top 2, then progressively more columns.
  const rows: Tile[][] = [];
  let i = 0;
  let cols = 2;
  while (i < sorted.length) {
    rows.push(sorted.slice(i, i + cols));
    i += cols;
    cols = Math.min(cols + 1, 4);
  }
  return rows;
}

function plToBackground(pl: number): string {
  if (pl === 0) return 'bg-bg-panelAlt';
  const intensity = Math.min(1, Math.abs(pl) / 1000); // scaled
  if (pl > 0) {
    const a = 0.20 + 0.50 * intensity;
    return `rgba(34, 197, 94, ${a.toFixed(2)})`;
  }
  const a = 0.20 + 0.50 * intensity;
  return `rgba(239, 68, 68, ${a.toFixed(2)})`;
}

export default function PortfolioHeatmap({ positions }: PortfolioHeatmapProps) {
  const totalMv = positions.reduce(
    (acc, p) => acc + p.current_price * p.quantity,
    0,
  );
  const tiles: Tile[] = positions.map((p) => {
    const mv = p.current_price * p.quantity;
    return {
      ticker: p.ticker,
      weight: totalMv > 0 ? mv / totalMv : 0,
      pl: p.unrealized_pl,
      pctChange: p.pct_change,
      marketValue: mv,
    };
  });
  const rows = makeRows(tiles);

  return (
    <section className="panel flex flex-col h-full">
      <div className="px-4 pt-3 pb-1 flex items-center justify-between">
        <h2 className="panel-title">Portfolio Heatmap</h2>
        <span className="text-[10px] text-muted">{positions.length} positions</span>
      </div>
      <div className="flex-1 min-h-0 p-2 flex flex-col gap-1.5">
        {rows.length === 0 && (
          <div className="flex-1 flex items-center justify-center text-xs text-muted">
            No positions yet — try buying something.
          </div>
        )}
        {rows.map((row, ri) => {
          const rowWeight = row.reduce((acc, t) => acc + t.weight, 0) || 1;
          return (
            <div key={ri} className="flex gap-1.5 flex-1 min-h-[44px]">
              {row.map((t) => {
                const flex = Math.max(0.3, t.weight / rowWeight) * 10;
                return (
                  <div
                    key={t.ticker}
                    style={{
                      flex,
                      background: plToBackground(t.pl),
                    }}
                    className="rounded border border-bg-border/70 px-2 py-1 flex flex-col justify-between min-w-[60px] overflow-hidden"
                    title={`${t.ticker}: ${fmtUsdCompact(t.marketValue)} (${fmtPct(t.pctChange / 100)})`}
                    data-testid={`heatmap-tile-${t.ticker}`}
                  >
                    <div className="flex items-baseline justify-between gap-1">
                      <span className="font-mono text-xs font-semibold">{t.ticker}</span>
                      <span className="tabular text-[10px] text-white/80">
                        {fmtUsdCompact(t.marketValue)}
                      </span>
                    </div>
                    <div className={`tabular text-[11px] font-medium ${t.pl >= 0 ? 'text-white' : 'text-white'}`}>
                      {fmtPct((t.pctChange ?? 0) / 100)}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </section>
  );
}
