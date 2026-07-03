'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, AgentPortfolio, TradeHistory } from '@/lib/api';
import { INITIAL_MODAL } from '@/lib/constants';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import { useAuth } from '@/components/AuthProvider';

// ── EMETIQ theme tokens ────────────────────────────────────────
const ACCENT = '#F26A1B';
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#56564F';
const FAINT = '#9A9A92';
const HAIR = '#ECEBE6';
const UP = '#138A50';
const DOWN = '#D23B3B';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

const CARD: React.CSSProperties = {
  background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 18,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

interface Me { id: string; email: string | null; tier: string; }

export default function ProfilePage() {
  return (
    <RequireAuth>
      <ProfileInner />
    </RequireAuth>
  );
}

function ProfileInner() {
  useEffect(() => { document.title = 'Profil — EMETIQ'; }, []);
  const { signOut } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    await signOut();
    router.push('/');
  };

  const [me, setMe] = useState<Me | null>(null);
  const [port, setPort] = useState<AgentPortfolio | null>(null);
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [watchCount, setWatchCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true); setError(null);
      try {
        // /me diambil terpisah agar kegagalan auth (401) tampil jelas sebagai error,
        // bukan spinner tak berujung.
        const meData = await api.getMe();
        if (!alive) return;
        setMe(meData);

        const [portfolio, hist, watch] = await Promise.all([
          api.getPortfolio(),
          api.getTradeHistory('USER'),
          api.getWatchlist(),
        ]);
        if (!alive) return;
        setPort(portfolio.USER);
        setHistory(hist);
        setWatchCount(watch.length);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : 'Gagal memuat data.');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const buys = history.filter(t => t.action === 'BUY').length;
  const sells = history.filter(t => t.action === 'SELL').length;
  const totalReturn = port ? port.total_value - INITIAL_MODAL : 0;
  const totalUp = totalReturn >= 0;

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav />

      <div style={{ maxWidth: 900, margin: '0 auto', padding: '28px 24px 80px' }}>
        <div className="mb-6">
          <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-.02em' }}>Profil</h1>
          <p style={{ marginTop: 4, fontSize: 14.5, color: MUTED }}>Info akun dan ringkasan data untuk verifikasi.</p>
        </div>

        {error && (
          <div style={{ ...CARD, padding: 20, marginBottom: 24, borderColor: '#F3C7C7', background: '#FBE9E9' }}>
            <p style={{ color: DOWN, fontWeight: 700, fontSize: 14 }}>Gagal memuat data ({error})</p>
            <p style={{ color: MUTED, fontSize: 13, marginTop: 6 }}>
              Kalau muncul 401/Unauthorized, sesi backend tidak menerima token. Coba keluar lalu masuk lagi,
              atau pastikan <code>SUPABASE_URL</code> / <code>SUPABASE_JWT_SECRET</code> di server sudah benar.
            </p>
          </div>
        )}

        {/* ACCOUNT */}
        <div style={{ ...CARD, padding: 24, marginBottom: 24 }}>
          <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: ACCENT, marginBottom: 16 }}>Akun</p>
          {loading && !me ? (
            <p style={{ color: FAINT, fontSize: 13, fontFamily: MONO }} className="animate-pulse">Memuat…</p>
          ) : (
            <div style={{ display: 'grid', gap: 14 }}>
              <Row label="Email" value={me?.email ?? '-'} />
              <Row label="Tier" value={<span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em', color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 86%)`, padding: '3px 10px', borderRadius: 999 }}>{me?.tier ?? '-'}</span>} />
              <Row label="User ID" value={<span style={{ fontFamily: MONO, fontSize: 12, color: MUTED, wordBreak: 'break-all' }}>{me?.id ?? '-'}</span>} />
            </div>
          )}
          <div style={{ marginTop: 20, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Link href="/portfolio" style={{ textDecoration: 'none', color: '#fff', background: ACCENT, fontWeight: 700, fontSize: 13.5, padding: '9px 15px', borderRadius: 11 }}>Lihat Portofolio</Link>
            <button type="button" onClick={handleLogout} style={{ color: INK, background: '#fff', border: `1px solid ${HAIR}`, fontWeight: 600, fontSize: 13.5, padding: '9px 15px', borderRadius: 11, cursor: 'pointer' }}>Keluar</button>
          </div>
        </div>

        {/* DATA SUMMARY */}
        <div style={{ ...CARD, padding: 24 }}>
          <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: ACCENT, marginBottom: 16 }}>Ringkasan Data</p>
          {loading ? (
            <p style={{ color: FAINT, fontSize: 13, fontFamily: MONO }} className="animate-pulse">Memuat…</p>
          ) : !port ? (
            <p style={{ color: FAINT, fontSize: 13 }}>Tidak ada data portofolio.</p>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                <Stat label="Total Nilai" value={`Rp ${port.total_value.toLocaleString('id-ID')}`} />
                <Stat label="Kas Tersedia" value={`Rp ${port.modal.toLocaleString('id-ID')}`} color={port.modal < 0 ? DOWN : INK} />
                <Stat label="Invested" value={`Rp ${port.invested.toLocaleString('id-ID')}`} />
                <Stat label="Total Return" value={`${totalUp ? '+' : ''}Rp ${totalReturn.toLocaleString('id-ID')}`} color={totalUp ? UP : DOWN} />
                <Stat label="Posisi Aktif" value={`${port.assets.length}`} />
                <Stat label="Watchlist" value={watchCount != null ? `${watchCount}` : '-'} />
                <Stat label="Total Transaksi" value={`${history.length}`} />
                <Stat label="Beli / Jual" value={`${buys} / ${sells}`} />
                <Stat label="Realized P&L" value={`${port.realized >= 0 ? '+' : ''}Rp ${Math.round(port.realized).toLocaleString('id-ID')}`} color={port.realized >= 0 ? UP : DOWN} />
              </div>

              {port.assets.length > 0 && (
                <div style={{ marginTop: 22 }}>
                  <p style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 10 }}>Kepemilikan</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                    {port.assets.map(a => (
                      <Link key={a.ticker} href={`/stocks/${a.ticker}`} style={{ textDecoration: 'none', fontFamily: MONO, fontSize: 12, fontWeight: 700, color: INK, border: `1px solid ${HAIR}`, background: '#FBFBF9', padding: '6px 11px', borderRadius: 9 }}>
                        {a.ticker} <span style={{ color: FAINT, fontWeight: 500 }}>· {a.shares / 100} lot</span>
                      </Link>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, borderBottom: `1px solid #F2F1EC`, paddingBottom: 12 }}>
      <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.1em', textTransform: 'uppercase', color: FAINT }}>{label}</span>
      <span style={{ fontSize: 14.5, fontWeight: 600, textAlign: 'right' }}>{value}</span>
    </div>
  );
}

function Stat({ label, value, color = INK }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ border: `1px solid ${HAIR}`, borderRadius: 12, padding: 16 }}>
      <p style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 8 }}>{label}</p>
      <p style={{ fontFamily: MONO, fontSize: 16, fontWeight: 600, color }}>{value}</p>
    </div>
  );
}
