'use client';

import { useEffect, useState, Suspense, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, Stock, BacktestResult } from '@/lib/api';
import Link from 'next/link';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import strategyRegistry from '../../strategies_local/registry.json';

type FundSortKey = 'last_price' | 'change_pct' | 'pe_ratio' | 'pbv_ratio' | 'dividend_yield' | 'market_cap';

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
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 18,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

const TH: React.CSSProperties = { padding: '13px 18px', textAlign: 'left', fontFamily: MONO, fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: FAINT, fontWeight: 600, whiteSpace: 'nowrap' };
const THR: React.CSSProperties = { ...TH, textAlign: 'right', cursor: 'pointer', userSelect: 'none' };
const TD: React.CSSProperties = { padding: '13px 18px', fontSize: 13, verticalAlign: 'middle' };
const TDR: React.CSSProperties = { ...TD, textAlign: 'right', fontFamily: MONO };

function fmtCap(n: number | null) {
  if (n == null || n <= 0) return '-';
  if (n >= 1_000_000_000_000) return `${(n / 1_000_000_000_000).toFixed(1)}T`;
  if (n >= 1_000_000_000)     return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000)         return `${(n / 1_000_000).toFixed(0)}M`;
  return n.toLocaleString('id-ID');
}

function fmtRatio(n: number | null) {
  if (n == null || n <= 0) return '-';
  return n.toFixed(2);
}

function ScreenerInner() {
  useEffect(() => { document.title = 'Screener - EMETIQ'; }, []);
  const router = useRouter();
  const searchParams = useSearchParams();

  // ── View state is URL-driven so the browser back/forward buttons work ──
  const tabParam = searchParams.get('tab');
  const activeTab: 'teknikal' | 'fundamental' | 'backtest' =
    tabParam === 'fundamental' || tabParam === 'backtest' ? tabParam : 'teknikal';
  const selectedStratId = activeTab === 'teknikal' ? searchParams.get('strat') : null;

  const goTab = (tab: 'teknikal' | 'fundamental' | 'backtest') => router.push(`/screener?tab=${tab}`);
  const openStrat = (id: string) => router.push(`/screener?tab=teknikal&strat=${id}`);
  const backToList = () => router.push('/screener?tab=teknikal');

  // ── Teknikal states ──────────────────────────────────────
  const [matches, setMatches]                 = useState<any[]>([]);
  const [loading, setLoading]                 = useState(false);
  const [scanTime, setScanTime]               = useState<string | null>(null);
  const [sortCol, setSortCol]                 = useState<string | null>(null);
  const [sortDir, setSortDir]                 = useState<'asc' | 'desc'>('desc');

  // ── Fundamental states ───────────────────────────────────
  const [fundStocks, setFundStocks]     = useState<Stock[]>([]);
  const [fundLoading, setFundLoading]   = useState(false);
  const [peMax, setPeMax]               = useState('');
  const [pbvMax, setPbvMax]             = useState('');
  const [divYieldMin, setDivYieldMin]   = useState('');
  const [selectedSector, setSelectedSector] = useState('');
  const [fundSortKey, setFundSortKey]   = useState<FundSortKey>('market_cap');
  const [fundSortDir, setFundSortDir]   = useState<'asc' | 'desc'>('desc');
  const [fundPage, setFundPage]         = useState(30);
  const fundSentinelRef                 = useRef<HTMLDivElement>(null);

  // ── Backtest states ──────────────────────────────────────
  const [bktTicker, setBktTicker]     = useState('BBCA');
  const [bktCapital, setBktCapital]   = useState('10000000');
  const [bktResults, setBktResults]   = useState<Record<string, BacktestResult>>({});
  const [bktRunning, setBktRunning]   = useState(false);
  const [bktQuery, setBktQuery]       = useState('');
  const [bktOpen, setBktOpen]         = useState(false);
  const bktCapitalParsed = Math.max(1_000_000, parseInt(bktCapital.replace(/\D/g, '')) || 10_000_000);

  const runBacktestAll = async () => {
    setBktRunning(true);
    setBktResults({});
    const settled = await Promise.allSettled(
      strategyRegistry.map(strat =>
        api.runBacktest(bktTicker, strat.id, bktCapitalParsed).then(res => ({ id: strat.id, res }))
      )
    );
    const next: Record<string, BacktestResult> = {};
    settled.forEach(s => {
      if (s.status === 'fulfilled' && s.value.res && !('error' in (s.value.res as any))) {
        next[s.value.id] = s.value.res as BacktestResult;
      }
    });
    setBktResults(next);
    setBktRunning(false);
  };

  const bktRanked = Object.values(bktResults)
    .filter(r => r.metrics)
    .sort((a, b) => b.metrics.total_return_pct - a.metrics.total_return_pct);

  // ── Load fundamental data on tab switch ─────────────────
  useEffect(() => {
    if ((activeTab === 'fundamental' || activeTab === 'backtest') && fundStocks.length === 0) {
      setFundLoading(true);
      api.getStocks()
        .then(data => setFundStocks(data))
        .catch(() => {})
        .finally(() => setFundLoading(false));
    }
  }, [activeTab]);

  // ── Teknikal logic ───────────────────────────────────────
  const runScreener = async (id: string) => {
    setScanTime(null);
    setSortCol(null);
    setLoading(true);
    try {
      const res = await api.screenStocks(id);
      setMatches(res.matches || []);
      setScanTime(new Date().toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch {
    } finally {
      setLoading(false);
    }
  };

  function toggleSort(col: string) {
    if (sortCol === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
    else { setSortCol(col); setSortDir('desc'); }
  }

  const sortedMatches = sortCol
    ? [...matches].sort((a, b) => {
        const av = a[sortCol] as number | null;
        const bv = b[sortCol] as number | null;
        if (av == null) return 1;
        if (bv == null) return -1;
        return sortDir === 'desc' ? bv - av : av - bv;
      })
    : matches;

  useEffect(() => {
    if (selectedStratId) runScreener(selectedStratId);
  }, [selectedStratId]);

  // ── Fundamental filter + sort ────────────────────────────
  const sectors = [...new Set(fundStocks.map(s => s.sector).filter(Boolean))].sort();

  const noDataKeys: FundSortKey[] = ['pe_ratio', 'pbv_ratio', 'dividend_yield', 'market_cap'];

  const filtered = fundStocks
    .filter(s => {
      if (peMax !== '' && (s.pe_ratio == null || s.pe_ratio <= 0 || s.pe_ratio > Number(peMax))) return false;
      if (pbvMax !== '' && (s.pbv_ratio == null || s.pbv_ratio <= 0 || s.pbv_ratio > Number(pbvMax))) return false;
      if (divYieldMin !== '' && (s.dividend_yield == null || s.dividend_yield < Number(divYieldMin))) return false;
      if (selectedSector && s.sector !== selectedSector) return false;
      return true;
    })
    .sort((a, b) => {
      const av = a[fundSortKey] as number | null;
      const bv = b[fundSortKey] as number | null;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (noDataKeys.includes(fundSortKey)) {
        if (av <= 0) return 1;
        if (bv <= 0) return -1;
      }
      return fundSortDir === 'desc' ? bv - av : av - bv;
    });

  const visibleFund = filtered.slice(0, fundPage);
  const hasMoreFund = fundPage < filtered.length;

  // Reset visible page when filters or sort change
  useEffect(() => { setFundPage(30); }, [peMax, pbvMax, divYieldMin, selectedSector, fundSortKey, fundSortDir]);

  // Infinite scroll sentinel for fundamental tab
  useEffect(() => {
    const el = fundSentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) setFundPage(c => c + 30); },
      { rootMargin: '300px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMoreFund, filtered.length]);

  function toggleFundSort(key: FundSortKey) {
    if (fundSortKey === key) setFundSortDir(d => (d === 'desc' ? 'asc' : 'desc'));
    else { setFundSortKey(key); setFundSortDir('desc'); }
  }

  function SortIcon({ k }: { k: FundSortKey }) {
    if (fundSortKey !== k) return <span style={{ color: '#CDCCC4', marginLeft: 4 }}>↕</span>;
    return <span style={{ color: ACCENT, marginLeft: 4 }}>{fundSortDir === 'desc' ? '↓' : '↑'}</span>;
  }

  const activeStrat = strategyRegistry.find(s => s.id === selectedStratId);

  // ── Shared tab bar ───────────────────────────────────────
  const tabBar = () => (
    <div className="emx-scroll" style={{ display: 'flex', gap: 4, padding: 4, background: '#F2F1EC', borderRadius: 12, marginBottom: 28, width: 'fit-content', maxWidth: '100%', overflowX: 'auto' }}>
      {(['teknikal', 'fundamental', 'backtest'] as const).map(tab => {
        const active = activeTab === tab;
        const label = tab === 'teknikal' ? 'Strategi Teknikal' : tab === 'fundamental' ? 'Fundamental' : 'Backtest';
        return (
          <button
            key={tab}
            onClick={() => goTab(tab)}
            style={{ flex: 'none', whiteSpace: 'nowrap', padding: '8px 18px', borderRadius: 9, fontSize: 12.5, fontWeight: 700, border: 'none', cursor: 'pointer', transition: 'all .15s ease', background: active ? '#fff' : 'transparent', color: active ? ACCENT : MUTED, boxShadow: active ? '0 1px 4px rgba(20,20,15,.08)' : 'none' }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );

  const SCREENER_SUB = 'Saring saham berdasarkan strategi teknikal maupun fundamental.';
  const titleBlock = () => (
    <div className="mb-6">
      <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-.02em' }}>Screener</h1>
      <p style={{ marginTop: 4, fontSize: 14.5, color: MUTED }}>{SCREENER_SUB}</p>
    </div>
  );

  // ── FUNDAMENTAL VIEW ─────────────────────────────────────
  const renderFundamental = () => {
    const inputStyle: React.CSSProperties = { width: '100%', background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 12px', fontSize: 13, fontFamily: MONO, color: INK };
    const labelStyle: React.CSSProperties = { display: 'block', fontSize: 11, fontWeight: 600, color: FAINT, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 7 };
    const hasFilter = peMax || pbvMax || divYieldMin || selectedSector;

    return (
      <>
        {titleBlock()}
        {tabBar()}

        {/* Filter panel */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5" style={{ ...CARD, padding: 20 }}>
          <div>
            <label style={labelStyle}>PE Ratio Maks</label>
            <input type="number" min="0" placeholder="cth: 20" value={peMax} onChange={e => setPeMax(e.target.value)} className="emx-input" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>PBV Ratio Maks</label>
            <input type="number" min="0" placeholder="cth: 3" value={pbvMax} onChange={e => setPbvMax(e.target.value)} className="emx-input" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Div. Yield Min (%)</label>
            <input type="number" min="0" step="0.1" placeholder="cth: 3" value={divYieldMin} onChange={e => setDivYieldMin(e.target.value)} className="emx-input" style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>Sektor</label>
            <select value={selectedSector} onChange={e => setSelectedSector(e.target.value)} className="emx-input" style={inputStyle}>
              <option value="">Semua Sektor</option>
              {sectors.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
        </div>

        {/* Results count + reset */}
        <div className="flex items-center justify-between mb-3">
          <span style={{ fontFamily: MONO, fontSize: 12, color: ACCENT, fontWeight: 600 }}>
            {filtered.length} saham ditemukan
          </span>
          {hasFilter && (
            <button
              onClick={() => { setPeMax(''); setPbvMax(''); setDivYieldMin(''); setSelectedSector(''); }}
              style={{ fontFamily: MONO, fontSize: 12, color: FAINT, background: 'none', border: 'none', cursor: 'pointer' }}
            >
              Reset filter ✕
            </button>
          )}
        </div>

        {/* Table */}
        <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
          {fundLoading ? (
            <div className="flex items-center justify-center" style={{ padding: '96px 0' }}>
              <div style={{ width: 28, height: 28, border: `2px solid ${ACCENT}`, borderTopColor: 'transparent', borderRadius: '50%' }} className="animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto emx-scroll">
              <table className="min-w-full" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${HAIR}`, background: '#FBFBF9' }}>
                    <th style={TH}>Saham</th>
                    <th style={TH} className="fund-col-hide">Sektor</th>
                    <th style={THR} onClick={() => toggleFundSort('last_price')}>Harga <SortIcon k="last_price" /></th>
                    <th style={THR} onClick={() => toggleFundSort('change_pct')}>Chg% <SortIcon k="change_pct" /></th>
                    <th style={THR} className="fund-col-hide" onClick={() => toggleFundSort('pe_ratio')}>PE <SortIcon k="pe_ratio" /></th>
                    <th style={THR} className="fund-col-hide" onClick={() => toggleFundSort('pbv_ratio')}>PBV <SortIcon k="pbv_ratio" /></th>
                    <th style={THR} onClick={() => toggleFundSort('dividend_yield')}>Div. Yield <SortIcon k="dividend_yield" /></th>
                    <th style={THR} onClick={() => toggleFundSort('market_cap')}>Mkt Cap <SortIcon k="market_cap" /></th>
                    <th style={{ ...TH, textAlign: 'right' }} />
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr><td colSpan={9} style={{ padding: '72px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>Tidak ada saham yang memenuhi kriteria filter.</td></tr>
                  ) : (
                    visibleFund.map((s, i) => {
                      const up = (s.change_pct ?? 0) >= 0;
                      return (
                        <tr key={s.ticker} className="emx-listrow" style={{ borderBottom: (i < visibleFund.length - 1 || hasMoreFund) ? '1px solid #F2F1EC' : 'none' }}>
                          <td style={TD}>
                            <span style={{ fontWeight: 700, fontSize: 14, display: 'block' }}>{s.ticker}</span>
                            <span style={{ fontFamily: MONO, fontSize: 10.5, color: FAINT, display: 'block', marginTop: 1 }} className="truncate w-36">{s.name}</span>
                          </td>
                          <td className="fund-col-hide" style={{ ...TD, fontSize: 11.5, color: MUTED, whiteSpace: 'nowrap' }}>{s.sector || '-'}</td>
                          <td style={{ ...TDR, fontWeight: 600 }}>{s.last_price?.toLocaleString('id-ID') ?? '-'}</td>
                          <td style={{ ...TDR, fontWeight: 600, color: up ? UP : DOWN }}>{s.change_pct != null ? `${up ? '+' : ''}${s.change_pct.toFixed(2)}%` : '-'}</td>
                          <td className="fund-col-hide" style={{ ...TDR, color: MUTED }}>{fmtRatio(s.pe_ratio)}</td>
                          <td className="fund-col-hide" style={{ ...TDR, color: MUTED }}>{fmtRatio(s.pbv_ratio)}</td>
                          <td style={{ ...TDR, fontWeight: 600, color: s.dividend_yield && s.dividend_yield > 0 ? ACCENT : MUTED }}>{s.dividend_yield != null && s.dividend_yield > 0 ? `${s.dividend_yield.toFixed(2)}%` : '-'}</td>
                          <td style={{ ...TDR, color: MUTED }}>{fmtCap(s.market_cap)}</td>
                          <td style={{ ...TD, textAlign: 'right' }}>
                            <Link href={`/stocks/${s.ticker}`} className="emx-pill" style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: ACCENT, border: `1px solid ${HAIR}`, padding: '6px 12px', borderRadius: 8, textDecoration: 'none', whiteSpace: 'nowrap' }}>Analisa</Link>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {hasMoreFund && <div ref={fundSentinelRef} style={{ height: 1 }} />}
      </>
    );
  };

  // ── TEKNIKAL: OVERVIEW (card → list) ─────────────────────
  const renderOverview = () => (
    <>
      {titleBlock()}
      {tabBar()}

      <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
        {strategyRegistry.map((strat, i) => (
          <button
            key={strat.id}
            onClick={() => openStrat(strat.id)}
            className="emx-listrow"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, width: '100%', textAlign: 'left', padding: '17px 20px', border: 'none', borderBottom: i < strategyRegistry.length - 1 ? '1px solid #F2F1EC' : 'none', background: 'transparent', cursor: 'pointer' }}
          >
            <div style={{ minWidth: 0 }}>
              <div className="flex items-center gap-2.5">
                <span style={{ fontWeight: 700, fontSize: 15.5 }}>{strat.name}</span>
                <span style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 88%)`, padding: '2px 8px', borderRadius: 999, whiteSpace: 'nowrap' }}>{strat.indicator}</span>
              </div>
              <p style={{ fontSize: 13, color: '#67675F', marginTop: 4, maxWidth: 680 }} className="line-clamp-2">{strat.description}</p>
            </div>
            <span style={{ flex: 'none', background: ACCENT, color: '#fff', fontWeight: 700, fontSize: 13, padding: '8px 18px', borderRadius: 999, boxShadow: `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 66%)` }}>Scan</span>
          </button>
        ))}
      </div>
    </>
  );

  // ── TEKNIKAL: STRATEGY DETAIL ────────────────────────────
  const renderDetail = () => (
    <>
      <button
        onClick={backToList}
        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 36, height: 36, borderRadius: 10, border: `1px solid ${HAIR}`, background: '#fff', cursor: 'pointer', fontSize: 18, color: INK, lineHeight: 1, marginBottom: 14 }}
        title="Kembali ke daftar strategi"
      >‹</button>
      <div className="mb-6">
        <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em', color: ACCENT }}>{activeStrat?.name}</h1>
        <p style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT, marginTop: 4 }}>
          {matches.length} saham cocok{scanTime && <span> · Scan {scanTime}</span>}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-1">
          <div style={{ ...CARD, padding: 22 }}>
            <h3 style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.12em', textTransform: 'uppercase', color: ACCENT, marginBottom: 16 }}>Logika Eksekusi</h3>
            <div className="space-y-3">
              {activeStrat?.rules?.map((rule: string, i: number) => (
                <div key={i} className="flex gap-3 items-start">
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: rule.startsWith('ENTRY') ? UP : '#CDCCC4', marginTop: 6, flex: 'none' }} />
                  <span style={{ fontFamily: MONO, fontSize: 11.5, lineHeight: 1.5, color: rule.startsWith('ENTRY') ? UP : MUTED }}>{rule}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-3">
          <div style={{ ...CARD, padding: 0, overflow: 'hidden', position: 'relative' }}>
            {loading && (
              <div style={{ position: 'absolute', inset: 0, background: 'rgba(252,252,251,.7)', zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(2px)' }}>
                <div className="flex flex-col items-center gap-3">
                  <div style={{ width: 28, height: 28, border: `2px solid ${ACCENT}`, borderTopColor: 'transparent', borderRadius: '50%' }} className="animate-spin" />
                  <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: ACCENT }}>Memindai 400+ saham...</p>
                </div>
              </div>
            )}
            <div className="overflow-x-auto">
              <table className="min-w-full" style={{ borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: `1px solid ${HAIR}`, background: '#FBFBF9' }}>
                    <th style={TH}>Instrumen</th>
                    {activeStrat?.display_columns.map(col => (
                      <th key={col} style={{ ...TH, cursor: 'pointer', userSelect: 'none' }} onClick={() => toggleSort(col)}>
                        {col.replace('_', ' ')}
                        {sortCol === col ? (sortDir === 'desc' ? ' ↓' : ' ↑') : <span style={{ color: '#CDCCC4', marginLeft: 4 }}>↕</span>}
                      </th>
                    ))}
                    <th style={{ ...TH, textAlign: 'right' }}>Aksi</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedMatches.length === 0 ? (
                    <tr><td colSpan={10} style={{ padding: '80px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>Belum ada saham yang memenuhi kriteria ini. Pasar sedang netral.</td></tr>
                  ) : (
                    sortedMatches.map((m, i) => (
                      <tr key={m.ticker} className="emx-listrow" style={{ borderBottom: i < sortedMatches.length - 1 ? '1px solid #F2F1EC' : 'none' }}>
                        <td style={{ ...TD, whiteSpace: 'nowrap' }}>
                          <span style={{ fontWeight: 700, fontSize: 14.5, display: 'block' }}>{m.ticker}</span>
                          <span style={{ fontFamily: MONO, fontSize: 10, color: FAINT, display: 'block', marginTop: 1 }} className="truncate w-32">{m.name}</span>
                        </td>
                        {activeStrat?.display_columns.map(col => (
                          <td key={col} style={{ ...TD, whiteSpace: 'nowrap', fontFamily: MONO }}>
                            <span style={{ fontWeight: 600, color: typeof m[col] === 'number' && m[col] > 0 ? ACCENT : typeof m[col] === 'number' && m[col] < 0 ? DOWN : MUTED }}>
                              {typeof m[col] === 'number' ? m[col].toLocaleString('id-ID', { maximumFractionDigits: 2 }) : m[col]}
                              {col.includes('Dist') || col.includes('Surge') ? '%' : ''}
                            </span>
                          </td>
                        ))}
                        <td style={{ ...TD, textAlign: 'right' }}>
                          <Link href={`/stocks/${m.ticker}`} className="emx-pill" style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, color: ACCENT, border: `1px solid ${HAIR}`, padding: '6px 12px', borderRadius: 8, textDecoration: 'none', whiteSpace: 'nowrap' }}>Analisa</Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </>
  );

  // ── BACKTEST VIEW (ranking only) ─────────────────────────
  const renderBacktest = () => {
    const inputStyle: React.CSSProperties = { background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 12px', fontSize: 13, fontFamily: MONO, color: INK };
    const labelStyle: React.CSSProperties = { display: 'block', fontSize: 11, fontWeight: 600, color: FAINT, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 7 };

    const stockList = fundStocks.filter(s => s.ticker !== '^JKSE');
    const q = bktQuery.trim().toLowerCase();
    const bktOptions = (q ? stockList.filter(s => s.ticker.toLowerCase().includes(q) || s.name.toLowerCase().includes(q)) : stockList).slice(0, 60);

    return (
      <>
        {titleBlock()}
        {tabBar()}

        {/* Asset picker */}
        <div style={{ ...CARD, padding: 16, marginBottom: 20 }} className="flex flex-wrap items-end gap-4">
          <div style={{ position: 'relative' }}>
            <label style={labelStyle}>Aset</label>
            <input
              value={bktOpen ? bktQuery : bktTicker}
              onFocus={() => { setBktOpen(true); setBktQuery(''); }}
              onBlur={() => setTimeout(() => setBktOpen(false), 120)}
              onChange={e => { setBktQuery(e.target.value); setBktOpen(true); }}
              placeholder="Cari kode / nama..."
              className="emx-input"
              style={{ ...inputStyle, width: 230, fontWeight: 700, color: ACCENT }}
            />
            {bktOpen && (
              <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, marginTop: 6, zIndex: 30, background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 12, boxShadow: '0 18px 40px -20px rgba(20,20,15,.3)', maxHeight: 264, overflowY: 'auto' }} className="emx-scroll">
                {bktOptions.length === 0 ? (
                  <div style={{ padding: '14px', fontSize: 12.5, color: FAINT }}>{fundLoading ? 'Memuat daftar saham...' : 'Tidak ada saham cocok.'}</div>
                ) : bktOptions.map(s => (
                  <button
                    key={s.ticker}
                    onMouseDown={() => { setBktTicker(s.ticker); setBktQuery(''); setBktOpen(false); setBktResults({}); }}
                    className="emx-listrow"
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, width: '100%', textAlign: 'left', padding: '9px 13px', border: 'none', background: s.ticker === bktTicker ? `color-mix(in oklab, ${ACCENT}, white 90%)` : 'transparent', cursor: 'pointer' }}
                  >
                    <span style={{ fontWeight: 700, fontSize: 13, flex: 'none' }}>{s.ticker}</span>
                    <span style={{ fontFamily: MONO, fontSize: 11, color: FAINT, minWidth: 0 }} className="truncate">{s.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <div>
            <label style={labelStyle}>Modal Simulasi</label>
            <div className="emx-inputwrap" style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 12px', width: 180 }}>
              <span style={{ fontFamily: MONO, fontSize: 12, color: FAINT, flex: 'none' }}>Rp</span>
              <input
                inputMode="numeric"
                value={bktCapital ? Number(bktCapital).toLocaleString('id-ID') : ''}
                onChange={e => { setBktCapital(e.target.value.replace(/\D/g, '')); setBktResults({}); }}
                placeholder="10.000.000"
                style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', fontFamily: MONO, fontSize: 13, color: INK }}
              />
            </div>
          </div>
          <button
            onClick={runBacktestAll}
            disabled={bktRunning}
            className="emx-btn"
            style={{ marginLeft: 'auto', background: ACCENT, color: '#fff', fontWeight: 700, fontSize: 13, padding: '11px 22px', borderRadius: 11, border: 'none', cursor: 'pointer', opacity: bktRunning ? 0.6 : 1, boxShadow: `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 64%)` }}
          >
            {bktRunning ? 'Menjalankan...' : 'Run Backtest'}
          </button>
        </div>

        {/* Body: ranking after run, strategy list before */}
        <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
          {bktRunning ? (
            <div className="flex flex-col items-center justify-center gap-3" style={{ padding: '72px 0' }}>
              <div style={{ width: 28, height: 28, border: `2px solid ${ACCENT}`, borderTopColor: 'transparent', borderRadius: '50%' }} className="animate-spin" />
              <p style={{ fontFamily: MONO, fontSize: 11.5, fontWeight: 600, color: ACCENT }}>Menjalankan backtest semua strategi untuk {bktTicker}...</p>
            </div>
          ) : bktRanked.length > 0 ? (
            bktRanked.map((r, idx) => {
              const info = strategyRegistry.find(s => s.id === r.strategy_id);
              const ret = r.metrics.total_return_pct;
              const up = ret >= 0;
              return (
                <div
                  key={r.strategy_id}
                  className="emx-listrow"
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '15px 20px', borderBottom: idx < bktRanked.length - 1 ? '1px solid #F2F1EC' : 'none', background: idx === 0 ? `color-mix(in oklab, ${ACCENT}, white 93%)` : 'transparent' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                    <span style={{ fontFamily: MONO, fontSize: 13, fontWeight: 700, color: idx === 0 ? ACCENT : FAINT, width: 20, flex: 'none' }}>{idx + 1}</span>
                    <div style={{ minWidth: 0 }}>
                      <div className="flex items-center gap-2">
                        <span style={{ fontWeight: 700, fontSize: 15 }}>{info?.name ?? r.strategy_id}</span>
                        {idx === 0 && <span style={{ fontFamily: MONO, fontSize: 9, fontWeight: 700, color: '#fff', background: ACCENT, padding: '2px 7px', borderRadius: 999 }}>BEST</span>}
                      </div>
                      <div style={{ fontFamily: MONO, fontSize: 11, color: FAINT, marginTop: 3 }}>
                        WR {r.metrics.win_rate}% · DD -{r.metrics.max_drawdown_pct}% · {r.metrics.total_trades} trade · Rp {(r.metrics.final_value / 1_000_000).toFixed(1)}M
                      </div>
                    </div>
                  </div>
                  <span style={{ fontFamily: MONO, fontSize: 18, fontWeight: 700, color: up ? UP : DOWN, flex: 'none' }}>{up ? '+' : ''}{ret}%</span>
                </div>
              );
            })
          ) : (
            strategyRegistry.map((strat, i) => (
              <div key={strat.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '15px 20px', borderBottom: i < strategyRegistry.length - 1 ? '1px solid #F2F1EC' : 'none' }}>
                <div style={{ minWidth: 0 }}>
                  <div className="flex items-center gap-2.5">
                    <span style={{ fontWeight: 700, fontSize: 15 }}>{strat.name}</span>
                    <span style={{ fontFamily: MONO, fontSize: 10, fontWeight: 600, color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 88%)`, padding: '2px 8px', borderRadius: 999, whiteSpace: 'nowrap' }}>{strat.indicator}</span>
                  </div>
                  <p style={{ fontSize: 13, color: '#67675F', marginTop: 4, maxWidth: 680 }} className="line-clamp-2">{strat.description}</p>
                </div>
                <span style={{ fontFamily: MONO, fontSize: 11, color: FAINT, flex: 'none' }}>Menunggu</span>
              </div>
            ))
          )}
        </div>
      </>
    );
  };

  const inner = activeTab === 'fundamental'
    ? renderFundamental()
    : activeTab === 'backtest'
      ? renderBacktest()
      : selectedStratId
        ? renderDetail()
        : renderOverview();

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      {/* Fonts — React 19 hoists these into <head> */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav active="screener" />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 24px 80px' }}>
        {inner}
      </div>

      <style jsx global>{`
        .emx-listrow {
          transition: background .14s ease;
        }
        .emx-listrow:hover {
          background: #FBFBF9;
        }
        .emx-input {
          transition: border-color .15s ease, box-shadow .15s ease;
        }
        .emx-input:focus {
          outline: none;
          border-color: color-mix(in oklab, ${ACCENT}, white 50%);
          box-shadow: 0 0 0 3px color-mix(in oklab, ${ACCENT}, transparent 86%);
        }
        .emx-input::placeholder {
          color: #A9A9A1;
        }
        .emx-pill {
          transition: background .14s ease, color .14s ease, border-color .14s ease;
        }
        .emx-pill:hover {
          background: ${ACCENT};
          color: #fff !important;
          border-color: ${ACCENT};
        }
        .emx-btn {
          transition: transform .15s ease, filter .15s ease;
        }
        .emx-btn:hover {
          transform: translateY(-1px);
          filter: brightness(1.03);
        }
        .emx-inputwrap {
          transition: border-color .15s ease, box-shadow .15s ease;
        }
        .emx-inputwrap:focus-within {
          border-color: color-mix(in oklab, ${ACCENT}, white 50%);
          box-shadow: 0 0 0 3px color-mix(in oklab, ${ACCENT}, transparent 86%);
        }
        .emx-scroll::-webkit-scrollbar {
          width: 6px;
        }
        .emx-scroll::-webkit-scrollbar-thumb {
          background: #E2E1DB;
          border-radius: 10px;
        }
        ::selection {
          background: color-mix(in oklab, ${ACCENT}, white 70%);
        }
        @media (max-width: 640px) {
          .fund-col-hide { display: none; }
        }
      `}</style>
    </main>
  );
}

export default function ScreenerPage() {
  return (
    <RequireAuth>
      <Suspense fallback={<div style={{ minHeight: '100vh', background: BG }} />}>
        <ScreenerInner />
      </Suspense>
    </RequireAuth>
  );
}
