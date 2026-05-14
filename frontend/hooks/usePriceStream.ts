'use client';

import { useEffect, useRef, useState } from 'react';
import type { PriceEvent } from '@/lib/types';

/**
 * Wire-level shape of one ticker's update inside a multi-ticker SSE event.
 * The backend sends `timestamp` as a Unix float (seconds since epoch) but
 * the rest of the app uses ISO strings — we normalize on receive.
 */
interface RawPriceUpdate {
  ticker?: string;
  price: number;
  previous_price?: number | null;
  timestamp?: number | string;
  direction?: 'up' | 'down' | 'flat';
}

export type ConnectionStatus = 'connecting' | 'open' | 'disconnected';

export interface PriceState {
  ticker: string;
  price: number;
  previousPrice: number | null;
  timestamp: string;
  direction: 'up' | 'down' | 'flat';
  // Wall-clock ms of last update — used to debounce/observe flash CSS.
  receivedAt: number;
}

export interface PriceStreamState {
  prices: Record<string, PriceState>;
  history: Record<string, number[]>; // session sparkline buffers
  sessionBaselines: Record<string, number>;
  connectionStatus: ConnectionStatus;
  lastEventAt: number | null;
}

const MAX_HISTORY = 240; // ~2 minutes at 500ms per tick

/**
 * Subscribes to /api/stream/prices and exposes the latest price for every
 * ticker, plus a per-session baseline (first price seen since page load) used
 * for the watchlist's session change %, and an in-memory rolling history used
 * for sparklines.
 */
export function usePriceStream(): PriceStreamState {
  const [prices, setPrices] = useState<Record<string, PriceState>>({});
  const [history, setHistory] = useState<Record<string, number[]>>({});
  const [sessionBaselines, setSessionBaselines] = useState<Record<string, number>>({});
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('connecting');
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);

  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    let cancelled = false;
    const es = new EventSource('/api/stream/prices');
    sourceRef.current = es;
    setConnectionStatus('connecting');

    es.onopen = () => {
      if (cancelled) return;
      setConnectionStatus('open');
    };

    es.onerror = () => {
      if (cancelled) return;
      // EventSource auto-reconnects; surface as either connecting or disconnected
      // based on readyState.
      if (es.readyState === EventSource.CLOSED) {
        setConnectionStatus('disconnected');
      } else {
        setConnectionStatus('connecting');
      }
    };

    es.onmessage = (ev: MessageEvent<string>) => {
      if (cancelled) return;
      try {
        const parsed = JSON.parse(ev.data) as
          | PriceEvent
          | Record<string, PriceEvent | RawPriceUpdate>;
        if (!parsed || typeof parsed !== 'object') return;

        // The backend sends a dict of all tickers per event:
        //   {"AAPL": {ticker, price, previous_price, timestamp, direction}, ...}
        // We also tolerate the single-ticker shape {ticker, price, ...} for
        // forward compatibility with the PLAN §6 wording.
        const updates: PriceEvent[] = [];
        if (typeof (parsed as PriceEvent).ticker === 'string' &&
            typeof (parsed as PriceEvent).price === 'number') {
          updates.push(parsed as PriceEvent);
        } else {
          for (const [ticker, raw] of Object.entries(parsed)) {
            if (!raw || typeof raw !== 'object') continue;
            const r = raw as RawPriceUpdate;
            if (typeof r.price !== 'number') continue;
            updates.push({
              ticker: r.ticker ?? ticker,
              price: r.price,
              previous_price: r.previous_price ?? null,
              timestamp:
                typeof r.timestamp === 'number'
                  ? new Date(r.timestamp * 1000).toISOString()
                  : (r.timestamp ?? new Date().toISOString()),
              direction: (r.direction ?? 'flat') as PriceEvent['direction'],
            });
          }
        }

        if (updates.length === 0) return;
        const now = Date.now();

        setPrices((prev) => {
          const next = { ...prev };
          for (const u of updates) {
            next[u.ticker] = {
              ticker: u.ticker,
              price: u.price,
              previousPrice: u.previous_price,
              timestamp: u.timestamp,
              direction: u.direction,
              receivedAt: now,
            };
          }
          return next;
        });

        setHistory((prev) => {
          const next = { ...prev };
          for (const u of updates) {
            const cur = next[u.ticker] ?? [];
            const trimmed = cur.length >= MAX_HISTORY ? cur.slice(1) : cur.slice();
            trimmed.push(u.price);
            next[u.ticker] = trimmed;
          }
          return next;
        });

        setSessionBaselines((prev) => {
          let changed = false;
          const next = { ...prev };
          for (const u of updates) {
            if (next[u.ticker] == null) {
              next[u.ticker] = u.price;
              changed = true;
            }
          }
          return changed ? next : prev;
        });

        setLastEventAt(now);
      } catch {
        // ignore malformed payloads
      }
    };

    return () => {
      cancelled = true;
      es.close();
      sourceRef.current = null;
    };
  }, []);

  return { prices, history, sessionBaselines, connectionStatus, lastEventAt };
}
