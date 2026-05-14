'use client';

import { FormEvent, useState } from 'react';

interface AddTickerInputProps {
  onAdd: (ticker: string) => Promise<boolean>;
  error: { message: string; code: string } | null;
  clearError: () => void;
}

export default function AddTickerInput({ onAdd, error, clearError }: AddTickerInputProps) {
  const [value, setValue] = useState('');
  const [pending, setPending] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const v = value.trim().toUpperCase();
    if (!v) return;
    setPending(true);
    const ok = await onAdd(v);
    setPending(false);
    if (ok) setValue('');
  }

  return (
    <form onSubmit={onSubmit} className="px-3 pt-2 pb-2">
      <div className="flex gap-2">
        <input
          aria-label="Add ticker"
          data-testid="add-ticker-input"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (error) clearError();
          }}
          placeholder="Add ticker…"
          className="flex-1 bg-bg-alt border border-bg-border rounded px-2 py-1 text-sm font-mono uppercase placeholder:normal-case placeholder:font-sans placeholder:text-muted focus:outline-none focus:border-accent-blue"
        />
        <button
          type="submit"
          disabled={pending || !value.trim()}
          className="px-3 py-1 rounded bg-accent-blue/90 hover:bg-accent-blue text-bg text-xs font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add
        </button>
      </div>
      {error && (
        <div className="mt-1.5 text-xs text-down" role="alert">
          {error.message}
        </div>
      )}
    </form>
  );
}
