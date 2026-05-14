'use client';

import { useEffect, useRef, useState } from 'react';
import { getPortfolioHistory } from '@/lib/api';
import { fmtUsd } from '@/lib/format';
import type { Snapshot } from '@/lib/types';
import type {
  AreaData,
  IChartApi,
  ISeriesApi,
  Time,
} from 'lightweight-charts';

interface PnLChartProps {
  totalValue: number | null;
  /** Bump this value (e.g. via Date.now()) after a trade to refetch history. */
  refreshKey?: number;
}

/**
 * Lightweight Charts area chart of total portfolio value. Hydrates from
 * `/api/portfolio/history` once, then appends a new point each time
 * `totalValue` changes.
 */
export default function PnLChart({ totalValue, refreshKey }: PnLChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Area'> | null>(null);
  const lastTimeRef = useRef<number>(0);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);

  useEffect(() => {
    let cleanup = () => {};
    (async () => {
      if (!containerRef.current) return;
      const lib = await import('lightweight-charts');
      if (!containerRef.current) return;
      const chart = lib.createChart(containerRef.current, {
        layout: {
          background: { color: 'transparent' },
          textColor: '#8b96a8',
          fontFamily: 'JetBrains Mono, ui-monospace, monospace',
          fontSize: 11,
        },
        grid: {
          vertLines: { color: 'rgba(42,47,58,0.5)' },
          horzLines: { color: 'rgba(42,47,58,0.5)' },
        },
        rightPriceScale: { borderColor: '#2a2f3a' },
        timeScale: { borderColor: '#2a2f3a', timeVisible: true },
        autoSize: true,
      });
      const series = chart.addAreaSeries({
        lineColor: '#753991',
        topColor: 'rgba(117,57,145,0.45)',
        bottomColor: 'rgba(117,57,145,0.02)',
        lineWidth: 2,
      });
      chartRef.current = chart;
      seriesRef.current = series;
      cleanup = () => {
        chart.remove();
        chartRef.current = null;
        seriesRef.current = null;
      };
    })();
    return () => cleanup();
  }, []);

  // Initial hydrate + refetch when refreshKey changes.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { snapshots: rows } = await getPortfolioHistory(500);
        if (cancelled) return;
        setSnapshots(rows);
      } catch {
        // backend may not be up — leave empty
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  // Render snapshots whenever they change.
  useEffect(() => {
    if (!seriesRef.current) return;
    if (!snapshots.length) {
      seriesRef.current.setData([]);
      lastTimeRef.current = 0;
      return;
    }
    // Lightweight Charts requires strictly ascending unique times.
    const seen = new Set<number>();
    const data: AreaData[] = [];
    for (const s of snapshots) {
      const ms = new Date(s.recorded_at).getTime();
      if (!Number.isFinite(ms)) continue;
      let t = Math.floor(ms / 1000);
      while (seen.has(t)) t += 1;
      seen.add(t);
      data.push({ time: t as Time, value: s.total_value });
    }
    seriesRef.current.setData(data);
    lastTimeRef.current = data.length ? (data[data.length - 1].time as number) : 0;
    if (chartRef.current) chartRef.current.timeScale().fitContent();
  }, [snapshots]);

  // Append live ticks of totalValue (one per change, throttled by the polling).
  useEffect(() => {
    if (!seriesRef.current || totalValue == null) return;
    const now = Math.floor(Date.now() / 1000);
    let t = now > lastTimeRef.current ? now : lastTimeRef.current + 1;
    lastTimeRef.current = t;
    try {
      seriesRef.current.update({ time: t as Time, value: totalValue });
    } catch {
      // ignore non-monotonic update
    }
  }, [totalValue]);

  return (
    <section className="panel flex flex-col h-full">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <h2 className="panel-title">Portfolio P&amp;L</h2>
        {totalValue != null && (
          <div className="tabular text-sm font-semibold text-accent-blue">{fmtUsd(totalValue)}</div>
        )}
      </div>
      <div
        ref={containerRef}
        className="flex-1 min-h-0"
        data-testid="pnl-chart"
        data-chart="pnl"
      />
    </section>
  );
}
