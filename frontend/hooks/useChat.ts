'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { getChatHistory, sendChat } from '@/lib/api';
import { ApiError } from '@/lib/types';
import type { ChatMessage, ChatResponse } from '@/lib/types';

export interface ChatState {
  messages: ChatMessage[];
  loading: boolean;
  sending: boolean;
  error: { message: string; code: string } | null;
  send: (text: string) => Promise<ChatResponse | null>;
  refresh: () => Promise<void>;
  clearError: () => void;
}

export function useChat(): ChatState {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<{ message: string; code: string } | null>(null);
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await getChatHistory(50);
      if (!mounted.current) return;
      setMessages(data.messages);
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

  const send = useCallback(async (text: string): Promise<ChatResponse | null> => {
    const trimmed = text.trim();
    if (!trimmed) return null;
    setSending(true);
    setError(null);
    // Optimistic user message
    const optimistic: ChatMessage = {
      id: -Date.now(),
      role: 'user',
      content: trimmed,
      actions: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    try {
      const res = await sendChat(trimmed);
      const assistant: ChatMessage = {
        id: -(Date.now() + 1),
        role: 'assistant',
        content: res.message,
        actions: {
          trades: res.trades,
          watchlist_changes: res.watchlist_changes,
          errors: res.errors,
        },
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistant]);
      return res;
    } catch (e) {
      const code = e instanceof ApiError ? e.code : 'UNKNOWN';
      const message = e instanceof Error ? e.message : 'Failed to send';
      setError({ message, code });
      return null;
    } finally {
      setSending(false);
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

  return { messages, loading, sending, error, send, refresh, clearError };
}
