'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase';

const BG = '#FCFCFB';
const ACCENT = '#F26A1B';

function CallbackInner() {
  const router = useRouter();
  const next = useSearchParams().get('next') || '/overview';
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { document.title = 'Masuk — EMETIQ'; }, []);

  useEffect(() => {
    // supabase-js (detectSessionInUrl) menukar code/hash di URL menjadi sesi otomatis.
    // Kita tinggal menunggu sesi muncul lalu redirect.
    let done = false;
    const go = () => { if (!done) { done = true; router.replace(next); } };

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_e, session) => {
      if (session) go();
    });
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) go();
    });
    // Fallback: bila tak ada sesi dalam 5 detik, anggap gagal.
    const t = setTimeout(() => {
      if (!done) setErr('Gagal menyelesaikan login. Coba lagi.');
    }, 5000);

    return () => { subscription.unsubscribe(); clearTimeout(t); };
  }, [router, next]);

  return (
    <main style={{ minHeight: '100vh', background: BG, color: ACCENT, fontFamily: "'IBM Plex Mono', monospace" }}
          className="flex items-center justify-center text-xs tracking-[0.3em] uppercase">
      {err ? <span style={{ color: '#D23B3B' }}>{err}</span> : <span className="animate-pulse">Menyelesaikan login...</span>}
    </main>
  );
}

export default function AuthCallbackPage() {
  return <Suspense fallback={null}><CallbackInner /></Suspense>;
}
