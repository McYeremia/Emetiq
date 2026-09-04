'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { Session, Subscription, User } from '@supabase/supabase-js';
import { adaSesiTersimpan, getSupabase, supabaseConfigured } from '@/lib/supabase';
import { setAccessToken } from '@/lib/authToken';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

interface AuthState {
  user: User | null;
  tier: string | null;
  loading: boolean;
  configured: boolean;
  signOut: () => Promise<void>;
  /** Dipanggil halaman login/callback setelah sesi baru dibuat — lihat catatan di
   *  `pasangKlien` tentang kenapa ini perlu ada. */
  mulaiSesi: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  user: null,
  tier: null,
  loading: true,
  configured: false,
  signOut: async () => {},
  mulaiSesi: async () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [tier, setTier] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const langgananRef = useRef<Subscription | null>(null);
  const terpasangRef = useRef(false);

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

  /**
   * Unduh pustaka Supabase, baca sesinya, lalu berlangganan perubahannya.
   *
   * Idempoten: pemanggilan kedua tak melakukan apa-apa, karena sejak panggilan
   * pertama `onAuthStateChange` sudah menangani segalanya.
   */
  const pasangKlien = useCallback(async () => {
    if (terpasangRef.current) return;
    terpasangRef.current = true;
    try {
      const sb = await getSupabase();
      const { data } = await sb.auth.getSession();
      await applySession(data.session);
      langgananRef.current = sb.auth.onAuthStateChange((_event, session) => {
        void applySession(session);
      }).data.subscription;
    } catch {
      // Gagal mengunduh chunk (jaringan putus di tengah jalan) tak boleh membuat
      // provider ini terkunci selamanya — biarkan percobaan berikutnya jalan.
      terpasangRef.current = false;
    }
  }, [applySession]);

  useEffect(() => {
    if (!supabaseConfigured) {
      setLoading(false);
      return;
    }

    // Pengunjung anonim berhenti di sini: tak ada sesi tersimpan, jadi pustaka
    // 225,9 KB itu tak pernah diunduh sama sekali. Ini yang membedakan "impor
    // malas" dari "impor yang cuma ditunda" — AuthProvider ada di root layout,
    // jadi tanpa penjaga ini setiap halaman tetap menariknya begitu hidrasi
    // selesai.
    if (!adaSesiTersimpan()) {
      setLoading(false);
      return;
    }

    pasangKlien().finally(() => setLoading(false));

    return () => {
      langgananRef.current?.unsubscribe();
      langgananRef.current = null;
      // Direset supaya efek yang dijalankan ulang (StrictMode di dev, atau
      // provider yang benar-benar di-mount ulang) memasang langganan baru.
      terpasangRef.current = false;
    };
  }, [pasangKlien]);

  /**
   * Halaman login memakai `router.replace()` — navigasi sisi klien, jadi root
   * layout (dan provider ini) TIDAK di-mount ulang. Sebelumnya itu tak masalah:
   * klien Supabase selalu ada, jadi `onAuthStateChange` menangkap sesi barunya.
   *
   * Sekarang pengunjung anonim sengaja tak punya klien maupun langganan, jadi
   * sesi baru itu tak akan terlihat oleh siapa pun. `mulaiSesi()` adalah pintunya:
   * halaman login dan callback memanggilnya setelah berhasil, sebelum redirect.
   */
  const mulaiSesi = useCallback(async () => {
    setLoading(true);
    await pasangKlien();
    setLoading(false);
  }, [pasangKlien]);

  const signOut = useCallback(async () => {
    const sb = await getSupabase();
    await sb.auth.signOut();
    setAccessToken(null);
    setUser(null);
    setTier(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{ user, tier, loading, configured: supabaseConfigured, signOut, mulaiSesi }}
    >
      {children}
    </AuthContext.Provider>
  );
}
