'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, Stock, OHLCV } from '@/lib/api';
import { createChartSync } from '@/lib/chartSync';
import dynamic from 'next/dynamic';
import EmetiqNav from '@/components/EmetiqNav';
import { useToast } from '@/components/Toast';

const StockChart = dynamic(() => import("@/components/StockChart"), { ssr: false });
const IndicatorSubChart = dynamic(() => import("@/components/IndicatorSubChart"), { ssr: false });

type SubPanelType = 'rsi' | 'macd' | 'stoch' | 'volume';
type Timeframe = '3M' | '6M' | '1Y' | 'ALL';
type SortKey = 'name' | 'price' | 'change';

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

interface Indicators {
  MA_20: number | null; MA_50: number | null; MA_200: number | null;
  EMA_12: number | null; EMA_26: number | null; RSI_14: number | null;
  MACD_LINE: number | null; MACD_SIGNAL: number | null; MACD_HIST: number | null;
  BB_UPPER: number | null; BB_MIDDLE: number | null; BB_LOWER: number | null;
  ATR_14: number | null; STOCH_K: number | null; STOCH_D: number | null;
  VOLUME_MA_20: number | null;
  [key: string]: number | null;
}

function rsiColor(v: number | null) {
  if (v == null) return MUTED;
  if (v < 30) return UP;
  if (v > 70) return DOWN;
  return '#2563EB';
}

function fmt(v: number | null) {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const ticker = params?.ticker as string;

  useEffect(() => {
    if (ticker) document.title = `${ticker} — EMETIQ`;
  }, [ticker]);

  const { toast } = useToast();

  const [stocks, setStocks] = useState<Stock[]>([]);
  const [ohlcv, setOhlcv] = useState<OHLCV[]>([]);
  const [indicators, setIndicators] = useState<Indicators | null>(null);
  const [portfolio, setPortfolio] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  // ML state
  type MlResult = Awaited<ReturnType<typeof api.getMlPrediction>>;
  type MlStatus = Awaited<ReturnType<typeof api.getMlStatus>>;
  const [mlResult, setMlResult] = useState<MlResult | null>(null);
  const [mlStatus, setMlStatus] = useState<MlStatus | null>(null);
  const [mlLoading, setMlLoading] = useState(false);

  // Order state
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY');
  const [tradeQty, setTradeQty] = useState(1);
  const [isTrading, setIsTrading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Watchlist state
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set());

  // Sidebar sort — mirrors the Market page (Nama / Harga / %)
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // Order note (strategy fixed to manual since the picker was removed)
  const selectedStrategy = 'manual-intuition';
  const [reasoning, setReasoning] = useState('');

  // Shared time scale sync between price chart and indicator sub-panels
  const chartSync = useRef(createChartSync());

  // Chart visibility state
  const [showMA20, setShowMA20] = useState(true);
  const [showMA50, setShowMA50] = useState(true);
  const [showMA200, setShowMA200] = useState(false);
  const [showEMA12, setShowEMA12] = useState(false);
  const [showEMA26, setShowEMA26] = useState(false);
  const [showBB, setShowBB] = useState(false);
  const [activeSubPanel, setActiveSubPanel] = useState<SubPanelType | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>('3M');

  useEffect(() => {
    api.getStocks().then(setStocks);
  }, []);

  useEffect(() => {
    const saved = localStorage.getItem('watchlist');
    if (saved) { try { setWatchlist(new Set(JSON.parse(saved))); } catch {} }
  }, []);

  const toggleWatchlist = (e: React.MouseEvent, tickerSymbol: string) => {
    e.preventDefault();
    e.stopPropagation();
    setWatchlist(prev => {
      const next = new Set(prev);
      next.has(tickerSymbol) ? next.delete(tickerSymbol) : next.add(tickerSymbol);
      localStorage.setItem('watchlist', JSON.stringify([...next]));
      return next;
    });
  };

  const fetchData = useCallback(async () => {
    if (!ticker) return;
    setLoading(true);
    try {
      const [ohlcvData, indData, portfolioData, status] = await Promise.all([
        api.getOHLCV(ticker),
        api.getIndicators(ticker),
        api.getPortfolio(),
        api.getMlStatus(ticker),
      ]);
      setOhlcv(ohlcvData.data || []);
      setIndicators(indData.indicators || null);
      setPortfolio(portfolioData.USER.assets.find((p: any) => p.ticker === ticker) || null);
      setMlStatus(status);
      if (status.trained) {
        setMlLoading(true);
        api.getMlPrediction(ticker).then(setMlResult).finally(() => setMlLoading(false));
      }
    } catch (err) {
      toast('Gagal memuat data saham. Periksa koneksi backend.', 'error');
    } finally {
      setLoading(false);
    }
  }, [ticker]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTrade = async () => {
    if (!ticker) return;
    setIsTrading(true);
    try {
      const res = await api.executeTrade(ticker, orderSide, tradeQty, undefined, 'MANUAL', reasoning, selectedStrategy);
      if (res.status === 'ok') {
        toast(`Order ${orderSide} berhasil — ${tradeQty} lot ${ticker}`, 'success');
        setReasoning('');
        await fetchData();
      } else {
        toast(res.detail || "Gagal mengeksekusi order", 'error');
      }
    } catch (err) {
      toast("Gagal menghubungi server", 'error');
    } finally {
      setIsTrading(false);
    }
  };

  const latestPrice = ohlcv[ohlcv.length - 1]?.close || 0;
  const totalValue = latestPrice * tradeQty * 100;

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir(key === 'name' ? 'asc' : 'desc'); }
  };

  const filteredStocks = stocks
    .filter(s => s.ticker !== '^JKSE' && (s.ticker.toLowerCase().includes(searchTerm.toLowerCase()) || s.name.toLowerCase().includes(searchTerm.toLowerCase())))
    .sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'name') cmp = a.ticker.localeCompare(b.ticker);
      else if (sortKey === 'price') cmp = (a.last_price ?? 0) - (b.last_price ?? 0);
      else cmp = (a.change_pct ?? 0) - (b.change_pct ?? 0);
      return sortDir === 'asc' ? cmp : -cmp;
    });

  const currentStockInfo = stocks.find(s => s.ticker === ticker);
  const priceUp = (currentStockInfo?.change_pct ?? 0) >= 0;

  const displayedOhlcv = (() => {
    if (timeframe === 'ALL' || ohlcv.length === 0) return ohlcv;
    const months = { '3M': 3, '6M': 6, '1Y': 12 }[timeframe];
    const cutoff = new Date();
    cutoff.setMonth(cutoff.getMonth() - months);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return ohlcv.filter(d => d.date >= cutoffStr);
  })();

  // ── Price overlay toggles (dot color = the line color drawn on the chart) ──
  const overlayToggles = [
    { label: 'MA 20',  on: showMA20,  set: () => setShowMA20(v => !v),   dot: '#f59e0b' },
    { label: 'MA 50',  on: showMA50,  set: () => setShowMA50(v => !v),   dot: '#a78bfa' },
    { label: 'MA 200', on: showMA200, set: () => setShowMA200(v => !v),  dot: '#f97316' },
    { label: 'EMA 12', on: showEMA12, set: () => setShowEMA12(v => !v),  dot: '#38bdf8' },
    { label: 'EMA 26', on: showEMA26, set: () => setShowEMA26(v => !v),  dot: '#22d3ee' },
    { label: 'BB',     on: showBB,    set: () => setShowBB(v => !v),     dot: '#ec4899' },
  ];

  const subPanelToggles: { label: string; panel: SubPanelType }[] = [
    { label: 'RSI', panel: 'rsi' },
    { label: 'MACD', panel: 'macd' },
    { label: 'STOCH', panel: 'stoch' },
    { label: 'VOL', panel: 'volume' },
  ];

  // ── Technical indicators grouped by family for compact reading ──
  const indGroups: { title: string; items: { label: string; value: number | null; color?: string; tag?: string | null }[] }[] = [
    {
      title: 'Moving Average',
      items: [
        { label: 'MA 20', value: indicators?.MA_20 ?? null },
        { label: 'MA 50', value: indicators?.MA_50 ?? null },
        { label: 'MA 200', value: indicators?.MA_200 ?? null },
      ],
    },
    {
      title: 'Exponential MA',
      items: [
        { label: 'EMA 12', value: indicators?.EMA_12 ?? null },
        { label: 'EMA 26', value: indicators?.EMA_26 ?? null },
      ],
    },
    {
      title: 'MACD',
      items: [
        { label: 'Line', value: indicators?.MACD_LINE ?? null },
        { label: 'Signal', value: indicators?.MACD_SIGNAL ?? null },
        { label: 'Histogram', value: indicators?.MACD_HIST ?? null },
      ],
    },
    {
      title: 'Bollinger Bands',
      items: [
        { label: 'Upper', value: indicators?.BB_UPPER ?? null },
        { label: 'Middle', value: indicators?.BB_MIDDLE ?? null },
        { label: 'Lower', value: indicators?.BB_LOWER ?? null },
      ],
    },
    {
      title: 'Oscillator',
      items: [
        {
          label: 'RSI 14',
          value: indicators?.RSI_14 ?? null,
          color: rsiColor(indicators?.RSI_14 ?? null),
          tag: indicators?.RSI_14 != null ? (indicators.RSI_14 < 30 ? 'Oversold' : indicators.RSI_14 > 70 ? 'Overbought' : 'Neutral') : null,
        },
        { label: 'Stoch %K', value: indicators?.STOCH_K ?? null },
        { label: 'Stoch %D', value: indicators?.STOCH_D ?? null },
      ],
    },
    {
      title: 'Volatility',
      items: [
        { label: 'ATR 14', value: indicators?.ATR_14 ?? null },
      ],
    },
  ];

  // Reusable pill style
  const pill = (active: boolean): React.CSSProperties => ({
    display: 'inline-flex', alignItems: 'center', gap: 6,
    fontSize: 11.5, fontWeight: 700, padding: '6px 12px', borderRadius: 999,
    cursor: 'pointer', transition: 'all .15s ease', whiteSpace: 'nowrap',
    border: `1px solid ${active ? ACCENT : HAIR}`,
    background: active ? `color-mix(in oklab, ${ACCENT}, white 88%)` : '#fff',
    color: active ? ACCENT : MUTED,
  });

  const labelStyle: React.CSSProperties = { display: 'block', fontSize: 10.5, fontWeight: 600, color: FAINT, textTransform: 'uppercase', letterSpacing: '.08em', marginBottom: 6 };

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      {/* Fonts — React 19 hoists these into <head> */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav active="market" />

      <div style={{ maxWidth: 1320, margin: '0 auto', padding: '24px 20px 80px' }}>
        {/* ── Stock header ───────────────────────────────────── */}
        <div style={{ ...CARD, padding: 22, marginBottom: 20 }} className="flex flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3 md:gap-5 min-w-0">
            <button
              onClick={() => router.back()}
              title="Kembali"
              style={{ flex: 'none', width: 38, height: 38, borderRadius: 11, border: `1px solid ${HAIR}`, background: '#fff', cursor: 'pointer', fontSize: 19, color: INK, lineHeight: 1 }}
            >‹</button>
            <div>
              <div className="flex items-center gap-3">
                <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1 }}>{ticker}</h1>
                <button
                  onClick={(e) => toggleWatchlist(e, ticker)}
                  title={watchlist.has(ticker) ? 'Hapus dari watchlist' : 'Tambah ke watchlist'}
                  style={{ fontSize: 18, lineHeight: 1, background: 'none', border: 'none', cursor: 'pointer', color: watchlist.has(ticker) ? ACCENT : '#D6D5CE' }}
                >★</button>
              </div>
              <p className="truncate" style={{ fontFamily: MONO, fontSize: 11, color: FAINT, textTransform: 'uppercase', letterSpacing: '.14em', marginTop: 5 }}>{currentStockInfo?.sector || 'Sektor tidak diketahui'}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-3 flex-wrap justify-end" style={{ flex: 'none' }}>
            <p style={{ fontFamily: MONO, fontSize: 26, fontWeight: 600, letterSpacing: '-.01em' }}>Rp {latestPrice.toLocaleString('id-ID')}</p>
            {currentStockInfo?.change_pct != null && (
              <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: priceUp ? UP : DOWN, background: priceUp ? UP_BG : DOWN_BG, padding: '3px 9px', borderRadius: 7, display: 'inline-block' }}>
                {priceUp ? '▲' : '▼'} {Math.abs(currentStockInfo.change_pct).toFixed(2)}%
              </span>
            )}
          </div>
        </div>

        {/* Mobile stock selector (sidebar is hidden on small screens) */}
        <div className="term-mobile-select" style={{ marginBottom: 18 }}>
          <select
            value={ticker}
            onChange={e => router.push(`/stocks/${e.target.value}`)}
            className="emx-input"
            style={{ width: '100%', background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 12, padding: '11px 14px', fontSize: 14, color: INK, fontFamily: SANS }}
          >
            {filteredStocks.map(s => (
              <option key={s.ticker} value={s.ticker}>{s.ticker} — {s.name || ''}</option>
            ))}
          </select>
        </div>

        {/* ── 3-column workspace ─────────────────────────────── */}
        <div className="term-grid">
          {/* LEFT: Market watch */}
          <aside className="term-side">
            <div style={{ ...CARD, padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', maxHeight: 'calc(100vh - 108px)' }}>
              <div style={{ padding: 14, borderBottom: `1px solid ${HAIR}` }}>
                <input
                  type="text"
                  placeholder="Cari saham..."
                  className="emx-input"
                  style={{ width: '100%', background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 12px', fontSize: 13, color: INK, fontFamily: SANS }}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
                <div className="flex items-center gap-1.5 mt-2.5">
                  <span style={{ fontSize: 11, fontWeight: 600, color: FAINT, marginRight: 2 }}>Urut</span>
                  {([['name', 'Nama'], ['price', 'Harga'], ['change', '%']] as const).map(([key, label]) => {
                    const active = sortKey === key;
                    return (
                      <button key={key} onClick={() => toggleSort(key)} style={{ ...pill(active), padding: '5px 9px', fontSize: 11 }}>
                        {label}{active && <span style={{ fontSize: 8 }}>{sortDir === 'asc' ? '▲' : '▼'}</span>}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="emx-scroll" style={{ overflowY: 'auto', flex: 1 }}>
                {filteredStocks.map(stock => {
                  const active = ticker === stock.ticker;
                  const up = stock.change_pct != null && stock.change_pct >= 0;
                  return (
                    <div
                      key={stock.ticker}
                      onClick={() => router.push(`/stocks/${stock.ticker}`)}
                      role="button"
                      tabIndex={0}
                      className="emx-listrow"
                      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '11px 14px', cursor: 'pointer', borderBottom: '1px solid #F4F3EF', borderLeft: `3px solid ${active ? ACCENT : 'transparent'}`, background: active ? `color-mix(in oklab, ${ACCENT}, white 92%)` : 'transparent' }}
                    >
                      <div className="min-w-0">
                        <p style={{ fontWeight: 700, fontSize: 13, color: active ? ACCENT : INK }}>{stock.ticker}</p>
                        <p style={{ fontFamily: MONO, fontSize: 9.5, color: FAINT }} className="truncate w-24">{stock.name}</p>
                      </div>
                      <button
                        onClick={(e) => toggleWatchlist(e, stock.ticker)}
                        style={{ fontSize: 12, lineHeight: 1, background: 'none', border: 'none', cursor: 'pointer', color: watchlist.has(stock.ticker) ? ACCENT : '#D6D5CE', flex: 'none' }}
                      >★</button>
                      <div style={{ textAlign: 'right', flex: 'none' }}>
                        <p style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600 }}>{stock.last_price?.toLocaleString('id-ID') ?? '-'}</p>
                        {stock.change_pct != null && (
                          <p style={{ fontFamily: MONO, fontSize: 9.5, fontWeight: 600, color: up ? UP : DOWN }}>{up ? '+' : ''}{stock.change_pct.toFixed(2)}%</p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </aside>

          {/* CENTER (top): chart toolbar + chart */}
          <div className="term-main-top" style={{ minWidth: 0 }}>
            {/* Chart toolbar */}
            <div className="flex flex-wrap items-center gap-2 mb-4">
              {overlayToggles.map(t => (
                <button key={t.label} onClick={t.set} style={pill(t.on)}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: t.dot, flex: 'none', opacity: t.on ? 1 : .45 }} />
                  {t.label}
                </button>
              ))}
              <span style={{ width: 1, height: 22, background: HAIR, margin: '0 4px' }} />
              {subPanelToggles.map(t => (
                <button key={t.panel} onClick={() => setActiveSubPanel(p => p === t.panel ? null : t.panel)} style={pill(activeSubPanel === t.panel)}>
                  {t.label}
                </button>
              ))}
              <span style={{ width: 1, height: 22, background: HAIR, margin: '0 4px' }} />
              {(['3M', '6M', '1Y', 'ALL'] as Timeframe[]).map(tf => (
                <button key={tf} onClick={() => setTimeframe(tf)} style={pill(timeframe === tf)}>{tf}</button>
              ))}
            </div>

            {/* Chart card */}
            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              {loading ? (
                <div style={{ height: 460, fontFamily: MONO, color: ACCENT }} className="flex items-center justify-center text-xs tracking-[0.3em] uppercase animate-pulse">
                  Memuat data pasar...
                </div>
              ) : (
                <>
                  <StockChart
                    data={displayedOhlcv}
                    indicators={indicators ?? {}}
                    showMA20={showMA20}
                    showMA50={showMA50}
                    showMA200={showMA200}
                    showEMA12={showEMA12}
                    showEMA26={showEMA26}
                    showBB={showBB}
                    height={460}
                    light
                    sync={chartSync.current}
                  />
                  {activeSubPanel && ohlcv.length > 0 && (
                    <IndicatorSubChart data={displayedOhlcv} type={activeSubPanel} light sync={chartSync.current} />
                  )}
                </>
              )}
            </div>
          </div>

          {/* CENTER (bottom): ML + indicators */}
          <div className="term-main-bottom" style={{ minWidth: 0 }}>
            {/* ── ML PREDICTION ── */}
            <div style={{ ...CARD, padding: 0, overflow: 'hidden', marginBottom: 24 }}>
              <div className="flex items-center justify-between" style={{ padding: '16px 22px', borderBottom: `1px solid ${HAIR}` }}>
                <div className="flex items-center gap-2.5">
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#7C3AED' }} />
                  <h2 style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.14em', textTransform: 'uppercase', color: '#7C3AED' }}>Prediksi ML</h2>
                  <span style={{ fontFamily: MONO, fontSize: 10, color: FAINT, background: '#F2F1EC', padding: '2px 8px', borderRadius: 999 }}>Horizon 5 hari</span>
                </div>
                {mlStatus?.trained && mlStatus.trained_at && (
                  <span style={{ fontFamily: MONO, fontSize: 10, color: FAINT }} className="hidden md:block">
                    Dilatih {new Date(mlStatus.trained_at).toLocaleDateString('id-ID')}{mlStatus.accuracy ? ` · Acc ${(mlStatus.accuracy * 100).toFixed(1)}%` : ''}
                  </span>
                )}
              </div>

              <div style={{ padding: 22 }}>
                {!mlStatus?.trained && !mlLoading && (
                  <div className="flex flex-col items-center justify-center gap-2" style={{ padding: '28px 0' }}>
                    <p style={{ fontSize: 13, color: MUTED }}>Prediksi belum tersedia untuk saham ini.</p>
                    <p style={{ fontSize: 11.5, color: FAINT }}>Model dilatih otomatis setiap hari setelah sinkronisasi data.</p>
                  </div>
                )}
                {mlLoading && (
                  <div className="flex items-center justify-center" style={{ padding: '28px 0' }}>
                    <p style={{ fontFamily: MONO, fontSize: 11, color: FAINT, textTransform: 'uppercase', letterSpacing: '.12em' }} className="animate-pulse">Menghitung prediksi...</p>
                  </div>
                )}
                {mlResult?.status === 'error' && (
                  <div style={{ color: DOWN, fontSize: 12.5, fontFamily: MONO, textAlign: 'center', padding: '16px 0' }}>{mlResult.message}</div>
                )}
                {mlResult?.status === 'ok' && !mlLoading && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-7">
                    <div>
                      <div className="inline-flex items-center gap-3" style={{ padding: '11px 16px', borderRadius: 14, marginBottom: 18,
                        background: mlResult.direction === 'BULLISH' ? UP_BG : mlResult.direction === 'BEARISH' ? DOWN_BG : '#FEF6E7',
                        color: mlResult.direction === 'BULLISH' ? UP : mlResult.direction === 'BEARISH' ? DOWN : '#B7791F',
                        border: `1px solid ${mlResult.direction === 'BULLISH' ? '#BBE6CC' : mlResult.direction === 'BEARISH' ? '#F2C9C9' : '#F5E0B0'}` }}>
                        <span style={{ fontSize: 20, fontWeight: 800 }}>{mlResult.direction === 'BULLISH' ? '▲' : mlResult.direction === 'BEARISH' ? '▼' : '◆'}</span>
                        <div>
                          <p style={{ fontSize: 16, fontWeight: 800, letterSpacing: '-.01em', lineHeight: 1 }}>{mlResult.direction}</p>
                          <p style={{ fontFamily: MONO, fontSize: 9.5, opacity: .8, textTransform: 'uppercase', letterSpacing: '.1em', marginTop: 3 }}>Rekomendasi: {mlResult.recommendation}</p>
                        </div>
                      </div>

                      <div style={{ marginBottom: 18 }}>
                        <div className="flex justify-between items-center" style={{ marginBottom: 7 }}>
                          <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em', color: FAINT }}>Confidence</span>
                          <span style={{ fontFamily: MONO, fontSize: 14, fontWeight: 700 }}>{mlResult.confidence}%</span>
                        </div>
                        <div style={{ width: '100%', background: '#F2F1EC', borderRadius: 999, height: 7 }}>
                          <div style={{ height: 7, borderRadius: 999, width: `${mlResult.confidence}%`, background: mlResult.direction === 'BULLISH' ? UP : mlResult.direction === 'BEARISH' ? DOWN : '#D9A441', transition: 'width .7s ease' }} />
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-3" style={{ marginBottom: 14 }}>
                        <div style={{ background: UP_BG, border: '1px solid #BBE6CC', borderRadius: 12, padding: 14, textAlign: 'center' }}>
                          <p style={{ fontSize: 9.5, color: MUTED, textTransform: 'uppercase', letterSpacing: '.1em', fontWeight: 700, marginBottom: 4 }}>Prob. Naik</p>
                          <p style={{ fontFamily: MONO, fontSize: 19, fontWeight: 800, color: UP }}>{((mlResult.probability_up ?? 0) * 100).toFixed(1)}%</p>
                        </div>
                        <div style={{ background: DOWN_BG, border: '1px solid #F2C9C9', borderRadius: 12, padding: 14, textAlign: 'center' }}>
                          <p style={{ fontSize: 9.5, color: MUTED, textTransform: 'uppercase', letterSpacing: '.1em', fontWeight: 700, marginBottom: 4 }}>Prob. Turun</p>
                          <p style={{ fontFamily: MONO, fontSize: 19, fontWeight: 800, color: DOWN }}>{((mlResult.probability_down ?? 0) * 100).toFixed(1)}%</p>
                        </div>
                      </div>

                      {mlResult.model_accuracy && (
                        <div className="flex gap-4 flex-wrap" style={{ fontFamily: MONO, fontSize: 10, color: FAINT }}>
                          <span>Akurasi: <span style={{ color: INK, fontWeight: 700 }}>{(mlResult.model_accuracy * 100).toFixed(1)}%</span></span>
                          {mlResult.model_auc && <span>AUC: <span style={{ color: INK, fontWeight: 700 }}>{mlResult.model_auc.toFixed(3)}</span></span>}
                          {mlResult.samples_train && <span>Train: <span style={{ color: INK, fontWeight: 700 }}>{mlResult.samples_train} bar</span></span>}
                        </div>
                      )}
                    </div>

                    <div>
                      <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em', color: FAINT, marginBottom: 14 }}>Faktor Penentu Utama</p>
                      <div className="space-y-3">
                        {mlResult.top_features?.map((f, i) => {
                          const maxImp = mlResult.top_features![0].importance;
                          const pct = Math.round((f.importance / maxImp) * 100);
                          return (
                            <div key={i}>
                              <div className="flex justify-between items-center" style={{ marginBottom: 5 }}>
                                <span style={{ fontSize: 11.5, fontWeight: 600, color: MUTED }}>{f.name}</span>
                                <span style={{ fontFamily: MONO, fontSize: 10, color: FAINT }}>{(f.importance * 100).toFixed(1)}%</span>
                              </div>
                              <div style={{ width: '100%', background: '#F2F1EC', borderRadius: 999, height: 6 }}>
                                <div style={{ height: 6, borderRadius: 999, width: `${pct}%`, background: 'color-mix(in oklab, #7C3AED, white 35%)' }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                      <p style={{ fontFamily: MONO, fontSize: 9.5, color: FAINT, marginTop: 16, lineHeight: 1.6 }}>
                        ⚠ Prediksi berbasis probabilitas historis — bukan jaminan. Selalu konfirmasi dengan analisa teknikal & fundamental.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ── TECHNICAL INDICATORS (compact, grouped) ── */}
            <div className="flex items-center gap-3 mb-4">
              <h2 style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: FAINT }}>Indikator Teknikal</h2>
              <span style={{ flex: 1, height: 1, background: HAIR }} />
            </div>
            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              {indGroups.map((g, gi) => (
                <div key={g.title} className="ind-group" style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', borderBottom: gi < indGroups.length - 1 ? '1px solid #F4F3EF' : 'none' }}>
                  <span className="ind-group-label" style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: FAINT, width: 132, flex: 'none' }}>{g.title}</span>
                  <div className="ind-group-items" style={{ display: 'flex', flexWrap: 'wrap', gap: 26, flex: 1 }}>
                    {g.items.map(it => (
                      <div key={it.label} style={{ minWidth: 84 }}>
                        <p style={{ fontSize: 10, color: FAINT, fontWeight: 600, marginBottom: 3 }}>
                          {it.label}
                          {it.tag && <span style={{ marginLeft: 6, fontFamily: MONO, fontSize: 8.5, fontWeight: 700, color: it.color, textTransform: 'uppercase' }}>{it.tag}</span>}
                        </p>
                        <p style={{ fontFamily: MONO, fontSize: 14.5, fontWeight: 700, color: it.color ?? INK }}>{fmt(it.value)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* RIGHT: Buy & Sell panel */}
          <div className="term-trade">
            <div style={{ ...CARD, padding: 18 }}>
              <h2 style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: FAINT, marginBottom: 14 }}>Order</h2>

              {/* BUY / SELL segmented */}
              <div style={{ display: 'flex', gap: 4, padding: 4, background: '#F2F1EC', borderRadius: 12, marginBottom: 16 }}>
                {(['BUY', 'SELL'] as const).map(side => {
                  const active = orderSide === side;
                  const col = side === 'BUY' ? UP : DOWN;
                  return (
                    <button
                      key={side}
                      onClick={() => setOrderSide(side)}
                      style={{ flex: 1, padding: '9px 0', borderRadius: 9, fontSize: 13, fontWeight: 800, letterSpacing: '.04em', border: 'none', cursor: 'pointer', transition: 'all .15s ease', background: active ? '#fff' : 'transparent', color: active ? col : MUTED, boxShadow: active ? '0 1px 4px rgba(20,20,15,.1)' : 'none' }}
                    >
                      {side === 'BUY' ? 'Beli' : 'Jual'}
                    </button>
                  );
                })}
              </div>

              {/* Reason (optional) */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Catatan (opsional)</label>
                <input
                  type="text"
                  placeholder="Alasan / catatan order..."
                  value={reasoning}
                  onChange={(e) => setReasoning(e.target.value)}
                  className="emx-input"
                  style={{ width: '100%', background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 12px', fontSize: 13, color: INK, fontFamily: SANS }}
                />
              </div>

              {/* Quantity */}
              <div style={{ marginBottom: 14 }}>
                <label style={labelStyle}>Jumlah (Lot)</label>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button onClick={() => setTradeQty(q => Math.max(1, q - 1))} className="emx-btn" style={{ width: 38, height: 38, flex: 'none', borderRadius: 10, border: `1px solid ${HAIR}`, background: '#fff', fontSize: 18, color: INK, cursor: 'pointer', lineHeight: 1 }}>−</button>
                  <input
                    type="number"
                    value={tradeQty}
                    onChange={(e) => setTradeQty(Math.max(1, parseInt(e.target.value) || 1))}
                    className="emx-input"
                    style={{ flex: 1, minWidth: 0, textAlign: 'center', background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '9px 8px', fontSize: 15, fontWeight: 700, fontFamily: MONO, color: INK }}
                  />
                  <button onClick={() => setTradeQty(q => q + 1)} className="emx-btn" style={{ width: 38, height: 38, flex: 'none', borderRadius: 10, border: `1px solid ${HAIR}`, background: '#fff', fontSize: 18, color: INK, cursor: 'pointer', lineHeight: 1 }}>+</button>
                </div>
                <p style={{ fontFamily: MONO, fontSize: 10.5, color: FAINT, marginTop: 6 }}>{tradeQty} lot = {(tradeQty * 100).toLocaleString('id-ID')} lembar</p>
              </div>

              {/* Estimated total */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', background: '#FBFBF9', border: `1px solid ${HAIR}`, borderRadius: 12, marginBottom: 16 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: FAINT, textTransform: 'uppercase', letterSpacing: '.06em' }}>Estimasi Total</span>
                <span style={{ fontFamily: MONO, fontSize: 15, fontWeight: 700 }}>Rp {totalValue.toLocaleString('id-ID')}</span>
              </div>

              {/* Execute */}
              <button
                onClick={handleTrade}
                disabled={isTrading}
                className="emx-btn"
                style={{ width: '100%', padding: '13px 0', borderRadius: 12, fontSize: 14, fontWeight: 800, letterSpacing: '.04em', border: 'none', cursor: 'pointer', color: '#fff', background: orderSide === 'BUY' ? UP : DOWN, opacity: isTrading ? 0.6 : 1, boxShadow: `0 6px 18px -8px ${orderSide === 'BUY' ? UP : DOWN}` }}
              >
                {isTrading ? 'Memproses...' : orderSide === 'BUY' ? `Beli ${ticker}` : `Jual ${ticker}`}
              </button>

              {/* Position */}
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: `1px solid ${HAIR}` }}>
                <div className="flex items-center justify-between" style={{ marginBottom: portfolio ? 10 : 0 }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: FAINT, textTransform: 'uppercase', letterSpacing: '.06em' }}>Posisi Kamu</span>
                  <span style={{ fontFamily: MONO, fontSize: 14, fontWeight: 700, color: portfolio ? INK : FAINT }}>{portfolio ? `${portfolio.shares / 100} Lot` : '0 Lot'}</span>
                </div>
                {portfolio && (
                  <div className="grid grid-cols-2 gap-2" style={{ fontFamily: MONO, fontSize: 11 }}>
                    <div>
                      <p style={{ color: FAINT, fontSize: 9.5, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 2 }}>Avg Price</p>
                      <p style={{ fontWeight: 700 }}>Rp {portfolio.avg_price?.toLocaleString('id-ID')}</p>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <p style={{ color: FAINT, fontSize: 9.5, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 2 }}>Unrealized</p>
                      <p style={{ fontWeight: 700, color: (portfolio.unrealized_pnl ?? 0) >= 0 ? UP : DOWN }}>
                        {(portfolio.unrealized_pnl ?? 0) >= 0 ? '+' : ''}Rp {Math.abs(portfolio.unrealized_pnl ?? 0).toLocaleString('id-ID')}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .term-grid {
          display: grid;
          grid-template-columns: 248px minmax(0, 1fr) 320px;
          grid-template-areas:
            "side top trade"
            "side bottom trade";
          gap: 20px;
          align-items: start;
        }
        .term-side { grid-area: side; position: sticky; top: 84px; }
        .term-main-top { grid-area: top; min-width: 0; }
        .term-main-bottom { grid-area: bottom; min-width: 0; margin-top: 4px; }
        .term-trade { grid-area: trade; position: sticky; top: 84px; }
        .term-mobile-select { display: none; }
        @media (max-width: 1180px) {
          /* Stack into one column and reorder so Buy/Sell sits right under the chart.
             align-items stretch makes every stacked card span the full width
             (otherwise the inherited start value shrinks the order card to its content). */
          .term-grid { display: flex; flex-direction: column; align-items: stretch; gap: 18px; }
          .term-side { display: none; }
          .term-main-top, .term-main-bottom, .term-trade { width: 100%; min-width: 0; }
          .term-main-top { order: 1; }
          .term-trade { order: 2; position: static; }
          .term-main-bottom { order: 3; margin-top: 0; }
          .term-mobile-select { display: block; }
        }
        @media (max-width: 520px) {
          .ind-group { flex-direction: column; align-items: flex-start !important; gap: 8px !important; }
          .ind-group-label { width: auto !important; }
          .ind-group-items { gap: 18px !important; }
        }
        .emx-listrow { transition: background .14s ease; }
        .emx-listrow:hover { background: #FBFBF9; }
        .emx-input { transition: border-color .15s ease, box-shadow .15s ease; }
        .emx-input:focus { outline: none; border-color: color-mix(in oklab, ${ACCENT}, white 50%); box-shadow: 0 0 0 3px color-mix(in oklab, ${ACCENT}, transparent 86%); }
        .emx-input::placeholder { color: #A9A9A1; }
        .emx-btn { transition: transform .15s ease, filter .15s ease; }
        .emx-btn:hover { transform: translateY(-1px); filter: brightness(1.02); }
        .emx-scroll::-webkit-scrollbar { width: 6px; }
        .emx-scroll::-webkit-scrollbar-thumb { background: #E2E1DB; border-radius: 10px; }
        ::selection { background: color-mix(in oklab, ${ACCENT}, white 70%); }
      `}</style>
    </main>
  );
}
