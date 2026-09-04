'use client';

import { useEffect, useState } from 'react';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import TanggalData from '@/components/TanggalData';
import { useAuth } from '@/components/AuthProvider';
import { api, AiPortoSnapshot, TradeHistory } from '@/lib/api';

// ── EMETIQ theme tokens ────────────────────────────────────────
const ACCENT = '#F26A1B';
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#56564F';
const FAINT = '#9A9A92';
const HAIR = '#ECEBE6';
const UP = '#138A50';
const DOWN = '#D23B3B';
const SANS = "var(--font-jakarta), system-ui, sans-serif";
const MONO = "var(--font-plex-mono), monospace";

const CARD: React.CSSProperties = {
  background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 16,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

/** Modal dummy tiap bucket. Sumber kebenarannya `INITIAL_MODAL` di
 *  `backend/services/trade_exec.py`; snapshot tak mengirimkannya, jadi angkanya
 *  ditulis ulang di sini persis seperti di halaman AI Porto tier dev. */
const MODAL_AWAL = 15_000_000;

/** Berapa transaksi terbaru yang ditampilkan sebelum daftarnya dibentangkan.
 *  Cukup untuk menjawab "AI barusan ngapain?" tanpa membuat halaman jadi gulungan
 *  panjang; sisanya di balik satu ketukan. */
const HISTORI_AWAL = 5;

/** Tier terendah yang boleh memantau. Backend tetap yang menolak (403) — nilai di
 *  sini hanya menentukan layar mana yang ditampilkan, bukan pengamanannya. */
const TIER_BOLEH = ['pro', 'premium', 'dev'];

const rp = (n: number | null | undefined) =>
  n == null ? '—' : 'Rp ' + Math.round(n).toLocaleString('id-ID');

/**
 * Pantauan portofolio AI untuk tier `pro` ke atas — melihat, tanpa memerintah.
 *
 * Tampilannya SALINAN dari `app/ai-porto/AiPortoClient.tsx`, bukan komponen bersama,
 * dan itu disengaja: halaman itu permukaan yang mengeksekusi trade sungguhan, dan
 * syarat saat fitur ini dibuat adalah tak menyentuhnya sama sekali. Harganya nyata —
 * mengubah tampilan di satu tempat tak mengubah yang lain. Kalau suatu saat keduanya
 * perlu berubah bersama, barulah pantas dipikirkan menyatukan komponennya.
 *
 * Bedanya dengan halaman tier dev, selain hilangnya kotak perintah:
 *
 * - **Histori memuat alasan AI.** Tiap transaksi menyimpan alasannya di kolom
 *   `notes`, dan justru itu isi yang paling berguna untuk sebuah pantauan.
 * - **Tak ada badge rezim risiko.** Nilai itu datang dari balasan endpoint chat,
 *   bukan dari data tersimpan — menampilkannya berarti menjalankan pipeline AI.
 * - **Dimuat sekali saja**, tanpa polling: porto AI hanya berubah ketika pemiliknya
 *   menjalankan AI-nya. Polling berkala oleh tiap penonton berarti kueri berulang ke
 *   basis data untuk angka yang sama.
 */
export default function AiPortoMonitorPage() {
  return (
    <RequireAuth>
      <GerbangTier />
    </RequireAuth>
  );
}

function GerbangTier() {
  const { tier, loading } = useAuth();
  if (loading) return null;
  if (!TIER_BOLEH.includes((tier || '').toLowerCase())) return <BelumBerhak tier={tier} />;
  return <Pantauan />;
}

function BelumBerhak({ tier }: { tier: string | null }) {
  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS }}>
      <EmetiqNav active="ai-porto" />
      <div style={{ maxWidth: 520, margin: '0 auto', padding: '80px 20px', textAlign: 'center' }}>
        <div style={{ ...CARD, padding: 32 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Untuk tier Pro ke atas</h1>
          <p style={{ marginTop: 10, fontSize: 14.5, color: MUTED, lineHeight: 1.6 }}>
            <strong>AI Porto</strong> memperlihatkan portofolio yang dikelola AI — apa yang
            dibeli, kapan dijual, dan alasannya. Akun Anda saat ini bertier{' '}
            <code>{tier || 'free'}</code>.
          </p>
        </div>
      </div>
    </main>
  );
}

function Pantauan() {
  const [snapshot, setSnapshot] = useState<AiPortoSnapshot | null>(null);
  const [histori, setHistori] = useState<TradeHistory[]>([]);
  const [memuat, setMemuat] = useState(true);
  const [galat, setGalat] = useState<string | null>(null);
  const [bentangkan, setBentangkan] = useState(false);

  // Sekali jalan, tanpa polling — lihat catatan di kepala berkas.
  useEffect(() => {
    let dibatalkan = false;
    Promise.all([api.getAiPortoMonitor(), api.getTradeHistory('AI')])
      .then(([snap, riwayat]) => {
        if (dibatalkan) return;
        setSnapshot(snap);
        setHistori(riwayat);
      })
      .catch(() => { if (!dibatalkan) setGalat('Gagal memuat porto AI. Periksa koneksi.'); })
      .finally(() => { if (!dibatalkan) setMemuat(false); });
    return () => { dibatalkan = true; };
  }, []);

  const pnl = snapshot ? snapshot.total_value - MODAL_AWAL : 0;
  const pnlPct = snapshot ? (pnl / MODAL_AWAL) * 100 : 0;
  const naik = pnl >= 0;
  // `GET /trades/history` memulangkan TERBARU DI DEPAN (endpoint-nya mengurut
  // menurun). Jadi transaksi terakhir ada di indeks 0 — bukan di ujung. Versi
  // pertama halaman ini mengambil ujungnya dan menampilkan tanggal transaksi
  // PALING LAMA sebagai "transaksi terakhir".
  const tanggalTerakhir = histori[0]?.date;
  const historiTampil = bentangkan ? histori : histori.slice(0, HISTORI_AWAL);
  const adaSisa = histori.length > HISTORI_AWAL;

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      <EmetiqNav active="ai-porto" />

      <div style={{ maxWidth: 880, margin: '0 auto', padding: '24px 18px 60px' }}>
        <div className="flex items-baseline gap-3 flex-wrap" style={{ marginBottom: 4 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>AI Porto</h1>
          <TanggalData tanggal={tanggalTerakhir} awalan="Transaksi terakhir" />
        </div>
        <p style={{ fontSize: 13.5, color: MUTED, marginBottom: 22, lineHeight: 1.6 }}>
          Portofolio yang dikelola AI — apa yang dibeli, kapan dijual, dan alasannya.
          Halaman ini <strong>memantau saja</strong>; perintah dan eksekusinya ada di
          tier developer.
        </p>

        {memuat && (
          <div style={{ ...CARD, padding: 28, fontFamily: MONO, fontSize: 12, color: ACCENT }}
               className="animate-pulse">
            Memuat porto AI…
          </div>
        )}

        {galat && !memuat && (
          <div style={{ ...CARD, padding: 24, color: DOWN, fontSize: 14 }}>{galat}</div>
        )}

        {!memuat && !galat && snapshot && (
          <>
            {/* Ringkasan */}
            <div style={{ ...CARD, padding: 22, marginBottom: 18 }}>
              <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: FAINT }}>
                Nilai portofolio
              </p>
              <div className="flex items-baseline gap-3 flex-wrap" style={{ marginTop: 8 }}>
                <span style={{ fontFamily: MONO, fontSize: 30, fontWeight: 700 }}>{rp(snapshot.total_value)}</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: naik ? UP : DOWN }}>
                  {naik ? '▲' : '▼'} {rp(Math.abs(pnl))} ({pnlPct.toFixed(2)}%)
                </span>
              </div>
              <p style={{ fontSize: 11.5, color: FAINT, marginTop: 6 }}>
                dibanding modal awal {rp(MODAL_AWAL)}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginTop: 18 }}>
                <Stat label="Kas" value={rp(snapshot.cash)} />
                <Stat label="Diinvestasikan" value={rp(snapshot.invested)} />
                <Stat label="Unrealized" value={rp(snapshot.unrealized)} color={snapshot.unrealized >= 0 ? UP : DOWN} />
                <Stat label="Realized" value={rp(snapshot.realized)} color={snapshot.realized >= 0 ? UP : DOWN} />
              </div>
            </div>

            {/* Holdings */}
            <div style={{ ...CARD, padding: 22, marginBottom: 18 }}>
              <h2 style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: FAINT, marginBottom: 14 }}>
                Posisi terbuka ({snapshot.position_count})
              </h2>
              {snapshot.holdings.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {snapshot.holdings.map((h, i) => (
                    <div
                      key={h.ticker}
                      className="flex items-center justify-between gap-3"
                      style={{ padding: '11px 0', borderTop: i === 0 ? 'none' : `1px solid #F2F1EC` }}
                    >
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 700, fontSize: 14 }}>{h.ticker}</div>
                        <div style={{ fontSize: 11.5, color: MUTED }}>{h.lots} lot @ {rp(h.avg_price)}</div>
                      </div>
                      <div style={{ textAlign: 'right', flex: 'none' }}>
                        <div style={{ fontFamily: MONO, fontSize: 13 }}>{rp(h.current_price)}</div>
                        <div style={{ fontSize: 11.5, fontWeight: 700, color: h.unrealized_pnl >= 0 ? UP : DOWN }}>
                          {h.unrealized_pct == null ? '—' : `${h.unrealized_pct >= 0 ? '+' : ''}${h.unrealized_pct.toFixed(2)}%`}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: 13, color: FAINT }}>AI sedang tidak memegang posisi apa pun.</p>
              )}
            </div>

            {/* Histori — bagian utama halaman ini */}
            <div style={{ ...CARD, padding: 22 }}>
              <h2 style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: FAINT, marginBottom: 14 }}>
                Histori jual/beli{histori.length > 0 ? ` (${histori.length})` : ''}
              </h2>
              {histori.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  {historiTampil.map((t, i) => <BarisHistori key={t.id} t={t} pertama={i === 0} />)}
                </div>
              ) : (
                <p style={{ fontSize: 13, color: FAINT }}>Belum ada transaksi.</p>
              )}

              {adaSisa && (
                <button
                  type="button"
                  onClick={() => setBentangkan(b => !b)}
                  aria-expanded={bentangkan}
                  style={{
                    marginTop: 14, width: '100%', minHeight: 40, borderRadius: 10,
                    border: `1px solid ${HAIR}`, background: '#FBFBF9', cursor: 'pointer',
                    fontFamily: SANS, fontSize: 13, fontWeight: 700, color: MUTED,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                  }}
                >
                  {bentangkan
                    ? 'Ringkas'
                    : `Tampilkan ${histori.length - HISTORI_AWAL} transaksi lainnya`}
                  <span style={{ fontSize: 11, transform: bentangkan ? 'rotate(180deg)' : 'none' }}>▾</span>
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: '#FBFBF9', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 11px' }}>
      <p style={{ fontSize: 9.5, color: FAINT, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 3 }}>{label}</p>
      <p style={{ fontFamily: MONO, fontSize: 13, fontWeight: 700, color: color ?? INK }}>{value}</p>
    </div>
  );
}

function BarisHistori({ t, pertama }: { t: TradeHistory; pertama: boolean }) {
  const warna = t.action === 'BUY' ? UP : DOWN;
  const tanggal = (() => {
    const d = new Date(t.date);
    return isNaN(d.getTime()) ? t.date : d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });
  })();

  return (
    <div style={{ padding: '12px 0', borderTop: pertama ? 'none' : `1px solid #F2F1EC` }}>
      <div className="flex items-start justify-between gap-3">
        <div style={{ minWidth: 0 }}>
          <div className="flex items-center gap-2 flex-wrap">
            <span style={{ fontFamily: MONO, fontSize: 9.5, fontWeight: 700, color: warna, background: `color-mix(in oklab, ${warna}, white 86%)`, padding: '1px 7px', borderRadius: 999 }}>
              {t.action === 'BUY' ? 'BELI' : 'JUAL'}
            </span>
            <span style={{ fontWeight: 700, fontSize: 13.5 }}>{t.ticker}</span>
            <span style={{ fontSize: 11.5, color: MUTED }}>{t.quantity} lot @ {rp(t.price)}</span>
          </div>
          <div style={{ fontSize: 11, color: FAINT, marginTop: 3 }}>{tanggal}</div>
        </div>
        <div style={{ textAlign: 'right', flex: 'none' }}>
          <div style={{ fontFamily: MONO, fontSize: 12 }}>{rp(t.total_value)}</div>
          {t.pnl != null && (
            <div style={{ fontSize: 11.5, fontWeight: 700, color: t.pnl >= 0 ? UP : DOWN, marginTop: 2 }}>
              {t.pnl >= 0 ? '+' : ''}{rp(t.pnl)}
              {t.pnl_pct != null ? ` (${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(1)}%)` : ''}
            </div>
          )}
        </div>
      </div>

      {/* Alasan AI. Inilah yang membuat halaman ini layak dibuka — bukan sekadar
          daftar angka, tapi kenapa angkanya begitu. */}
      {t.notes && (
        <p style={{ fontSize: 12, color: MUTED, lineHeight: 1.55, marginTop: 7, paddingLeft: 2 }}>
          {t.notes}
        </p>
      )}
    </div>
  );
}
