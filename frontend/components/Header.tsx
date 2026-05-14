'use client';

import { fmtUsd } from '@/lib/format';
import type { ConnectionStatus } from '@/hooks/usePriceStream';

interface HeaderProps {
  totalValue: number | null;
  cashBalance: number | null;
  connectionStatus: ConnectionStatus;
}

const STATUS_TO_DOT: Record<ConnectionStatus, string> = {
  open: 'bg-up shadow-[0_0_10px_rgba(34,197,94,0.7)]',
  connecting: 'bg-accent-yellow shadow-[0_0_10px_rgba(236,173,10,0.6)]',
  disconnected: 'bg-down shadow-[0_0_10px_rgba(239,68,68,0.6)]',
};

const STATUS_TO_LABEL: Record<ConnectionStatus, string> = {
  open: 'Live',
  connecting: 'Reconnecting…',
  disconnected: 'Disconnected',
};

export default function Header({ totalValue, cashBalance, connectionStatus }: HeaderProps) {
  return (
    <header className="border-b border-bg-border bg-bg/80 backdrop-blur px-5 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="text-accent-yellow font-bold text-base tracking-wide">FinAlly</div>
        <span className="text-muted text-xs uppercase tracking-widest hidden sm:inline">
          AI Trading Workstation
        </span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="panel-title">Cash</div>
          <div className="tabular text-sm font-semibold" data-testid="cash-balance">
            {fmtUsd(cashBalance)}
          </div>
        </div>
        <div className="text-right">
          <div className="panel-title">Portfolio Value</div>
          <div className="tabular text-base font-semibold text-accent-blue">
            {fmtUsd(totalValue)}
          </div>
        </div>
        <div className="flex items-center gap-2 pl-4 border-l border-bg-border">
          <span
            data-testid="connection-status"
            data-status={connectionStatus}
            className={`inline-block w-2.5 h-2.5 rounded-full status-${connectionStatus} ${STATUS_TO_DOT[connectionStatus]}`}
          />
          <span className="text-xs text-muted uppercase tracking-wider">
            {STATUS_TO_LABEL[connectionStatus]}
          </span>
        </div>
      </div>
    </header>
  );
}
