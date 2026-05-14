'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { addToWatchlist, getWatchlist, removeFromWatchlist } from '@/lib/api';
import { ApiError } from '@/lib/types';
import type { WatchlistEntry } from '@/lib/types';

export interface WatchlistState {
  entries: WatchlistEntry[];
  loading: boolean;
  error: { message: string; code: string } | null;
  add: (ticker: string) => Promise<boolean>;
  remove: (ticker: string) => Promise<boolean>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

export function useWatchlist(): WatchlistState {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await getWatchlist();
      if (!mounted.current) return;
      setEntries(data.tickers);
    } catch (e) {
      if (e instanceof ApiError) {
        setError({ message: e.message, code: e.code });
      } else if (e instanceof Error) {
        setError({ message: e.message, code: 'UNKNOWN' });
      }
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  const add = useCallback(async (ticker: string) => {
    try {
      const entry = await addToWatchlist(ticker.toUpperCase());
      setEntries((prev) =>
        prev.find((e) => e.ticker === entry.ticker) ? prev : [...prev, entry],
      );
      setError(null);
      return true;
    } catch (e) {
      if (e instanceof ApiError) {
        setError({ message: e.message, code: e.code });
      } else if (e instanceof Error) {
        setError({ message: e.message, code: 'UNKNOWN' });
      }
      return false;
    }
  }, []);

  const remove = useCallback(async (ticker: string) => {
    try {
      await removeFromWatchlist(ticker);
      setEntries((prev) => prev.filter((e) => e.ticker !== ticker));
      setError(null);
      return true;
    } catch (e) {
      if (e instanceof ApiError) {
        setError({ message: e.message, code: e.code });
      } else if (e instanceof Error) {
        setError({ message: e.message, code: 'UNKNOWN' });
      }
      return false;
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => {
      mounted.current = false;
    };
  }, [refresh]);

  return { entries, loading, error, add, remove, refresh, clearError };
}
