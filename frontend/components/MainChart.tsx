'use client';

import { useEffect, useRef } from 'react';
import { fmtUsd } from '@/lib/format';
import type { PriceState } from '@/hooks/usePriceStream';
import type { IChartApi, ISeriesApi, LineData, Time } from 'lightweight-charts';

interface MainChartProps {
  ticker: string | null;
  price: PriceState | undefined;
  history: number[];
}

/**
 * Lightweight Charts line chart of the currently selected ticker. Hydrates
 * from the accumulated session history buffer; appends each new SSE tick.
 */
export default function MainChart({ ticker, price, history }: MainChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const startTsRef = useRef<number>(Date.now());

  // Create / destroy the chart on mount.
  useEffect(() => {
    if (!containerRef.current) return;
    let chart: IChartApi | null = null;
    let series: ISeriesApi<'Line'> | null = null;
    let cleanup = () => {};

    (async () => {
      const lib = await import('lightweight-charts');
      if (!containerRef.current) return;
      chart = lib.createChart(containerRef.current, {
        layout: {
          background: { color: 'transparent' },
          textColor: '#8b96a8',
          fontFamily: 'JetBrains Mono, ui-monospace, monospace',
          fontSize: 11,
        },
        grid: {
          vertLines: { color: 'rgba(42,47,58,0.6)' },
          horzLines: { color: 'rgba(42,47,58,0.6)' },
        },
        rightPriceScale: {
          borderColor: '#2a2f3a',
        },
        timeScale: {
          borderColor: '#2a2f3a',
          timeVisible: true,
          secondsVisible: true,
        },
        crosshair: {
          vertLine: { color: '#3a4050', width: 1 },
          horzLine: { color: '#3a4050', width: 1 },
        },
        autoSize: true,
      });
      series = chart.addLineSeries({
        color: '#209dd7',
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: true,
        priceLineColor: '#ecad0a',
      });
      chartRef.current = chart;
      seriesRef.current = series;
      cleanup = () => {
        chart?.remove();
        chartRef.current = null;
        seriesRef.current = null;
      };
    })();

    return () => cleanup();
  }, []);

  // Reset series when ticker changes; hydrate from buffered history.
  useEffect(() => {
    if (!seriesRef.current) return;
    const series = seriesRef.current;
    startTsRef.current = Date.now() - history.length * 500; // synthetic ~500ms steps
    const data: LineData[] = history.map((v, i) => {
      const t = Math.floor((startTsRef.current + i * 500) / 1000) as Time;
      return { time: t, value: v };
    });
    series.setData(data);
    if (chartRef.current) chartRef.current.timeScale().fitContent();
  }, [ticker]); // eslint-disable-line react-hooks/exhaustive-deps

  // Append latest tick.
  useEffect(() => {
    if (!seriesRef.current || !price || !ticker) return;
    if (price.ticker !== ticker) return;
    const t = Math.floor(price.receivedAt / 1000) as Time;
    try {
      seriesRef.current.update({ time: t, value: price.price });
    } catch {
      // sequence violation — rebuild from history snapshot is handled on ticker change
    }
  }, [price, ticker]);

  return (
    <section className="panel flex flex-col h-full">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="panel-title">Price Chart</h2>
          {ticker && (
            <span className="font-mono text-accent-yellow text-sm font-semibold">{ticker}</span>
          )}
        </div>
        {price && (
          <div className="tabular text-base font-semibold">
            {fmtUsd(price.price)}
            <span className="ml-2 text-xs text-muted">{new Date(price.timestamp).toLocaleTimeString()}</span>
          </div>
        )}
      </div>
      <div ref={containerRef} className="flex-1 min-h-0" data-testid="main-chart-container" />
      {!ticker && (
        <div className="absolute inset-0 flex items-center justify-center text-muted text-xs">
          Select a ticker to view chart
        </div>
      )}
    </section>
  );
}
