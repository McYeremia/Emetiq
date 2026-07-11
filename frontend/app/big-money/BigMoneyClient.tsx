'use client';

import { useEffect, useState } from 'react';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import { useAuth } from '@/components/AuthProvider';
import {
  api,
  BigMoneyPick,
  BigMoneyPosition,
  BigMoneyPositions,
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
const UP_BG = '#E7F6EE';
const DOWN_BG = '#FBE9E9';
const AMBER = '#B7791F';
const AMBER_BG = '#FBF3E3';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

const CARD: React.CSSProperties = {
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 18,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

const EYEBROW: React.CSSProperties = {
  fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em',
  textTransform: 'uppercase', color: ACCENT, marginBottom: 6,
};

// ── Pembaca angka ──────────────────────────────────────────────

/** "Jumat, 10 Juli 2026" — bukan "2026-07-10". Laporan dibaca manusia. */
function tanggalPanjang(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('id-ID', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });
}

function rupiah(value: number | null): string {
  if (value === null || value === undefined) return '—';
  const abs = Math.abs(value);
  const tanda = value < 0 ? '−' : '+';
  if (abs >= 1_000_000_000_000) return `${tanda}Rp ${(abs / 1_000_000_000_000).toFixed(2)} T`;
  if (abs >= 1_000_000_000) return `${tanda}Rp ${(abs / 1_000_000_000).toFixed(1)} M`;
  if (abs >= 1_000_000) return `${tanda}Rp ${(abs / 1_000_000).toFixed(0)} jt`;
  return `${tanda}Rp ${abs.toLocaleString('id-ID')}`;
}

/** Rezim dalam bahasa manusia. "VOLATILE/BULL" tak berarti apa-apa bagi pembaca. */
function bacaRezim(r: BigMoneyRegime): { kalimat: string; nada: string; latar: string } {
  const gejolak = r.volatility_regime === 'VOLATILE' ? 'Pasar sedang bergejolak' : 'Pasar relatif tenang';
  const tren =
    r.trend_regime === 'BULL' ? 'dengan tren naik'
    : r.trend_regime === 'BEAR' ? 'dengan tren turun'
    : 'dan bergerak datar';

  const nada = r.trend_regime === 'BEAR' ? DOWN : r.trend_regime === 'BULL' ? UP : MUTED;
  const latar = r.trend_regime === 'BEAR' ? DOWN_BG : r.trend_regime === 'BULL' ? UP_BG : '#F4F3EF';

  return { kalimat: `${gejolak} ${tren}.`, nada, latar };
}

/** Satu kalimat: ke mana uang besar bergerak hari ini. */
function bacaAliran(r: BigMoneyRegime): string {
  const net = r.total_foreign_net_value ?? 0;
  if (net === 0) return 'Aliran dana asing hari ini seimbang.';
  const arah = net > 0 ? 'masuk ke' : 'keluar dari';
  return `Investor asing ${net > 0 ? 'membeli' : 'menjual'} bersih ${rupiah(Math.abs(net)).replace('+', '')} — dana ${arah} pasar Indonesia.`;
}

const KONVIKSI: Record<string, { label: string; warna: string; latar: string }> = {
  STRONG: { label: 'Kuat', warna: UP, latar: UP_BG },
  WATCH: { label: 'Pantau', warna: AMBER, latar: AMBER_BG },
  WEAK: { label: 'Lemah', warna: MUTED, latar: '#F4F3EF' },
};

const FASE: Record<string, string> = {
  AKUMULASI: 'Akumulasi',
  MARKUP: 'Markup',
  DISTRIBUSI: 'Distribusi',
  MARKDOWN: 'Markdown',
  NETRAL: 'Netral',
};

function warnaFase(fase: string) {
  if (fase === 'AKUMULASI' || fase === 'MARKUP') return UP;
  if (fase === 'DISTRIBUSI' || fase === 'MARKDOWN') return DOWN;
  return MUTED;
}

/** Nama sinyal dalam bahasa manusia, dengan penjelasan singkat di tooltip. */
const SINYAL: Array<[keyof NonNullable<BigMoneyPick['subscores']>, string, string]> = [
  ['relative_foreign_flow', 'Aliran asing', 'Seberapa besar dana asing masuk ke saham ini dibanding saham lain hari ini'],
  ['foreign_persistence', 'Konsistensi', 'Berapa hari dari 5 hari terakhir asing tercatat beli bersih'],
  ['big_ticket', 'Tiket besar', 'Nilai rata-rata per transaksi dibanding kebiasaan saham ini — tanda institusi masuk'],
  ['cost_basis', 'Harga masuk', 'Posisi harga sekarang terhadap harga rata-rata saat asing mengakumulasi'],
  ['volume_price', 'Volume vs harga', 'Volume besar tapi harga diam — ciri akumulasi senyap'],
];

// ── Halaman ────────────────────────────────────────────────────

export default function BigMoneyClient() {
  return (
    <RequireAuth>
      <BigMoneyInner />
    </RequireAuth>
  );
}

function BigMoneyInner() {
  useEffect(() => { document.title = 'Big Money — EMETIQ'; }, []);

  const { tier } = useAuth();
  const [regime, setRegime] = useState<BigMoneyRegime | null>(null);
  const [top, setTop] = useState<BigMoneyTopAccumulation | null>(null);
  const [report, setReport] = useState<BigMoneyReport | null>(null);
  const [positions, setPositions] = useState<BigMoneyPositions | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [showAllPositions, setShowAllPositions] = useState(false);

  // Backend menolak non-dev dengan 403, jadi jangan meminta apa pun untuk mereka.
  const isDev = tier === 'dev';
  const loading = isDev && !loaded;

  useEffect(() => {
    if (!isDev) return;
    Promise.all([
      api.getBigMoneyRegime(),
      api.getBigMoneyTopAccumulation(),
      api.getBigMoneyReport(),
      api.getBigMoneyPositions(),
    ])
      .then(([r, t, rep, pos]) => { setRegime(r); setTop(t); setReport(rep); setPositions(pos); })
      .finally(() => setLoaded(true));
  }, [isDev]);

  const sektor = regime ? Object.entries(regime.sector_rotation).sort((a, b) => b[1] - a[1]) : [];
  const masuk = sektor.filter(([, v]) => v > 0).slice(0, 4);
  const keluar = sektor.filter(([, v]) => v < 0).slice(-4).reverse();

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      {/* Fonts — React 19 hoists these into <head> */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav active="big-money" />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 24px 80px' }}>
        {/* Judul */}
        <div className="mb-6">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>Big Money</h1>
            <span style={{
              fontFamily: MONO, fontSize: 10.5, fontWeight: 600, letterSpacing: '.1em',
              color: '#fff', background: ACCENT, padding: '3px 8px', borderRadius: 999,
            }}>DEV</span>
          </div>
          <p style={{ marginTop: 4, fontSize: 14.5, color: MUTED }}>
            Ke mana dana besar mengalir hari ini, dan atas dasar bukti apa.
          </p>
        </div>

        {!isDev && tier && (
          <div style={{ ...CARD, padding: 24 }}>
            <p style={{ fontSize: 14.5, color: MUTED }}>
              Big Money masih dalam pengembangan dan terbatas untuk tier <strong>dev</strong>.
            </p>
          </div>
        )}

        {loading && (
          <p style={{ fontFamily: MONO, fontSize: 11.5, letterSpacing: '.24em', color: ACCENT }} className="animate-pulse">
            MEMUAT…
          </p>
        )}

        {isDev && loaded && !regime && (
          <div style={{ ...CARD, padding: 24 }}>
            <p style={{ fontSize: 14.5, color: MUTED }}>
              Belum ada hari yang di-skor. Jalankan <code style={{ fontFamily: MONO }}>scripts/bigmoney_score.py</code> di backend.
            </p>
          </div>
        )}

        {isDev && loaded && regime && (
          <>
            {/* ── Ringkasan pasar ─────────────────────────────────────── */}
            <div style={{ ...CARD, padding: 24, marginBottom: 24 }}>
              <div className="flex flex-wrap items-start justify-between gap-3 mb-5">
                <div>
                  <p style={EYEBROW}>Kondisi Pasar</p>
                  <h2 style={{ fontSize: 19, fontWeight: 700, letterSpacing: '-.01em', lineHeight: 1.4 }}>
                    {bacaRezim(regime).kalimat}
                  </h2>
                  <p style={{ marginTop: 6, fontSize: 14.5, color: MUTED, maxWidth: 620, lineHeight: 1.6 }}>
                    {bacaAliran(regime)}
                  </p>
                </div>
                <span style={{
                  fontSize: 12.5, fontWeight: 600, color: bacaRezim(regime).nada,
                  background: bacaRezim(regime).latar, padding: '6px 12px', borderRadius: 999, flex: 'none',
                }}>
                  {tanggalPanjang(regime.date)}
                </span>
              </div>

              <div className="bm-metrics" style={{ display: 'grid', gap: 18 }}>
                <Metrik
                  label="Aliran asing hari ini"
                  nilai={rupiah(regime.total_foreign_net_value)}
                  warna={(regime.total_foreign_net_value ?? 0) < 0 ? DOWN : UP}
                  catatan={(regime.total_foreign_net_value ?? 0) < 0 ? 'dana keluar dari pasar' : 'dana masuk ke pasar'}
                />
                <Metrik
                  label="Saham yang naik"
                  nilai={regime.breadth !== null ? `${Math.round(regime.breadth * 100)}%` : '—'}
                  warna={(regime.breadth ?? 0) >= 0.5 ? UP : DOWN}
                  catatan="dari saham yang bergerak"
                />
                <Metrik
                  label="Gerak pasar"
                  nilai={regime.market_return_pct !== null ? `${regime.market_return_pct >= 0 ? '+' : ''}${regime.market_return_pct.toFixed(2)}%` : '—'}
                  warna={(regime.market_return_pct ?? 0) >= 0 ? UP : DOWN}
                  catatan="tertimbang nilai transaksi"
                />
                <Metrik
                  label="Ditransaksikan asing"
                  nilai={regime.foreign_participation !== null ? `${(regime.foreign_participation * 100).toFixed(0)}%` : '—'}
                  warna={INK}
                  catatan={regime.foreign_participation !== null
                    ? `sisanya ${(100 - regime.foreign_participation * 100).toFixed(0)}% domestik`
                    : 'dari volume bursa'}
                />
              </div>

              {/* Batas pengetahuan produk ini, ditulis terang-terangan. Pembaca yang mengira
                  melihat seluruh pasar akan salah menafsirkan setiap angka di bawahnya. */}
              <div style={{
                marginTop: 20, paddingTop: 16, borderTop: `1px solid ${HAIR}`,
                display: 'flex', gap: 10, alignItems: 'flex-start',
              }}>
                <span style={{ fontSize: 14, flex: 'none', lineHeight: 1.5 }}>👁️</span>
                <p style={{ fontSize: 12.5, color: MUTED, lineHeight: 1.65 }}>
                  <strong style={{ color: INK }}>Yang terlihat dan yang tidak.</strong>{' '}
                  Halaman ini melacak <strong>aliran dana asing</strong> — satu-satunya sisi yang
                  dipublikasikan IDX per saham. Perdagangan domestik
                  {regime.foreign_participation !== null && (
                    <> (sekitar {(100 - regime.foreign_participation * 100).toFixed(0)}% volume bursa hari ini)</>
                  )}{' '}
                  tidak terpisah datanya, sehingga akumulasi oleh institusi lokal tidak akan muncul di
                  sini. &ldquo;Tidak ada akumulasi&rdquo; di halaman ini berarti{' '}
                  <em>tidak ada akumulasi asing</em> — bukan tidak ada akumulasi sama sekali.
                </p>
              </div>
            </div>

            {/* ── Laporan + sektor ─────────────────────────────────────── */}
            <div className="bm-grid" style={{ display: 'grid', gap: 24, marginBottom: 24 }}>
              <div style={{ ...CARD, padding: 24 }}>
                <p style={EYEBROW}>Laporan Harian</p>
                {report ? (
                  <>
                    <h2 style={{ fontSize: 20, fontWeight: 700, lineHeight: 1.35, letterSpacing: '-.01em', marginBottom: 12 }}>
                      {report.headline}
                    </h2>
                    <div style={{ fontSize: 14.5, color: MUTED, lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>
                      {report.narrative}
                    </div>
                    <p style={{ fontFamily: MONO, fontSize: 10.5, color: FAINT, marginTop: 16 }}>
                      ditulis {report.model} · {tanggalPanjang(report.date)}
                    </p>
                  </>
                ) : (
                  <p style={{ fontSize: 14.5, color: MUTED, lineHeight: 1.7 }}>
                    Belum ada laporan untuk hari ini. Angka di bawah tetap terbaca tanpa laporan.
                  </p>
                )}
              </div>

              <div style={{ ...CARD, padding: 24 }}>
                <p style={EYEBROW}>Rotasi Sektor</p>
                <p style={{ fontSize: 13, color: FAINT, marginBottom: 16, lineHeight: 1.55 }}>
                  Sektor mana yang dituju dan ditinggalkan dana asing hari ini.
                </p>

                <DaftarSektor judul="Dituju" rows={masuk} warna={UP} />
                {masuk.length > 0 && keluar.length > 0 && (
                  <div style={{ height: 1, background: HAIR, margin: '16px 0' }} />
                )}
                <DaftarSektor judul="Ditinggalkan" rows={keluar} warna={DOWN} />
              </div>
            </div>

            {/* ── Akumulasi berjalan ───────────────────────────────────── */}
            {positions && positions.active.length > 0 && (
              <div style={{ ...CARD, padding: '24px 0 8px', marginBottom: 24 }}>
                <div style={{ padding: '0 24px' }}>
                  <p style={EYEBROW}>Akumulasi Berjalan</p>
                  <p style={{ fontSize: 13.5, color: MUTED, marginBottom: 4, lineHeight: 1.6, maxWidth: 700 }}>
                    Berbeda dari peringkat harian di bawah, daftar ini <strong>tidak berganti tiap hari</strong>.
                    Saham bertahan di sini selama akumulasi asingnya masih hidup — jadi perkembangannya
                    bisa diikuti.
                  </p>
                  <p style={{ fontSize: 12, color: FAINT, marginBottom: 16, lineHeight: 1.6, maxWidth: 700 }}>
                    Masuk: {positions.rules.entry} Keluar: {positions.rules.exit}
                  </p>
                </div>

                <div className="bm-rows">
                  {(showAllPositions ? positions.active : positions.active.slice(0, 15)).map(p => (
                    <BarisPosisi key={p.ticker} posisi={p} />
                  ))}
                </div>

                {positions.active.length > 15 && (
                  <div style={{ padding: '12px 24px 8px' }}>
                    <button
                      onClick={() => setShowAllPositions(!showAllPositions)}
                      style={{
                        background: 'none', border: 'none', color: ACCENT, fontFamily: SANS,
                        fontWeight: 600, fontSize: 13, cursor: 'pointer', padding: 0,
                      }}
                    >
                      {showAllPositions
                        ? 'Tampilkan 15 teratas saja'
                        : `Tampilkan ${positions.active.length - 15} posisi lainnya`}
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ── Baru keluar ──────────────────────────────────────────── */}
            {positions && positions.recently_closed.length > 0 && (
              <div style={{ ...CARD, padding: '24px 0 8px', marginBottom: 24 }}>
                <div style={{ padding: '0 24px' }}>
                  <p style={EYEBROW}>Baru Keluar</p>
                  <p style={{ fontSize: 13.5, color: MUTED, marginBottom: 16, lineHeight: 1.6, maxWidth: 700 }}>
                    Akumulasi yang sudah berakhir — asing melepas lebih dari separuh yang pernah ia
                    kumpulkan, atau mendistribusi dua hari beruntun.
                  </p>
                </div>
                <div className="bm-rows">
                  {positions.recently_closed.slice(0, 6).map(p => (
                    <BarisPosisi key={`${p.ticker}-${p.closed_on}`} posisi={p} />
                  ))}
                </div>
              </div>
            )}

            {/* ── Top akumulasi ────────────────────────────────────────── */}
            <div style={{ ...CARD, padding: '24px 0 8px' }}>
              <div style={{ padding: '0 24px' }}>
                <p style={EYEBROW}>Top Akumulasi</p>
                <p style={{ fontSize: 13.5, color: MUTED, marginBottom: 16, lineHeight: 1.6, maxWidth: 680 }}>
                  Peringkat <strong>relatif</strong> terhadap saham lain hari ini
                  {(regime.total_foreign_net_value ?? 0) < 0 && (
                    <> — saat asing menjual pasar, ini berarti <em>paling sedikit ditinggalkan</em>, bukan diborong</>
                  )}
                  . Klik baris untuk melihat buktinya.
                </p>
              </div>

              {(top?.data.length ?? 0) === 0 ? (
                <p style={{ padding: '0 24px 20px', fontSize: 14.5, color: MUTED }}>
                  Tak ada saham yang lolos ambang hari ini.
                </p>
              ) : (
                <div className="bm-rows">
                  {top?.data.map(pick => (
                    <BarisSaham
                      key={pick.ticker}
                      pick={pick}
                      open={expanded === pick.ticker}
                      onToggle={() => setExpanded(expanded === pick.ticker ? null : pick.ticker)}
                    />
                  ))}
                </div>
              )}
            </div>

            <TautanTelegram />

            <p style={{ fontSize: 12, color: FAINT, lineHeight: 1.7, marginTop: 20, maxWidth: 760 }}>
              {top?.disclaimer || regime.disclaimer}
            </p>
          </>
        )}
      </div>

      <style jsx global>{`
        .bm-metrics {
          grid-template-columns: repeat(4, 1fr);
        }
        .bm-grid {
          grid-template-columns: 1.6fr 1fr;
        }
        @media (max-width: 900px) {
          .bm-metrics { grid-template-columns: repeat(2, 1fr) !important; }
          .bm-grid { grid-template-columns: 1fr !important; }
        }
        .bm-rows > div {
          border-top: 1px solid #F2F1EC;
        }
        .bm-row {
          transition: background .14s ease;
        }
        .bm-row:hover {
          background: #FBFBF9;
        }
        ::selection {
          background: color-mix(in oklab, ${ACCENT}, white 70%);
        }
      `}</style>
    </main>
  );
}

// ── Komponen ───────────────────────────────────────────────────

function Metrik({ label, nilai, warna, catatan }: { label: string; nilai: string; warna: string; catatan?: string }) {
  return (
    <div>
      <div style={{ fontSize: 12, color: FAINT, marginBottom: 5 }}>{label}</div>
      <div style={{ fontFamily: MONO, fontSize: 17, fontWeight: 600, color: warna, letterSpacing: '-.01em' }}>{nilai}</div>
      {catatan && <div style={{ fontSize: 11.5, color: FAINT, marginTop: 3 }}>{catatan}</div>}
    </div>
  );
}

function DaftarSektor({ judul, rows, warna }: { judul: string; rows: [string, number][]; warna: string }) {
  if (rows.length === 0) return null;
  return (
    <div>
      <div style={{ fontSize: 11.5, color: FAINT, marginBottom: 8, fontWeight: 600 }}>{judul}</div>
      {rows.map(([sektor, nilai]) => (
        <div key={sektor} style={{ display: 'flex', justifyContent: 'space-between', gap: 14, padding: '5px 0', fontSize: 13.5 }}>
          <span>{sektor}</span>
          <span style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 600, color: warna, flex: 'none' }}>
            {rupiah(nilai)}
          </span>
        </div>
      ))}
    </div>
  );
}

const ALASAN_TUTUP: Record<string, string> = {
  OUTFLOW: 'dana ditarik >50%',
  DISTRIBUSI: 'distribusi 2 hari',
  REVERSED: 'akumulasi berbalik',
};

/** Satu posisi: umur, akumulasi, perkembangan harga, dan seberapa dekat ia ke pintu keluar. */
function BarisPosisi({ posisi }: { posisi: BigMoneyPosition }) {
  const aktif = posisi.status === 'ACTIVE';
  const naik = (posisi.price_change_pct ?? 0) >= 0;
  const tarik = (posisi.outflow_ratio ?? 0) * 100;

  const umur = posisi.last_date && posisi.opened_on
    ? Math.max(0, Math.round(
        (new Date(posisi.last_date).getTime() - new Date(posisi.opened_on).getTime()) / 86_400_000))
    : 0;

  return (
    <div>
      <div className="bm-row" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '13px 24px' }}>
        <span style={{ display: 'flex', flexDirection: 'column', gap: 3, flex: 1, minWidth: 0 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: 14.5 }}>{posisi.ticker}</span>
            {aktif ? (
              <span style={{ fontSize: 11, fontWeight: 600, color: UP, background: UP_BG, padding: '1px 7px', borderRadius: 999 }}>
                berjalan {umur} hari
              </span>
            ) : (
              <span style={{ fontSize: 11, fontWeight: 600, color: DOWN, background: DOWN_BG, padding: '1px 7px', borderRadius: 999 }}>
                keluar · {ALASAN_TUTUP[posisi.close_reason ?? ''] ?? posisi.close_reason}
              </span>
            )}
          </span>
          <span style={{ fontSize: 12, color: FAINT }}>
            sejak {tanggalPanjang(posisi.opened_on)}
            {posisi.entry_close !== null && ` · masuk di ${posisi.entry_close.toLocaleString('id-ID')}`}
          </span>
        </span>

        {/* Akumulasi bersih — angka yang menjelaskan kenapa posisi ini ada */}
        <span className="hidden sm:block" style={{ textAlign: 'right', flex: 'none', width: 112 }}>
          <span style={{ display: 'block', fontFamily: MONO, fontSize: 13, fontWeight: 600, color: UP }}>
            {rupiah(posisi.accumulated_value)}
          </span>
          <span style={{ fontSize: 11, color: FAINT }}>akumulasi asing</span>
        </span>

        {/* Seberapa dekat ke pintu keluar: >50% ditarik = ditutup */}
        {aktif && posisi.outflow_ratio !== null && (
          <span className="hidden md:block" style={{ flex: 'none', width: 92 }}>
            <span style={{ display: 'block', height: 5, background: '#F2F1EC', borderRadius: 999, overflow: 'hidden' }}>
              <span style={{
                display: 'block', width: `${Math.min(100, tarik * 2)}%`, height: '100%',
                background: tarik > 35 ? DOWN : tarik > 15 ? AMBER : '#D6D5CE',
              }} />
            </span>
            <span style={{ fontSize: 11, color: FAINT, marginTop: 3, display: 'block' }}>
              {tarik.toFixed(0)}% ditarik
            </span>
          </span>
        )}

        <span style={{ textAlign: 'right', flex: 'none', width: 74 }}>
          <span style={{
            fontFamily: MONO, fontSize: 13, fontWeight: 600, color: naik ? UP : DOWN,
            background: naik ? UP_BG : DOWN_BG, padding: '2px 7px', borderRadius: 6,
            display: 'inline-block', minWidth: 68, textAlign: 'right',
          }}>
            {naik ? '▲' : '▼'} {Math.abs(posisi.price_change_pct ?? 0).toFixed(1)}%
          </span>
          <span style={{ fontSize: 11, color: FAINT, marginTop: 3, display: 'block' }}>sejak masuk</span>
        </span>
      </div>
    </div>
  );
}

function BarisSaham({ pick, open, onToggle }: { pick: BigMoneyPick; open: boolean; onToggle: () => void }) {
  const konviksi = KONVIKSI[pick.conviction] ?? KONVIKSI.WEAK;
  const naik = (pick.change_pct ?? 0) >= 0;

  return (
    <div>
      <button
        onClick={onToggle}
        className="bm-row"
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 14, padding: '13px 24px',
          background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left', fontFamily: SANS,
        }}
      >
        <span style={{ fontFamily: MONO, fontSize: 12, color: FAINT, width: 18, flex: 'none' }}>{pick.rank}</span>

        <span style={{ display: 'flex', flexDirection: 'column', gap: 3, flex: 1, minWidth: 0 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 700, fontSize: 14.5 }}>{pick.ticker}</span>
            <span style={{ fontSize: 11, fontWeight: 600, color: warnaFase(pick.phase) }}>
              {FASE[pick.phase] ?? pick.phase}
            </span>
            {pick.flags?.pump_dump_risk && (
              <span style={{ fontSize: 10.5, fontWeight: 700, color: '#fff', background: DOWN, padding: '2px 7px', borderRadius: 999 }}>
                RISIKO PUMP
              </span>
            )}
            {pick.flags?.divergence && (
              <span style={{ fontSize: 10.5, fontWeight: 600, color: AMBER, background: AMBER_BG, padding: '2px 7px', borderRadius: 999 }}>
                divergensi
              </span>
            )}
          </span>
          <span style={{ fontSize: 12, color: FAINT }}>
            asing {rupiah(pick.foreign_net_value)} · beli bersih {pick.days_confirmed ?? 0} hari beruntun
          </span>
        </span>

        {pick.close !== null && (
          <span className="hidden sm:flex" style={{ alignItems: 'center', gap: 8, flex: 'none' }}>
            <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 600 }}>
              {pick.close.toLocaleString('id-ID')}
            </span>
            {pick.change_pct !== null && (
              <span style={{
                fontFamily: MONO, fontSize: 11, fontWeight: 600, color: naik ? UP : DOWN,
                background: naik ? UP_BG : DOWN_BG, padding: '2px 7px', borderRadius: 6,
                minWidth: 64, textAlign: 'right',
              }}>
                {naik ? '▲' : '▼'} {Math.abs(pick.change_pct).toFixed(2)}%
              </span>
            )}
          </span>
        )}

        <span style={{ textAlign: 'right', flex: 'none', width: 74 }}>
          <span style={{ display: 'block', fontFamily: MONO, fontSize: 15, fontWeight: 700 }}>
            {pick.composite?.toFixed(0) ?? '—'}
          </span>
          <span style={{
            fontSize: 10.5, fontWeight: 600, color: konviksi.warna, background: konviksi.latar,
            padding: '1px 7px', borderRadius: 999,
          }}>
            {konviksi.label}
          </span>
        </span>
      </button>

      {open && pick.subscores && (
        <div style={{ padding: '2px 24px 18px 56px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {SINYAL.map(([key, label, penjelasan]) => {
            const skor = pick.subscores![key] ?? 0;
            return (
              <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 12 }} title={penjelasan}>
                <span style={{ fontSize: 12.5, color: MUTED, width: 118, flex: 'none' }}>{label}</span>
                <span style={{ flex: 1, height: 6, background: '#F2F1EC', borderRadius: 999, overflow: 'hidden', maxWidth: 300 }}>
                  <span style={{ display: 'block', width: `${skor}%`, height: '100%', background: ACCENT, borderRadius: 999 }} />
                </span>
                <span style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT, width: 24, textAlign: 'right', flex: 'none' }}>
                  {skor.toFixed(0)}
                </span>
              </div>
            );
          })}
          {pick.foreign_participation !== null && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid #F2F1EC` }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 12.5, color: MUTED, width: 118, flex: 'none' }}>Siapa yang bertransaksi</span>
                <span style={{ display: 'flex', flex: 1, maxWidth: 300, height: 6, borderRadius: 999, overflow: 'hidden' }}>
                  <span style={{ width: `${pick.foreign_participation * 100}%`, background: ACCENT }} />
                  <span style={{ flex: 1, background: '#DCDBD4' }} />
                </span>
                <span style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT, width: 24, textAlign: 'right', flex: 'none' }}>
                  {(pick.foreign_participation * 100).toFixed(0)}
                </span>
              </div>
              <p style={{ fontSize: 11.5, color: FAINT, marginTop: 6, lineHeight: 1.6 }}>
                <span style={{ color: ACCENT, fontWeight: 600 }}>
                  {(pick.foreign_participation * 100).toFixed(0)}% asing
                </span>
                {' · '}
                {(100 - pick.foreign_participation * 100).toFixed(0)}% domestik
                {pick.foreign_participation < 0.1 && (
                  <> — sebagian besar pergerakan saham ini digerakkan pemain lokal yang tak terlihat sinyal ini.</>
                )}
              </p>
            </div>
          )}

          <p style={{ fontSize: 11.5, color: FAINT, marginTop: 8, lineHeight: 1.6 }}>
            Nilai 0–100 adalah peringkat terhadap saham lain pada hari yang sama, bukan nilai mutlak.
          </p>
        </div>
      )}
    </div>
  );
}

/** Penautan Telegram. Kode sekali pakai, bukan email: bukti kepemilikannya sesi login ini. */
function TautanTelegram() {
  const [code, setCode] = useState<TelegramLinkCode | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  const request = async () => {
    setBusy(true);
    setFailed(false);
    const issued = await api.issueTelegramCode();
    if (issued) setCode(issued); else setFailed(true);
    setBusy(false);
  };

  return (
    <div style={{ ...CARD, padding: 24, marginTop: 24 }}>
      <p style={EYEBROW}>Notifikasi Telegram</p>
      <p style={{ fontSize: 14, color: MUTED, marginBottom: 14, lineHeight: 1.6 }}>
        Terima laporan ini otomatis tiap sore lewat bot Telegram EMETIQ.
      </p>

      {code ? (
        <>
          <div style={{
            fontFamily: MONO, fontSize: 21, fontWeight: 700, letterSpacing: '.14em', color: ACCENT,
            background: `color-mix(in oklab, ${ACCENT}, white 92%)`, padding: '12px 18px',
            borderRadius: 12, display: 'inline-block',
          }}>
            {code.code}
          </div>
          <p style={{ fontSize: 13.5, color: MUTED, marginTop: 12, lineHeight: 1.6 }}>
            Kirim <code style={{ fontFamily: MONO, color: INK }}>/start {code.code}</code> ke bot Telegram EMETIQ.
            Kode hangus setelah dipakai dan kedaluwarsa dalam {code.expires_in_minutes} menit.
          </p>
        </>
      ) : (
        <button
          onClick={request}
          disabled={busy}
          style={{
            background: '#fff', border: `1px solid ${HAIR}`, color: INK, fontFamily: SANS,
            fontWeight: 600, fontSize: 13.5, padding: '9px 16px', borderRadius: 11,
            cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.6 : 1,
          }}
        >
          {busy ? 'Membuat kode…' : 'Hubungkan Telegram'}
        </button>
      )}

      {failed && <p style={{ fontSize: 13, color: DOWN, marginTop: 10 }}>Gagal membuat kode. Coba lagi.</p>}
    </div>
  );
}
