'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { supabase, supabaseConfigured, siteUrl } from '@/lib/supabase';
import PasswordInput from '@/components/PasswordInput';

const ACCENT = '#F26A1B';
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#56564F';
const HAIR = '#ECEBE6';
const UP = '#138A50';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '11px 14px', borderRadius: 11, border: `1px solid ${HAIR}`,
  background: '#fff', fontSize: 14.5, color: INK, outline: 'none',
};
const btnPrimary: React.CSSProperties = {
  width: '100%', padding: '12px 16px', borderRadius: 12, border: 'none', cursor: 'pointer',
  background: ACCENT, color: '#fff', fontWeight: 700, fontSize: 15,
};
const btnGoogle: React.CSSProperties = {
  width: '100%', padding: '11px 16px', borderRadius: 12, border: `1px solid ${HAIR}`, cursor: 'pointer',
  background: '#fff', color: INK, fontWeight: 600, fontSize: 14.5,
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 9,
};

function RegisterForm() {
  const next = useSearchParams().get('next') || '/overview';
  const [email, setEmail] = useState('');
  const [pw, setPw] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  useEffect(() => { document.title = 'Daftar — EMETIQ'; }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (pw.length < 8) { setErr('Password minimal 8 karakter.'); return; }
    setBusy(true);
    const { data, error } = await supabase.auth.signUp({
      email,
      password: pw,
      options: { emailRedirectTo: `${siteUrl()}/auth/callback?next=${encodeURIComponent(next)}` },
    });
    setBusy(false);
    if (error) { setErr(error.message); return; }
    // Supabase menyembunyikan info "email sudah terdaftar" (anti-enumeration):
    // mengembalikan user dgn identities kosong dan TIDAK mengirim email verifikasi.
    // Deteksi kasus ini agar UI tidak salah menyuruh "cek email".
    if (data.user && (data.user.identities?.length ?? 0) === 0) {
      setErr('Email ini sudah terdaftar. Silakan masuk atau reset password.');
      return;
    }
    // Bila email confirmation aktif, session null -> minta verifikasi email.
    if (!data.session) { setDone(true); return; }
    window.location.assign(next);
  };

  const google = async () => {
    setErr(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${siteUrl()}/auth/callback?next=${encodeURIComponent(next)}` },
    });
    if (error) setErr(error.message);
  };

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />

      <div style={{ width: '100%', maxWidth: 400, background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 18, padding: 28, boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)' }}>
        <Link href="/" style={{ textDecoration: 'none', color: INK, fontWeight: 800, fontSize: 19, letterSpacing: '.06em' }}>EMETIQ</Link>

        {done ? (
          <div style={{ marginTop: 18 }}>
            <h1 style={{ fontSize: 20, fontWeight: 800, color: UP }}>Cek email kamu</h1>
            <p style={{ fontSize: 14, color: MUTED, marginTop: 8 }}>
              Kami mengirim link verifikasi ke <b>{email}</b>. Klik link itu untuk mengaktifkan akun, lalu masuk.
            </p>
            <Link href={`/login?next=${encodeURIComponent(next)}`} style={{ display: 'inline-block', marginTop: 16, color: ACCENT, fontWeight: 700, textDecoration: 'none' }}>
              Ke halaman masuk
            </Link>
          </div>
        ) : (
          <>
            <h1 style={{ fontSize: 22, fontWeight: 800, marginTop: 16 }}>Daftar</h1>
            <p style={{ fontSize: 14, color: MUTED, marginTop: 4, marginBottom: 20 }}>Buat akun gratis untuk mulai memantau & menyimpan portofolio.</p>

            {!supabaseConfigured && (
              <div style={{ background: '#FBE9E9', color: '#B23B3B', fontSize: 13, padding: '10px 12px', borderRadius: 10, marginBottom: 16 }}>
                Auth belum dikonfigurasi. Set <code>NEXT_PUBLIC_SUPABASE_URL</code> & <code>NEXT_PUBLIC_SUPABASE_ANON_KEY</code>.
              </div>
            )}

            <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <input style={inputStyle} type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} required />
              <PasswordInput placeholder="Password (min. 8 karakter)" value={pw} onChange={e => setPw(e.target.value)} minLength={8} required />
              {err && <p style={{ color: '#D23B3B', fontSize: 13 }}>{err}</p>}
              <button style={{ ...btnPrimary, opacity: busy ? 0.7 : 1 }} type="submit" disabled={busy}>
                {busy ? 'Memproses...' : 'Daftar'}
              </button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '16px 0' }}>
              <span style={{ flex: 1, height: 1, background: HAIR }} />
              <span style={{ fontSize: 12, color: MUTED }}>atau</span>
              <span style={{ flex: 1, height: 1, background: HAIR }} />
            </div>

            <button style={btnGoogle} onClick={google} type="button">
              <span style={{ fontWeight: 800, color: '#4285F4' }}>G</span> Daftar dengan Google
            </button>

            <p style={{ fontSize: 13.5, color: MUTED, marginTop: 20, textAlign: 'center' }}>
              Sudah punya akun? <Link href={`/login?next=${encodeURIComponent(next)}`} style={{ color: ACCENT, fontWeight: 700, textDecoration: 'none' }}>Masuk</Link>
            </p>
          </>
        )}
      </div>
    </main>
  );
}

export default function RegisterPage() {
  return <Suspense fallback={null}><RegisterForm /></Suspense>;
}
