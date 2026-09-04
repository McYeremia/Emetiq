'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import type { Subscription } from '@supabase/supabase-js';
import { getSupabase } from '@/lib/supabase';
import { useAuth } from '@/components/AuthProvider';

const BG = '#FCFCFB';
const ACCENT = '#F26A1B';

function CallbackInner() {
  const router = useRouter();
  const { mulaiSesi } = useAuth();
  const next = useSearchParams().get('next') || '/overview';
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    // supabase-js (detectSessionInUrl) menukar code/hash di URL menjadi sesi
    // otomatis begitu kliennya dibuat. Kita tinggal menunggu sesi muncul lalu
    // redirect.
    //
    // Di sini kliennya SELALU diunduh, tak peduli hasil `adaSesiTersimpan()`:
    // pada alur verifikasi email, sesinya ada di hash URL dan belum menyentuh
    // localStorage sama sekali — jadi probe di AuthProvider justru menjawab
    // "tak ada sesi" dan itu memang benar sampai detik ini.
    let selesai = false;
    let dibatalkan = false;
    let langganan: Subscription | null = null;

    const lanjut = async () => {
      if (selesai) return;
      selesai = true;
      // Beri tahu AuthProvider sebelum pindah halaman — redirect di bawah adalah
      // navigasi sisi klien, jadi provider itu tak di-mount ulang.
      await mulaiSesi();
      router.replace(next);
    };

    getSupabase()
      .then(async sb => {
        if (dibatalkan) return;
        langganan = sb.auth.onAuthStateChange((_e, session) => {
          if (session) void lanjut();
        }).data.subscription;

        const { data } = await sb.auth.getSession();
        if (data.session) void lanjut();
      })
      .catch(() => {
        if (!dibatalkan) setErr('Gagal memuat modul login. Periksa koneksi.');
      });

    // Fallback: bila tak ada sesi dalam 5 detik, anggap gagal.
    const t = setTimeout(() => {
      if (!selesai) setErr('Gagal menyelesaikan login. Coba lagi.');
    }, 5000);

    return () => {
      dibatalkan = true;
      langganan?.unsubscribe();
      clearTimeout(t);
    };
  }, [router, next, mulaiSesi]);

  return (
    <main style={{ minHeight: '100vh', background: BG, color: ACCENT, fontFamily: "var(--font-plex-mono), monospace" }}
          className="flex items-center justify-center text-xs tracking-[0.3em] uppercase">
      {err ? <span style={{ color: '#D23B3B' }}>{err}</span> : <span className="animate-pulse">Menyelesaikan login...</span>}
    </main>
  );
}

export default function AuthCallbackPage() {
  return <Suspense fallback={null}><CallbackInner /></Suspense>;
}
