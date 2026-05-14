'use client';

import { useEffect, useRef, useState } from 'react';
import { fmtUsd, fmtPct } from '@/lib/format';
import Sparkline from './Sparkline';
import type { PriceState } from '@/hooks/usePriceStream';

interface WatchlistRowProps {
  ticker: string;
  price: PriceState | undefined;
  sparkValues: number[];
  baseline: number | undefined;
  selected: boolean;
  onSelect: () => void;
  onRemove: () => void;
}

/**
 * One row in the watchlist. Watches the incoming price's `receivedAt` and
 * toggles a `flash-up` / `flash-down` class on the price cell for ~250ms.
 */
export default function WatchlistRow({
  ticker,
  price,
  sparkValues,
  baseline,
  selected,
  onSelect,
  onRemove,
}: WatchlistRowProps) {
  const [flashClass, setFlashClass] = useState('');
  const lastReceivedRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    if (!price) return;
    if (lastReceivedRef.current === price.receivedAt) return;
    lastReceivedRef.current = price.receivedAt;
    if (price.direction === 'up') setFlashClass('flash-up');
    else if (price.direction === 'down') setFlashClass('flash-down');
    else setFlashClass('');
    // Clear the class shortly after the keyframes end so a future tick can
    // re-trigger the same animation. ~260ms matches the 250ms keyframe.
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setFlashClass(''), 260);
    return () => {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [price]);

  const pct =
    price && baseline ? (price.price - baseline) / baseline : null;
  const pctTone =
    pct == null ? 'text-muted' : pct > 0 ? 'text-up' : pct < 0 ? 'text-down' : 'text-muted';

  return (
    <div
      data-testid={`watchlist-row-${ticker}`}
      onClick={onSelect}
      className={`group grid grid-cols-[64px_1fr_72px_92px_28px] items-center gap-2 px-3 py-1.5 cursor-pointer rounded-md border border-transparent transition-colors hover:bg-bg-panelAlt/60 ${
        selected ? 'bg-bg-panelAlt/80 border-bg-border' : ''
      }`}
    >
      <div className="font-mono text-[12px] font-semibold tracking-wide text-accent-yellow">
        {ticker}
      </div>
      <div
        data-testid={`price-${ticker}`}
        className={`tabular text-sm font-semibold rounded px-1 py-0.5 ${flashClass}`}
      >
        {price ? fmtUsd(price.price) : '—'}
      </div>
      <div className={`tabular text-xs ${pctTone}`}>{fmtPct(pct ?? null)}</div>
      <div className="flex justify-end">
        <Sparkline values={sparkValues} width={88} height={22} />
      </div>
      <button
        type="button"
        data-testid="remove-ticker"
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="opacity-0 group-hover:opacity-100 text-muted hover:text-down text-xs transition-opacity"
        aria-label={`Remove ${ticker}`}
        title={`Remove ${ticker}`}
      >
        ✕
      </button>
    </div>
  );
}
