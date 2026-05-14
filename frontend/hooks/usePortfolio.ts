'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { getPortfolio } from '@/lib/api';
import type { Portfolio } from '@/lib/types';

export interface PortfolioState {
  portfolio: Portfolio | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

/**
 * Polls /api/portfolio every `intervalMs` ms and exposes a manual refresh()
 * (e.g., to call right after a successful trade).
 */
export function usePortfolio(intervalMs = 5000): PortfolioState {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await getPortfolio();
      if (!mounted.current) return;
      setPortfolio(data);
      setError(null);
    } catch (e) {
      if (!mounted.current) return;
      setError(e instanceof Error ? e.message : 'Failed to load portfolio');
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const id = window.setInterval(refresh, intervalMs);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [refresh, intervalMs]);

  return { portfolio, loading, error, refresh };
}
