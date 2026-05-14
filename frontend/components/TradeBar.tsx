'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { postTrade } from '@/lib/api';
import { ApiError } from '@/lib/types';
import type { Trade } from '@/lib/types';

interface TradeBarProps {
  defaultTicker?: string | null;
  onExecuted?: (trade: Trade) => void;
}

export default function TradeBar({ defaultTicker, onExecuted }: TradeBarProps) {
  const [ticker, setTicker] = useState(defaultTicker?.toUpperCase() ?? '');
  const [quantity, setQuantity] = useState('1');
  const [pending, setPending] = useState<null | 'buy' | 'sell'>(null);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const [last, setLast] = useState<Trade | null>(null);
  // Track whether the user has manually edited the ticker; if not, keep it
  // synced to the parent's selection.
  const userEditedRef = useRef(false);

  useEffect(() => {
    if (userEditedRef.current) return;
    if (defaultTicker) setTicker(defaultTicker.toUpperCase());
  }, [defaultTicker]);

  async function execute(side: 'buy' | 'sell', e: FormEvent) {
    e.preventDefault();
    setError(null);
    const t = ticker.trim().toUpperCase();
    const qty = parseFloat(quantity);
    if (!t) {
      setError({ message: 'Enter a ticker.', code: 'VALIDATION_ERROR' });
      return;
    }
    if (!Number.isFinite(qty) || qty <= 0) {
      setError({ message: 'Quantity must be greater than zero.', code: 'INVALID_QUANTITY' });
      return;
    }
    setPending(side);
    try {
      const trade = await postTrade({ ticker: t, side, quantity: qty });
      setLast(trade);
      onExecuted?.(trade);
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ message: err.message, code: err.code });
      } else if (err instanceof Error) {
        setError({ message: err.message, code: 'UNKNOWN' });
      }
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="panel px-3 py-2 flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <span className="panel-title">Trade</span>
        {last && (
          <span className="text-[10px] text-muted">
            Last: {last.side.toUpperCase()} {last.quantity} {last.ticker} @ ${last.price.toFixed(2)}
          </span>
        )}
      </div>
      <form className="flex flex-wrap items-center gap-2">
        <input
          aria-label="Ticker"
          data-testid="trade-ticker"
          value={ticker}
          onChange={(e) => {
            userEditedRef.current = true;
            setTicker(e.target.value);
            if (error) setError(null);
          }}
          placeholder="TICKER"
          className="w-24 bg-bg-alt border border-bg-border rounded px-2 py-1 text-sm font-mono uppercase placeholder:normal-case placeholder:font-sans placeholder:text-muted focus:outline-none focus:border-accent-blue"
        />
        <input
          aria-label="Quantity"
          data-testid="trade-quantity"
          value={quantity}
          onChange={(e) => {
            setQuantity(e.target.value);
            if (error) setError(null);
          }}
          inputMode="decimal"
          placeholder="Qty"
          className="w-20 bg-bg-alt border border-bg-border rounded px-2 py-1 text-sm tabular focus:outline-none focus:border-accent-blue"
        />
        <button
          type="submit"
          onClick={(e) => execute('buy', e)}
          disabled={!!pending}
          className="px-3 py-1 rounded text-xs font-semibold bg-up/90 hover:bg-up text-bg disabled:opacity-50"
        >
          {pending === 'buy' ? 'Buying…' : 'Buy'}
        </button>
        <button
          type="submit"
          onClick={(e) => execute('sell', e)}
          disabled={!!pending}
          className="px-3 py-1 rounded text-xs font-semibold bg-down/90 hover:bg-down text-bg disabled:opacity-50"
        >
          {pending === 'sell' ? 'Selling…' : 'Sell'}
        </button>
      </form>
      {error && (
        <div role="alert" data-testid="trade-error" className="text-xs text-down">
          <span className="font-mono mr-1 text-[10px] uppercase tracking-wider text-down/80">
            {error.code}
          </span>
          {error.message}
        </div>
      )}
    </section>
  );
}
