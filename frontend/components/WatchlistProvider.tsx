'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useAuth } from './AuthProvider';
import { useToast } from './Toast';
import { api } from '@/lib/api';

interface WatchlistState {
  watchlist: Set<string>;
  toggle: (e: React.MouseEvent, ticker: string) => void;
}

const WatchlistContext = createContext<WatchlistState>({
  watchlist: new Set(),
  toggle: () => {},
});

export function useWatchlist() {
  return useContext(WatchlistContext);
}

/** Watchlist per user, di-backing API backend. Logout -> kosong. */
export default function WatchlistProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const { toast } = useToast();
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!user) { setWatchlist(new Set()); return; }
    let cancelled = false;
    api.getWatchlist()
      .then(tickers => { if (!cancelled) setWatchlist(new Set(tickers)); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [user]);

  const toggle = useCallback((e: React.MouseEvent, ticker: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!user) {
      toast('Masuk dulu untuk memakai watchlist.', 'error');
      return;
    }
    setWatchlist(prev => {
      const next = new Set(prev);
      if (next.has(ticker)) {
        next.delete(ticker);
        api.removeWatchlist(ticker).catch(() => {});
      } else {
        next.add(ticker);
        api.addWatchlist(ticker).catch(() => {});
      }
      return next;
    });
  }, [user, toast]);

  return (
    <WatchlistContext.Provider value={{ watchlist, toggle }}>
      {children}
    </WatchlistContext.Provider>
  );
}
