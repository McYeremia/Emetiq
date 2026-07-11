'use client';

import { useEffect, useState } from 'react';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import { useAuth } from '@/components/AuthProvider';
import {
  api,
  BigMoneyPick,
  BigMoneyRegime,
  BigMoneyReport,
  BigMoneyTopAccumulation,
  TelegramLinkCode,
} from '@/lib/api';

// ── EMETIQ theme tokens ────────────────────────────────────────
const ACCENT = '#F26A1B';
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#56564F';
const FAINT = '#9A9A92';
const HAIR = '#ECEBE6';
const UP = '#138A50';
const DOWN = '#D23B3B';
const AMBER = '#B7791F';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

const CARD: React.CSSProperties = {
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 16,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

/** Rupiah dalam skala yang bisa dibaca manusia. Angka asing berorde miliar-triliun;
 *  menampilkannya utuh membuat mata harus menghitung digit. */
function rupiah(value: number | null): string {
  if (value === null || value === undefined) return '—';
  const abs = Math.abs(value);
  const sign = value < 0 ? '−' : '+';
  if (abs >= 1_000_000_000_000) return `${sign}Rp ${(abs / 1_000_000_000_000).toFixed(2)} T`;
  if (abs >= 1_000_000_000) return `${sign}Rp ${(abs / 1_000_000_000).toFixed(1)} M`;
  if (abs >= 1_000_000) return `${sign}Rp ${(abs / 1_000_000).toFixed(0)} jt`;
  return `${sign}Rp ${abs.toLocaleString('id-ID')}`;
}

function convictionColor(c: string) {
  if (c === 'STRONG') return UP;
  if (c === 'WATCH') return AMBER;
  return MUTED;
}

function phaseColor(p: string) {
  if (p === 'AKUMULASI' || p === 'MARKUP') return UP;
  if (p === 'DISTRIBUSI' || p === 'MARKDOWN') return DOWN;
  return MUTED;
}

const SIGNAL_LABELS: Array<[keyof NonNullable<BigMoneyPick['subscores']>, string]> = [
  ['relative_foreign_flow', 'Aliran asing'],
  ['foreign_persistence', 'Konsistensi'],
  ['big_ticket', 'Tiket besar'],
  ['cost_basis', 'Harga masuk'],
  ['volume_price', 'Volume/harga'],
];

export default function BigMoneyClient() {
  return (
    <RequireAuth>
      <BigMoneyInner />
    </RequireAuth>
  );
}

function BigMoneyInner() {
  useEffect(() => {
    document.title = 'Big Money — EMETIQ';
  }, []);

  const { tier } = useAuth();
  const [regime, setRegime] = useState<BigMoneyRegime | null>(null);
  const [top, setTop] = useState<BigMoneyTopAccumulation | null>(null);
  const [report, setReport] = useState<BigMoneyReport | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Backend menolak non-dev dengan 403, jadi jangan meminta apa pun untuk mereka.
  const isDev = tier === 'dev';
  const loading = isDev && !loaded;

  useEffect(() => {
    if (!isDev) return;

    Promise.all([
      api.getBigMoneyRegime(),
      api.getBigMoneyTopAccumulation(),
      api.getBigMoneyReport(),
    ])
      .then(([r, t, rep]) => {
        setRegime(r);
        setTop(t);
        setReport(rep);
      })
      .finally(() => setLoaded(true));
  }, [isDev]);

  // Backend menolak non-dev dengan 403; katakan apa adanya alih-alih menampilkan halaman kosong.
  if (tier && tier !== 'dev') {
    return (
      <div style={{ minHeight: '100vh', background: BG, fontFamily: SANS }}>
        <EmetiqNav />
        <main style={{ maxWidth: 720, margin: '0 auto', padding: '64px 20px', textAlign: 'center' }}>
          <p style={{ color: MUTED, fontSize: 15 }}>
            Big Money masih dalam pengembangan dan terbatas untuk tier <strong>dev</strong>.
          </p>
        </main>
      </div>
    );
  }

  const sectors = regime ? Object.entries(regime.sector_rotation).sort((a, b) => b[1] - a[1]) : [];
  const inflow = sectors.filter(([, v]) => v > 0).slice(0, 3);
  const outflow = sectors.filter(([, v]) => v < 0).slice(-3).reverse();

  return (
    <div style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS }}>
      <EmetiqNav />

      <main style={{ maxWidth: 1000, margin: '0 auto', padding: '28px 20px 80px' }}>
        <header style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap', marginBottom: 6 }}>
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.01em' }}>Big Money</h1>
          <span style={{
            fontSize: 11, fontWeight: 700, letterSpacing: '.06em', color: '#fff',
            background: ACCENT, padding: '3px 9px', borderRadius: 999,
          }}>
            DEV
          </span>
          {regime && (
            <span style={{ fontFamily: MONO, fontSize: 12.5, color: FAINT }}>{regime.date}</span>
          )}
        </header>
        <p style={{ color: MUTED, fontSize: 14.5, marginBottom: 24 }}>
          Ke mana dana besar mengalir hari ini, dan atas dasar bukti apa.
        </p>

        {loading && (
          <p style={{ fontFamily: MONO, fontSize: 12, color: ACCENT, letterSpacing: '.2em' }}>MEMUAT…</p>
        )}

        {!loading && !regime && (
          <div style={{ ...CARD, padding: 24 }}>
            <p style={{ color: MUTED, fontSize: 14.5 }}>
              Belum ada hari yang di-skor. Jalankan <code style={{ fontFamily: MONO }}>scripts/bigmoney_score.py</code> di backend.
            </p>
          </div>
        )}

        {!loading && regime && (
          <>
            {/* 1 — Rezim pasar */}
            <section style={{ ...CARD, padding: 20, marginBottom: 18 }}>
              <h2 style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.12em', color: FAINT, marginBottom: 14 }}>
                REZIM PASAR
              </h2>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 16 }}>
                <Metric label="Volatilitas" value={regime.volatility_regime}
                        color={regime.volatility_regime === 'VOLATILE' ? AMBER : UP} />
                <Metric label="Tren" value={regime.trend_regime}
                        color={regime.trend_regime === 'BEAR' ? DOWN : regime.trend_regime === 'BULL' ? UP : MUTED} />
                <Metric label="Net asing pasar" value={rupiah(regime.total_foreign_net_value)}
                        color={(regime.total_foreign_net_value ?? 0) < 0 ? DOWN : UP} />
                <Metric label="Saham naik"
                        value={regime.breadth !== null ? `${(regime.breadth * 100).toFixed(0)}%` : '—'}
                        color={INK} />
              </div>

              {(inflow.length > 0 || outflow.length > 0) && (
                <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', marginTop: 20, paddingTop: 16, borderTop: `1px solid ${HAIR}` }}>
                  <SectorList title="Dituju asing" rows={inflow} color={UP} />
                  <SectorList title="Ditinggalkan asing" rows={outflow} color={DOWN} />
                </div>
              )}
            </section>

            {/* 2 — Laporan Gemini */}
            <section style={{ ...CARD, padding: 20, marginBottom: 18 }}>
              <h2 style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.12em', color: FAINT, marginBottom: 14 }}>
                LAPORAN HARIAN
              </h2>
              {report ? (
                <>
                  <h3 style={{ fontSize: 18, fontWeight: 700, lineHeight: 1.35, marginBottom: 10 }}>{report.headline}</h3>
                  <p style={{ whiteSpace: 'pre-wrap', color: MUTED, fontSize: 14.5, lineHeight: 1.7 }}>{report.narrative}</p>
                  <p style={{ fontFamily: MONO, fontSize: 11, color: FAINT, marginTop: 14 }}>
                    ditulis {report.model} · {report.date}
                  </p>
                </>
              ) : (
                <p style={{ color: MUTED, fontSize: 14.5 }}>
                  Belum ada laporan. Set <code style={{ fontFamily: MONO }}>GEMINI_API_KEY</code> lalu jalankan{' '}
                  <code style={{ fontFamily: MONO }}>scripts/bigmoney_report.py</code>. Angka di bawah tetap terbaca tanpa laporan.
                </p>
              )}
            </section>

            {/* 3 — Top akumulasi */}
            <section style={{ ...CARD, padding: 20 }}>
              <h2 style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.12em', color: FAINT, marginBottom: 4 }}>
                TOP AKUMULASI
              </h2>
              <p style={{ fontSize: 12.5, color: FAINT, marginBottom: 16 }}>
                Peringkat relatif terhadap saham lain hari itu. Klik baris untuk melihat rincian skornya.
              </p>

              {(top?.data.length ?? 0) === 0 && (
                <p style={{ color: MUTED, fontSize: 14.5 }}>Tak ada saham yang lolos ambang hari ini.</p>
              )}

              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {top?.data.map(pick => (
                  <PickRow
                    key={pick.ticker}
                    pick={pick}
                    open={expanded === pick.ticker}
                    onToggle={() => setExpanded(expanded === pick.ticker ? null : pick.ticker)}
                  />
                ))}
              </div>
            </section>

            <TelegramLink />

            <p style={{ fontSize: 12, color: FAINT, lineHeight: 1.65, marginTop: 20 }}>
              {top?.disclaimer || regime.disclaimer}
            </p>
          </>
        )}
      </main>
    </div>
  );
}

/** Penautan Telegram. Kode sekali pakai, bukan email: bukti kepemilikannya adalah
 *  sesi login ini. Kode tampil sekali dan kedaluwarsa — tidak disimpan di klien. */
function TelegramLink() {
  const [code, setCode] = useState<TelegramLinkCode | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const request = async () => {
    setBusy(true);
    setFailed(false);
    const issued = await api.issueTelegramCode();
    if (issued) setCode(issued);
    else setFailed(true);
    setBusy(false);
  };

  return (
    <section style={{ ...CARD, padding: 20, marginTop: 18 }}>
      <h2 style={{ fontSize: 12, fontWeight: 700, letterSpacing: '.12em', color: FAINT, marginBottom: 6 }}>
        NOTIFIKASI TELEGRAM
      </h2>
      <p style={{ fontSize: 13.5, color: MUTED, marginBottom: 14, lineHeight: 1.6 }}>
        Terima laporan harian ini otomatis tiap sore lewat bot Telegram EMETIQ.
      </p>

      {code ? (
        <div>
          <div style={{
            fontFamily: MONO, fontSize: 22, fontWeight: 700, letterSpacing: '.12em',
            color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 92%)`,
            padding: '12px 16px', borderRadius: 12, display: 'inline-block',
          }}>
            {code.code}
          </div>
          <p style={{ fontSize: 13.5, color: MUTED, marginTop: 12, lineHeight: 1.6 }}>
            Kirim <code style={{ fontFamily: MONO, color: INK }}>/start {code.code}</code> ke bot Telegram EMETIQ.
            Kode hangus setelah dipakai dan kedaluwarsa dalam {code.expires_in_minutes} menit.
          </p>
        </div>
      ) : (
        <button
          onClick={request}
          disabled={busy}
          style={{
            background: '#fff', border: `1px solid ${HAIR}`, color: INK, fontFamily: SANS,
            fontWeight: 600, fontSize: 13.5, padding: '9px 15px', borderRadius: 10,
            cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? 'Membuat kode…' : 'Hubungkan Telegram'}
        </button>
      )}

      {failed && (
        <p style={{ fontSize: 13, color: DOWN, marginTop: 10 }}>
          Gagal membuat kode. Coba lagi.
        </p>
      )}
    </section>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <div style={{ fontSize: 11.5, color: FAINT, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color, fontFamily: MONO }}>{value}</div>
    </div>
  );
}

function SectorList({ title, rows, color }: { title: string; rows: [string, number][]; color: string }) {
  if (rows.length === 0) return null;
  return (
    <div style={{ minWidth: 190 }}>
      <div style={{ fontSize: 11.5, color: FAINT, marginBottom: 8 }}>{title}</div>
      {rows.map(([sector, value]) => (
        <div key={sector} style={{ display: 'flex', justifyContent: 'space-between', gap: 16, fontSize: 13.5, padding: '3px 0' }}>
          <span style={{ color: INK }}>{sector}</span>
          <span style={{ fontFamily: MONO, color, fontSize: 12.5 }}>{rupiah(value)}</span>
        </div>
      ))}
    </div>
  );
}

function PickRow({ pick, open, onToggle }: { pick: BigMoneyPick; open: boolean; onToggle: () => void }) {
  const risky = pick.flags?.pump_dump_risk;
  const diverging = pick.flags?.divergence;

  return (
    <div style={{ borderTop: `1px solid ${HAIR}` }}>
      <button
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12, padding: '13px 2px',
          background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', fontFamily: SANS,
        }}
      >
        <span style={{ fontFamily: MONO, fontSize: 12, color: FAINT, width: 20 }}>{pick.rank}</span>

        <span style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: 15 }}>{pick.ticker}</span>
            <span style={{ fontSize: 11, fontWeight: 700, color: phaseColor(pick.phase) }}>{pick.phase}</span>
            {risky && (
              <span style={{ fontSize: 10.5, fontWeight: 700, color: '#fff', background: DOWN, padding: '2px 7px', borderRadius: 999 }}>
                RISIKO PUMP
              </span>
            )}
            {diverging && (
              <span style={{ fontSize: 10.5, fontWeight: 700, color: AMBER }}>DIVERGENSI</span>
            )}
          </span>
          <span style={{ fontSize: 12, color: FAINT }}>
            asing {rupiah(pick.foreign_net_value)} · {pick.days_confirmed ?? 0} hari beruntun
          </span>
        </span>

        <span style={{ textAlign: 'right' }}>
          <span style={{ display: 'block', fontFamily: MONO, fontSize: 15, fontWeight: 700 }}>
            {pick.composite?.toFixed(0) ?? '—'}
          </span>
          <span style={{ fontSize: 11, fontWeight: 700, color: convictionColor(pick.conviction) }}>
            {pick.conviction}
          </span>
        </span>
      </button>

      {open && pick.subscores && (
        <div style={{ padding: '4px 2px 16px 32px', display: 'flex', flexDirection: 'column', gap: 7 }}>
          {SIGNAL_LABELS.map(([key, label]) => {
            const score = pick.subscores![key] ?? 0;
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 12, color: MUTED, width: 100 }}>{label}</span>
                <span style={{ flex: 1, height: 5, background: HAIR, borderRadius: 999, overflow: 'hidden', maxWidth: 260 }}>
                  <span style={{ display: 'block', width: `${score}%`, height: '100%', background: ACCENT }} />
                </span>
                <span style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT, width: 26, textAlign: 'right' }}>
                  {score.toFixed(0)}
                </span>
              </div>
            );
          })}
          {pick.close !== null && (
            <p style={{ fontSize: 12, color: FAINT, marginTop: 4 }}>
              Harga {pick.close.toLocaleString('id-ID')} · {pick.change_pct?.toFixed(2) ?? '—'}% hari ini
            </p>
          )}
        </div>
      )}
    </div>
  );
}
