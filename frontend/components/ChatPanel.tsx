'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import { useChat } from '@/hooks/useChat';
import type { ChatActionError, ChatActionWatchlist, Trade } from '@/lib/types';

interface ChatPanelProps {
  /** Notify parent that an assistant turn just landed (to refresh portfolio). */
  onActivity?: () => void;
}

function TradeBadge({ trade }: { trade: Trade }) {
  const tone = trade.side === 'buy' ? 'bg-up/20 text-up' : 'bg-down/20 text-down';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono ${tone}`}
      title={`${trade.side.toUpperCase()} ${trade.quantity} ${trade.ticker} @ $${trade.price.toFixed(2)}`}
      data-testid="chat-trade-badge"
    >
      {trade.side.toUpperCase()} {trade.quantity} {trade.ticker}
    </span>
  );
}

function WatchlistBadge({ change }: { change: ChatActionWatchlist }) {
  const tone =
    change.action === 'add' ? 'bg-accent-blue/20 text-accent-blue' : 'bg-muted/20 text-muted';
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono ${tone}`}
      data-testid="chat-watchlist-badge"
    >
      {change.action === 'add' ? '+' : '−'} {change.ticker}
    </span>
  );
}

function ErrorBadge({ err }: { err: ChatActionError }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-mono bg-down/25 text-down"
      title={err.detail}
      data-testid="chat-error-badge"
    >
      {err.code}
    </span>
  );
}

export default function ChatPanel({ onActivity }: ChatPanelProps) {
  const { messages, loading, sending, error, send } = useChat();
  const [input, setInput] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, sending]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    const res = await send(text);
    if (res) onActivity?.();
  }

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="panel px-3 py-2 text-xs uppercase tracking-wider text-muted hover:text-accent-yellow"
        aria-label="Open chat"
      >
        Open Chat ↗
      </button>
    );
  }

  return (
    <section className="panel flex flex-col h-full min-h-0">
      <div className="px-4 pt-3 pb-2 flex items-center justify-between">
        <h2 className="panel-title">AI Copilot</h2>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          className="text-[10px] uppercase tracking-wider text-muted hover:text-accent-yellow"
          aria-label="Collapse chat"
        >
          Collapse
        </button>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-3"
        data-testid="chat-history"
      >
        {loading && <div className="text-xs text-muted">Loading conversation…</div>}
        {!loading && messages.length === 0 && (
          <div className="text-xs text-muted">
            Ask FinAlly anything. Try <code className="text-accent-yellow">buy 5 AAPL</code> or
            <code className="text-accent-yellow"> analyze my portfolio</code>.
          </div>
        )}
        {messages.map((m) => {
          const isUser = m.role === 'user';
          return (
            <div
              key={m.id}
              data-testid={`chat-msg-${m.role}`}
              className={`max-w-[95%] ${isUser ? 'ml-auto text-right' : ''}`}
            >
              <div
                className={`inline-block rounded-md px-3 py-1.5 text-[12.5px] leading-snug ${
                  isUser
                    ? 'bg-accent-blue/15 text-accent-blue border border-accent-blue/30'
                    : 'bg-bg-panelAlt border border-bg-border text-white/90'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.content}</div>
              </div>
              {!isUser && m.actions && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {(m.actions.trades ?? []).map((t, i) => (
                    <TradeBadge key={`t-${i}`} trade={t} />
                  ))}
                  {(m.actions.watchlist_changes ?? []).map((w, i) => (
                    <WatchlistBadge key={`w-${i}`} change={w} />
                  ))}
                  {(m.actions.errors ?? []).map((er, i) => (
                    <ErrorBadge key={`e-${i}`} err={er} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
        {sending && (
          <div className="text-xs text-muted flex items-center gap-1" data-testid="chat-loading">
            <span className="inline-block w-1.5 h-1.5 bg-muted rounded-full animate-bounce [animation-delay:-0.3s]" />
            <span className="inline-block w-1.5 h-1.5 bg-muted rounded-full animate-bounce [animation-delay:-0.15s]" />
            <span className="inline-block w-1.5 h-1.5 bg-muted rounded-full animate-bounce" />
          </div>
        )}
      </div>
      {error && (
        <div className="px-3 py-1 text-xs text-down border-t border-bg-border" role="alert">
          {error.code}: {error.message}
        </div>
      )}
      <form
        onSubmit={onSubmit}
        className="px-3 py-2 border-t border-bg-border flex items-center gap-2"
      >
        <input
          aria-label="Chat message"
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask FinAlly…"
          className="flex-1 bg-bg-alt border border-bg-border rounded px-2 py-1 text-sm focus:outline-none focus:border-accent-purple"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="px-3 py-1 rounded bg-accent-purple text-white text-xs font-semibold disabled:opacity-50"
        >
          {sending ? '…' : 'Send'}
        </button>
      </form>
    </section>
  );
}
