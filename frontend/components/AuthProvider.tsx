'use client';

import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase, supabaseConfigured } from '@/lib/supabase';
import { setAccessToken } from '@/lib/authToken';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

interface AuthState {
  user: User | null;
  tier: string | null;
  loading: boolean;
  configured: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  tier: null,
  loading: true,
  configured: false,
  signOut: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const applySession = useCallback(async (session: Session | null) => {
    const token = session?.access_token ?? null;
    setAccessToken(token);
    setUser(session?.user ?? null);

    if (!token) {
      setTier(null);
      return;
    }
    // Ambil tier dari backend (sumber kebenaran tier = tabel profiles).
    try {
      const res = await fetch(`${API_BASE_URL}/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setTier(res.ok ? (await res.json()).tier ?? null : null);
    } catch {
      setTier(null);
    }
  }, []);

  useEffect(() => {
    if (!supabaseConfigured) {
      setLoading(false);
      return;
    }
    supabase.auth
      .getSession()
      .then(({ data }) => applySession(data.session))
      .finally(() => setLoading(false));

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      applySession(session);
    });
    return () => subscription.unsubscribe();
  }, [applySession]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    setAccessToken(null);
    setUser(null);
    setTier(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, tier, loading, configured: supabaseConfigured, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}
