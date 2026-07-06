'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { api, TradeHistory, PortfolioItem, AgentPortfolio } from '@/lib/api';
import { INITIAL_MODAL } from '@/lib/constants';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import dynamic from 'next/dynamic';
import Link from 'next/link';

const EquityChart = dynamic(() => import('@/components/EquityChart'), { ssr: false });

type ViewMode = 'portfolio' | 'analytics' | 'riwayat';

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
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

const CARD: React.CSSProperties = {
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 18,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

const TH: React.CSSProperties = { padding: '13px 18px', textAlign: 'left', fontFamily: MONO, fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: FAINT, fontWeight: 600, whiteSpace: 'nowrap' };
const THR: React.CSSProperties = { ...TH, textAlign: 'right' };
const TD: React.CSSProperties = { padding: '14px 18px', fontSize: 13, verticalAlign: 'middle' };
const TDR: React.CSSProperties = { ...TD, textAlign: 'right', fontFamily: MONO };

const DONUT_COLORS = ['#F26A1B', '#2563EB', '#0E9F6E', '#7C3AED', '#D97706', '#DB2777', '#0891B2', '#65A30D', '#DC2626'];

const ID_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];

function formatTanggal(d: string | null): string {
  if (!d) return '-';
  const [y, m, day] = d.split('-').map(Number);
  if (!y || !m || !day) return d;
  return `${day} ${ID_MONTHS[m - 1]} ${y}`;
}

function buildDonutPath(s: number, e: number, cx: number, cy: number, ro: number, ri: number) {
  const x1 = cx + ro * Math.cos(s), y1 = cy + ro * Math.sin(s);
  const x2 = cx + ro * Math.cos(e), y2 = cy + ro * Math.sin(e);
  const ix1 = cx + ri * Math.cos(e), iy1 = cy + ri * Math.sin(e);
  const ix2 = cx + ri * Math.cos(s), iy2 = cy + ri * Math.sin(s);
  const la = e - s > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${ro} ${ro} 0 ${la} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${ri} ${ri} 0 ${la} 0 ${ix2} ${iy2} Z`;
}

export default function PortfolioPage() {
  return (
    <RequireAuth>
      <PortfolioInner />
    </RequireAuth>
  );
}

function PortfolioInner() {
  useEffect(() => { document.title = 'Portofolio - EMETIQ'; }, []);
  const [port, setPort] = useState<AgentPortfolio | null>(null);
  const [growth, setGrowth] = useState<{ date: string; value: number }[]>([]);
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('portfolio');
  const [histDate, setHistDate] = useState('');
  const [donutHovered, setDonutHovered] = useState<{ ticker: string; pct: number; value: number } | null>(null);

  const isInitialLoad = useRef(true);

  const refresh = useCallback(async () => {
    const [portfolio, growthData, hist] = await Promise.all([
      api.getPortfolio(),
      api.getPortfolioGrowth(),
      api.getTradeHistory('USER'),
    ]);
    setPort(portfolio.USER);
    setGrowth(growthData.USER ?? []);
    setHistory(hist);
  }, []);

  useEffect(() => {
    if (isInitialLoad.current) {
      isInitialLoad.current = false;
      setLoading(true);
      refresh().finally(() => setLoading(false));
    }
  }, [refresh]);

  if (loading || !port) return (
    <div style={{ minHeight: '100vh', background: BG, fontFamily: MONO, color: ACCENT }} className="flex items-center justify-center text-xs tracking-[0.3em] uppercase animate-pulse">
      Memuat portofolio...
    </div>
  );

  const current = port;
  const totalReturn = current.total_value - INITIAL_MODAL;
  const totalReturnPct = ((totalReturn / INITIAL_MODAL) * 100).toFixed(2);
  const totalUp = totalReturn >= 0;
  const growthUp = growth.length > 1 ? growth[growth.length - 1].value >= growth[0].value : true;

  // Trade history: newest first; show last 10 by default, or a chosen date
  const sortedHistory = [...history].sort((a, b) => b.date.localeCompare(a.date) || b.id - a.id);
  const displayedHistory = histDate ? sortedHistory.filter(t => t.date === histDate) : sortedHistory.slice(0, 10);

  const exportToCSV = () => {
    if (displayedHistory.length === 0) return;
    const header = ['Tanggal', 'Ticker', 'Aksi', 'Harga', 'Lot', 'Total', 'P&L', 'P&L %'];
    const rows = displayedHistory.map(t => [
      formatTanggal(t.date),
      t.ticker,
      t.action,
      t.price.toString(),
      t.quantity.toString(),
      t.total_value.toLocaleString('id-ID'),
      t.pnl != null ? t.pnl.toLocaleString('id-ID') : '',
      t.pnl_pct != null ? t.pnl_pct.toFixed(2) + '%' : '',
    ]);
    const csv = [header, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `riwayat-transaksi-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Analytics
  const sellTrades = history.filter(t => t.action === 'SELL' && t.pnl !== null);
  const winCount = sellTrades.filter(t => t.pnl! > 0).length;
  const winRate = sellTrades.length > 0 ? (winCount / sellTrades.length * 100) : null;

  let maxDrawdownPct = 0;
  if (growth.length > 1) {
    let peak = growth[0].value;
    for (const pt of growth) {
      if (pt.value > peak) peak = pt.value;
      const dd = peak > 0 ? (peak - pt.value) / peak * 100 : 0;
      if (dd > maxDrawdownPct) maxDrawdownPct = dd;
    }
  }

  const monthlyPnl: Record<string, number> = {};
  for (const t of sellTrades) {
    const month = t.date.substring(0, 7);
    monthlyPnl[month] = (monthlyPnl[month] || 0) + (t.pnl || 0);
  }
  const monthlyRows = Object.entries(monthlyPnl).sort(([a], [b]) => b.localeCompare(a));
  const maxMonthlyAbs = monthlyRows.length > 0 ? Math.max(...monthlyRows.map(([, v]) => Math.abs(v))) : 1;

  const totalInvested = current.assets.reduce((sum: number, a: PortfolioItem) => sum + a.cost_basis, 0);
  const allocData = [...current.assets]
    .sort((a: PortfolioItem, b: PortfolioItem) => b.cost_basis - a.cost_basis)
    .map((a: PortfolioItem, i: number) => ({
      ticker: a.ticker,
      pct: totalInvested > 0 ? a.cost_basis / totalInvested * 100 : 0,
      value: a.cost_basis,
      color: DONUT_COLORS[i % DONUT_COLORS.length],
    }));

  let _angle = -Math.PI / 2;
  const donutSegments = allocData.map(seg => {
    const start = _angle;
    const end = _angle + (seg.pct / 100) * 2 * Math.PI;
    _angle = end;
    return { ...seg, pathD: buildDonutPath(start, end, 100, 100, 80, 55) };
  });

  const sectionLabel = (title: string, extra?: string): React.ReactNode => (
    <div className="flex items-center gap-3 mb-4">
      <h2 style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: FAINT }}>{title}</h2>
      <span style={{ flex: 1, height: 1, background: HAIR }} />
      {extra && <span style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT }}>{extra}</span>}
    </div>
  );

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      {/* Fonts — React 19 hoists these into <head> */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav active="portfolio" />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 24px 80px' }}>
        <div className="mb-6">
          <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-.02em' }}>Portofolio</h1>
          <p style={{ marginTop: 4, fontSize: 14.5, color: MUTED }}>Posisi aktif, performa, dan riwayat transaksi kamu.</p>
        </div>

        {/* TOTAL VALUE */}
        <div style={{ ...CARD, padding: 28, marginBottom: 24 }} className="flex flex-row justify-between items-center gap-2">
          <div style={{ minWidth: 0 }}>
            <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: FAINT, marginBottom: 6 }}>Total Nilai Portofolio</p>
            <p className="porto-total-val" style={{ fontFamily: MONO, fontWeight: 600, letterSpacing: '-.01em' }}>Rp {current.total_value.toLocaleString('id-ID')}</p>
          </div>
          <div className="text-right" style={{ flex: 'none' }}>
            <p className="porto-pct" style={{ fontFamily: MONO, fontWeight: 700, color: totalUp ? UP : DOWN }}>
              {totalUp ? '▲' : '▼'} {Math.abs(parseFloat(totalReturnPct))}%
            </p>
            <p className="porto-pnl" style={{ fontFamily: MONO, color: totalUp ? UP : DOWN }}>
              {totalUp ? '+' : ''}Rp {totalReturn.toLocaleString('id-ID')}
            </p>
          </div>
        </div>

        {/* CORE STATS */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-7">
          {[
            { label: 'Kas Tersedia', value: `Rp ${current.modal.toLocaleString('id-ID')}`, color: current.modal < 0 ? DOWN : INK },
            { label: 'Invested', value: `Rp ${current.invested.toLocaleString('id-ID')}`, color: INK },
            { label: 'Unrealized', value: `${current.unrealized >= 0 ? '+' : ''}Rp ${current.unrealized.toLocaleString('id-ID')}`, color: current.unrealized >= 0 ? UP : DOWN },
            { label: 'Realized', value: `${current.realized >= 0 ? '+' : ''}Rp ${current.realized.toLocaleString('id-ID')}`, color: current.realized >= 0 ? INK : DOWN },
          ].map(s => (
            <div key={s.label} style={{ ...CARD, padding: 20 }}>
              <p style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 8 }}>{s.label}</p>
              <p style={{ fontFamily: MONO, fontSize: 17, fontWeight: 600, color: s.color }}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* VIEW TOGGLE */}
        <div style={{ display: 'inline-flex', gap: 4, padding: 4, background: '#F2F1EC', borderRadius: 12, marginBottom: 28 }}>
          {(['portfolio', 'analytics', 'riwayat'] as const).map(m => {
            const active = viewMode === m;
            const label = m === 'portfolio' ? 'Portofolio' : m === 'analytics' ? 'Analitik' : 'Riwayat';
            return (
              <button
                key={m}
                onClick={() => setViewMode(m)}
                style={{ padding: '8px 18px', borderRadius: 9, fontSize: 12.5, fontWeight: 700, border: 'none', cursor: 'pointer', transition: 'all .15s ease', background: active ? '#fff' : 'transparent', color: active ? ACCENT : MUTED, boxShadow: active ? '0 1px 4px rgba(20,20,15,.08)' : 'none' }}
              >
                {label}
              </button>
            );
          })}
        </div>

        {viewMode === 'portfolio' && (<>
          {/* GROWTH CHART */}
          <div style={{ ...CARD, padding: 24, marginBottom: 28 }}>
            <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: ACCENT, marginBottom: 16 }}>Pertumbuhan Portofolio</p>
            {growth.length > 1 ? (
              <EquityChart data={growth} color={growthUp ? UP : DOWN} height={220} light />
            ) : (
              <div style={{ height: 220, color: FAINT, fontSize: 13 }} className="flex items-center justify-center">
                Belum ada riwayat untuk ditampilkan.
              </div>
            )}
          </div>

          {/* ACTIVE POSITIONS */}
          <div className="mb-9">
            {sectionLabel('Kepemilikan Saham')}
            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              <div className="overflow-x-auto">
                <table className="min-w-full holdings-table" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${HAIR}`, background: '#FBFBF9' }}>
                      <th style={TH}>Instrumen</th>
                      <th style={THR}>Invested</th>
                      <th style={THR}>Market Price</th>
                      <th style={THR}>P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {current.assets.length === 0 ? (
                      <tr><td colSpan={4} style={{ padding: '64px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>Belum ada posisi aktif.</td></tr>
                    ) : (
                      current.assets.map((item: PortfolioItem, i) => {
                        const lots = item.shares / 100;
                        const marketTotal = (item.current_price ?? 0) * item.shares;
                        const priceUp = (item.current_price ?? 0) >= (item.avg_price ?? 0);
                        const up = item.unrealized_pnl >= 0;
                        const pct = item.cost_basis > 0 ? (item.unrealized_pnl / item.cost_basis) * 100 : 0;
                        return (
                          <tr key={item.ticker} className="emx-listrow" style={{ borderBottom: i < current.assets.length - 1 ? '1px solid #F2F1EC' : 'none' }}>
                            <td style={TD}>
                              <Link href={`/stocks/${item.ticker}`} style={{ textDecoration: 'none', color: INK }} className="emx-link">
                                <span style={{ fontWeight: 700, fontSize: 15, display: 'block' }}>{item.ticker}</span>
                              </Link>
                              <span style={{ fontSize: 10.5, color: FAINT, display: 'block', marginTop: 2, whiteSpace: 'nowrap' }}>{lots} lot</span>
                            </td>
                            <td style={TDR} className="hold-cell">
                              <span className="hold-main" style={{ fontWeight: 600, display: 'block', whiteSpace: 'nowrap' }}>Rp {item.cost_basis.toLocaleString('id-ID')}</span>
                              <span style={{ fontSize: 10.5, color: FAINT, display: 'block', marginTop: 2, whiteSpace: 'nowrap' }}>Rp {item.avg_price?.toLocaleString('id-ID')}</span>
                            </td>
                            <td style={TDR} className="hold-cell">
                              <span className="hold-main" style={{ fontWeight: 600, display: 'block', whiteSpace: 'nowrap' }}>Rp {marketTotal.toLocaleString('id-ID')}</span>
                              <span style={{ fontSize: 10.5, color: priceUp ? UP : DOWN, display: 'block', marginTop: 2, whiteSpace: 'nowrap' }}>Rp {(item.current_price ?? 0).toLocaleString('id-ID')}</span>
                            </td>
                            <td style={TDR} className="hold-cell">
                              <span className="hold-main" style={{ fontWeight: 700, color: up ? UP : DOWN, display: 'block', whiteSpace: 'nowrap' }}>
                                {up ? '▲' : '▼'} Rp {Math.abs(item.unrealized_pnl).toLocaleString('id-ID')}
                              </span>
                              <span style={{ fontSize: 10.5, color: up ? UP : DOWN, opacity: .8, display: 'block', marginTop: 2, whiteSpace: 'nowrap' }}>
                                {up ? '+' : ''}{pct.toFixed(2)}%
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

        </>)}

        {viewMode === 'riwayat' && (
          <div className="mb-4">
            {sectionLabel('Riwayat Transaksi', histDate ? formatTanggal(histDate) : '10 terakhir')}

            {/* FILTER BAR: date only */}
            <div style={{ ...CARD, padding: 14, marginBottom: 14 }} className="flex items-center gap-3 flex-wrap">
              <label style={{ fontFamily: MONO, fontSize: 11.5, color: MUTED }}>Pilih tanggal</label>
              <input
                type="date"
                value={histDate}
                onChange={e => setHistDate(e.target.value)}
                className="emx-input"
                style={{ background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '8px 12px', fontSize: 13, fontFamily: MONO, color: INK }}
              />
              {histDate && (
                <button onClick={() => setHistDate('')} style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT, background: 'none', border: 'none', cursor: 'pointer' }}>Tampilkan 10 terakhir</button>
              )}
              <span style={{ marginLeft: 'auto', fontFamily: MONO, fontSize: 11, color: FAINT }}>{displayedHistory.length} transaksi</span>
              <button
                onClick={exportToCSV}
                disabled={displayedHistory.length === 0}
                title="Export ke CSV"
                className="emx-pill"
                style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: MUTED, border: `1px solid ${HAIR}`, background: '#fff', padding: '7px 12px', borderRadius: 8, cursor: 'pointer', opacity: displayedHistory.length === 0 ? 0.4 : 1 }}
              >
                ↓ CSV
              </button>
            </div>

            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              <div className="overflow-x-auto">
                <table className="min-w-full" style={{ borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ borderBottom: `1px solid ${HAIR}`, background: '#FBFBF9' }}>
                      <th style={TH}>Tanggal</th>
                      <th style={TH}>Ticker</th>
                      <th style={{ ...TH, textAlign: 'center' }}>Aksi</th>
                      <th style={THR} className="hist-col-hide">Lot</th>
                      <th style={THR} className="hist-col-hide">Harga</th>
                      <th style={THR} className="hist-col-hide">Total Nilai</th>
                      <th style={THR}>P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {displayedHistory.length === 0 ? (
                      <tr><td colSpan={7} style={{ padding: '64px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>{history.length === 0 ? 'Belum ada riwayat transaksi.' : 'Tidak ada transaksi pada tanggal ini.'}</td></tr>
                    ) : (
                      displayedHistory.map((t, i) => (
                        <tr key={t.id} className="emx-listrow" style={{ borderBottom: i < displayedHistory.length - 1 ? '1px solid #F2F1EC' : 'none' }}>
                          <td style={{ ...TD, color: MUTED, whiteSpace: 'nowrap' }}>{formatTanggal(t.date)}</td>
                          <td style={{ ...TD, fontWeight: 700 }}>{t.ticker}</td>
                          <td style={{ ...TD, textAlign: 'center' }}>
                            <span style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: t.action === 'BUY' ? UP : DOWN, background: t.action === 'BUY' ? UP_BG : DOWN_BG, padding: '3px 9px', borderRadius: 7 }}>{t.action}</span>
                          </td>
                          <td className="hist-col-hide" style={{ ...TDR, fontWeight: 600 }}>{t.quantity}</td>
                          <td className="hist-col-hide" style={TDR}>Rp {t.price.toLocaleString('id-ID')}</td>
                          <td className="hist-col-hide" style={{ ...TDR, color: t.action === 'BUY' ? DOWN : UP }}>
                            {t.action === 'BUY' ? '-' : '+'}Rp {t.total_value.toLocaleString('id-ID')}
                          </td>
                          <td style={TDR}>
                            {t.pnl !== null ? (
                              <>
                                <span style={{ fontWeight: 700, color: t.pnl >= 0 ? UP : DOWN, display: 'block' }}>
                                  {t.pnl >= 0 ? '+' : ''}Rp {Math.abs(t.pnl).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                                </span>
                                <span style={{ fontSize: 10.5, color: (t.pnl_pct ?? 0) >= 0 ? UP : DOWN, opacity: .8, display: 'block', marginTop: 2 }}>
                                  {(t.pnl_pct ?? 0) >= 0 ? '+' : ''}{t.pnl_pct?.toFixed(2)}%
                                </span>
                              </>
                            ) : (
                              <span style={{ color: '#B6B6AE' }}>-</span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {viewMode === 'analytics' && (
          <div className="pb-4">
            {sectionLabel('Metrik Risiko')}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-9">
              <div style={{ ...CARD, padding: 20 }}>
                <p style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 8 }}>Win Rate</p>
                <p style={{ fontSize: 24, fontWeight: 800, color: winRate !== null && winRate >= 50 ? UP : DOWN }}>{winRate !== null ? `${winRate.toFixed(1)}%` : '-'}</p>
                <p style={{ fontSize: 11, color: FAINT, marginTop: 4 }}>{winCount} menang / {sellTrades.length} jual</p>
              </div>
              <div style={{ ...CARD, padding: 20 }}>
                <p style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 8 }}>Max Drawdown</p>
                <p style={{ fontSize: 24, fontWeight: 800, color: DOWN }}>{maxDrawdownPct > 0 ? `-${maxDrawdownPct.toFixed(2)}%` : '-'}</p>
                <p style={{ fontSize: 11, color: FAINT, marginTop: 4 }}>dari puncak tertinggi</p>
              </div>
              <div style={{ ...CARD, padding: 20 }}>
                <p style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 8 }}>Total Transaksi</p>
                <p style={{ fontSize: 24, fontWeight: 800 }}>{history.length}</p>
                <p style={{ fontSize: 11, color: FAINT, marginTop: 4 }}>{history.filter(t => t.action === 'BUY').length} beli · {sellTrades.length} jual</p>
              </div>
              <div style={{ ...CARD, padding: 20 }}>
                <p style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginBottom: 8 }}>Realized P&amp;L</p>
                <p style={{ fontSize: 24, fontWeight: 800, color: current.realized >= 0 ? UP : DOWN }}>{current.realized >= 0 ? '+' : ''}Rp {Math.round(current.realized).toLocaleString('id-ID')}</p>
                <p style={{ fontSize: 11, color: FAINT, marginTop: 4 }}>dari transaksi jual</p>
              </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div style={{ ...CARD, padding: 24 }}>
                <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: ACCENT, marginBottom: 18 }}>Alokasi Portofolio</p>
                {allocData.length === 0 ? (
                  <div style={{ height: 160, color: FAINT, fontSize: 13 }} className="flex items-center justify-center">Tidak ada posisi aktif.</div>
                ) : (
                  <div className="flex flex-col md:flex-row items-center gap-8">
                    <svg viewBox="0 0 200 200" className="w-40 h-40 shrink-0">
                      {donutSegments.map(seg => (
                        <path
                          key={seg.ticker}
                          d={seg.pathD}
                          fill={seg.color}
                          opacity={donutHovered ? (donutHovered.ticker === seg.ticker ? 1 : 0.5) : 0.92}
                          cursor="pointer"
                          onMouseEnter={() => setDonutHovered({ ticker: seg.ticker, pct: seg.pct, value: seg.value })}
                          onMouseLeave={() => setDonutHovered(null)}
                        />
                      ))}
                      <circle cx="100" cy="100" r="46" fill="#fff" />
                      {donutHovered ? (
                        <>
                          <text x="100" y="95" textAnchor="middle" fill={INK} fontSize="13" fontWeight="bold" fontFamily="monospace">{donutHovered.ticker}</text>
                          <text x="100" y="110" textAnchor="middle" fill={ACCENT} fontSize="11" fontFamily="monospace">{donutHovered.pct.toFixed(1)}%</text>
                        </>
                      ) : (
                        <>
                          <text x="100" y="98" textAnchor="middle" fill={INK} fontSize="18" fontWeight="bold" fontFamily="monospace">{current.assets.length}</text>
                          <text x="100" y="112" textAnchor="middle" fill={FAINT} fontSize="8" fontFamily="monospace">SAHAM</text>
                        </>
                      )}
                    </svg>
                    <div className="flex-1 space-y-2.5 min-w-0" style={{ width: '100%' }}>
                      {allocData.map(seg => (
                        <div key={seg.ticker} className="flex items-center gap-2">
                          <span className="shrink-0" style={{ width: 10, height: 10, borderRadius: '50%', background: seg.color }} />
                          <span className="shrink-0" style={{ fontWeight: 700, fontSize: 12.5, width: 64 }}>{seg.ticker}</span>
                          <div className="flex-1 min-w-0" style={{ background: '#F2F1EC', borderRadius: 999, height: 6 }}>
                            <div style={{ height: 6, borderRadius: 999, width: `${seg.pct}%`, background: seg.color }} />
                          </div>
                          <span className="shrink-0" style={{ fontFamily: MONO, fontSize: 11, color: FAINT, width: 44, textAlign: 'right' }}>{seg.pct.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div style={{ ...CARD, padding: 24 }}>
                <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: ACCENT, marginBottom: 18 }}>P&amp;L Bulanan</p>
                {monthlyRows.length === 0 ? (
                  <div style={{ height: 160, color: FAINT, fontSize: 13 }} className="flex items-center justify-center">Belum ada transaksi jual.</div>
                ) : (
                  <div className="space-y-2 emx-scroll" style={{ maxHeight: 288, overflowY: 'auto', paddingRight: 4 }}>
                    {monthlyRows.map(([month, pnl]) => (
                      <div key={month} className="flex items-center gap-4 py-2" style={{ borderBottom: '1px solid #F2F1EC' }}>
                        <span className="shrink-0" style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: MUTED, width: 64 }}>{month}</span>
                        <div className="flex-1" style={{ background: '#F2F1EC', borderRadius: 999, height: 6 }}>
                          <div style={{ height: 6, borderRadius: 999, background: pnl >= 0 ? UP : DOWN, width: `${Math.min(100, Math.abs(pnl) / maxMonthlyAbs * 100)}%` }} />
                        </div>
                        <span className="shrink-0" style={{ fontFamily: MONO, fontSize: 12, fontWeight: 700, color: pnl >= 0 ? UP : DOWN, width: 128, textAlign: 'right' }}>
                          {pnl >= 0 ? '+' : ''}Rp {Math.round(pnl).toLocaleString('id-ID')}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <style jsx global>{`
        .emx-listrow { transition: background .14s ease; }
        .emx-listrow:hover { background: #FBFBF9; }
        .emx-link:hover span:first-child { color: ${ACCENT}; }
        .emx-input { transition: border-color .15s ease, box-shadow .15s ease; }
        .emx-input:focus { outline: none; border-color: color-mix(in oklab, ${ACCENT}, white 50%); box-shadow: 0 0 0 3px color-mix(in oklab, ${ACCENT}, transparent 86%); }
        .emx-input::placeholder { color: #A9A9A1; }
        .emx-pill { transition: background .14s ease, color .14s ease, border-color .14s ease; }
        .emx-pill:hover { background: ${ACCENT}; color: #fff !important; border-color: ${ACCENT}; }
        .emx-scroll::-webkit-scrollbar { width: 6px; }
        .emx-scroll::-webkit-scrollbar-thumb { background: #E2E1DB; border-radius: 10px; }
        ::selection { background: color-mix(in oklab, ${ACCENT}, white 70%); }
        @media (max-width: 640px) {
          .hist-col-hide { display: none; }
          .porto-total-val { font-size: 22px; }
          .porto-pct { font-size: 17px; }
          .porto-pnl { font-size: 11px; }
          .holdings-table th, .holdings-table td { padding-left: 11px; padding-right: 11px; }
          .holdings-table .hold-main { font-size: 12px; }
        }
        @media (min-width: 641px) {
          .porto-total-val { font-size: 38px; }
          .porto-pct { font-size: 22px; }
          .porto-pnl { font-size: 12.5px; }
        }
      `}</style>
    </main>
  );
}
