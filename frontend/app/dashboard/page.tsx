'use client';

import { useEffect, useRef, useState } from 'react';
import { api, Stock, MultiPortfolioResponse, OHLCV } from '@/lib/api';
import { INDEX_MEMBERS, INDEX_TABS, IndexKey } from '@/lib/indices';
import Link from 'next/link';
import EmetiqNav from '@/components/EmetiqNav';
import { useToast } from '@/components/Toast';
import { useWatchlist } from '@/components/WatchlistProvider';
import { useAuth } from '@/components/AuthProvider';
import dynamic from 'next/dynamic';

const StockChart = dynamic(() => import("@/components/StockChart"), { ssr: false });

// ── EMETIQ theme tokens (mirrors app/page.tsx landing) ─────────
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

// Categorical colors for the three trading agents (semantic legend, not decoration)
const AGENT = {
  USER: { fg: '#1F6FEB', bg: '#EAF1FE', label: 'User' },
  GEMINI: { fg: '#0E8F7E', bg: '#E4F5F1', label: 'Gemini' },
  CLAUDE: { fg: '#7A5AF8', bg: '#EFEBFE', label: 'Claude' },
};

interface Signal {
  ticker: string;
  name: string;
  type: string;
  strategies: string[];
  max_strength: number;
  date: string;
  market_cap: number | null;
}

export default function Dashboard() {
  useEffect(() => { document.title = 'Dashboard - EMETIQ'; }, []);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [portfolio, setPortfolio] = useState<MultiPortfolioResponse | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [ihsgData, setIhsgData] = useState<OHLCV[]>([]);
  const [loading, setLoading] = useState(true);
  const [isScanning, setIsRunningScan] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const { watchlist, toggle: toggleWatchlist } = useWatchlist();
  const { user } = useAuth();
  const [activeIndex, setActiveIndex] = useState<'ALL' | IndexKey>('ALL');
  const [sortKey, setSortKey] = useState<'name' | 'price' | 'change'>('name');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [visibleCount, setVisibleCount] = useState(30); // progressive (infinite-scroll) render window
  const loadMoreRef = useRef<HTMLDivElement | null>(null);

  const [newTicker, setNewTicker] = useState('');
  const [isAdding, setIsAdding] = useState(false);
  const [minMarketCap, setMinMarketCap] = useState(0);

  const { toast } = useToast();

  const MARKET_CAP_FILTERS = [
    { label: 'Semua', value: 0 },
    { label: 'Mid+', value: 1_000_000_000_000 },
    { label: 'Large', value: 10_000_000_000_000 },
    { label: 'Blue Chip', value: 50_000_000_000_000 },
  ];


  const loadData = async () => {
    try {
      // IHSG: only ~2 months of recent data (lighter payload, easier to read)
      const fromDate = new Date();
      fromDate.setMonth(fromDate.getMonth() - 2);
      const ihsgFrom = fromDate.toISOString().slice(0, 10);
      const [stocksData, ihsg, signalsData] = await Promise.all([
        api.getStocks(),
        api.getOHLCV('^JKSE', ihsgFrom),
        api.getSignals()
      ]);
      setStocks(stocksData);
      setIhsgData(ihsg.data || []);
      setSignals(signalsData || []);
    } catch (err) {
      toast('Gagal memuat data pasar. Periksa koneksi backend.', 'error');
    } finally {
      setLoading(false);
    }

    // Portofolio bersifat personal (butuh login). Jangan sampai menggagalkan
    // halaman pasar bila belum login (endpoint balas 401).
    try {
      if (user) {
        const p = await api.getPortfolio();
        setPortfolio(p && 'USER' in p ? p : null);
      } else {
        setPortfolio(null);
      }
    } catch {
      setPortfolio(null);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleScan = async () => {
    setIsRunningScan(true);
    try {
      await api.triggerScan();
      await loadData();
    } catch (err) {
      toast('Scan gagal. Periksa koneksi backend.', 'error');
    } finally {
      setIsRunningScan(false);
    }
  };

  const handleAddStock = async () => {
    if (!newTicker) return;
    setIsAdding(true);
    try {
      await api.addStock(newTicker);
      setNewTicker('');
      loadData();
    } catch (err) {
      toast(`Ticker "${newTicker}" tidak ditemukan.`, 'error');
    } finally {
      setIsAdding(false);
    }
  };

  // Gabungkan semua portofolio untuk total P&L jika portfolio sudah terisi
  const totalUnrealized = portfolio ? (portfolio.USER.unrealized + portfolio.GEMINI.unrealized + portfolio.CLAUDE.unrealized) : 0;

  const filteredSignals = signals.filter(sig =>
    minMarketCap === 0 || (sig.market_cap != null && sig.market_cap >= minMarketCap)
  );

  const filteredStocks = stocks.filter(s =>
    s.ticker !== '^JKSE' &&
    (activeIndex === 'ALL' || INDEX_MEMBERS[activeIndex].includes(s.ticker)) &&
    (s.ticker.toLowerCase().includes(searchTerm.toLowerCase()) || s.name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const visibleStocks = [...filteredStocks].sort((a, b) => {
    let cmp = 0;
    if (sortKey === 'name') cmp = a.ticker.localeCompare(b.ticker);
    else if (sortKey === 'price') cmp = (a.last_price ?? 0) - (b.last_price ?? 0);
    else cmp = (a.change_pct ?? 0) - (b.change_pct ?? 0);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  const toggleSort = (key: 'name' | 'price' | 'change') => {
    if (sortKey === key) {
      setSortDir(d => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
  };

  const shownStocks = visibleStocks.slice(0, visibleCount);
  const hasMore = visibleCount < visibleStocks.length;

  // Reset the render window whenever the filters/sort change
  useEffect(() => {
    setVisibleCount(30);
  }, [activeIndex, sortKey, sortDir, searchTerm]);

  // Infinite scroll: reveal more rows as the sentinel enters the viewport
  useEffect(() => {
    const el = loadMoreRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) setVisibleCount(c => c + 30);
      },
      { rootMargin: '300px' }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, visibleStocks.length]);

  const currentIhsg = ihsgData[ihsgData.length - 1]?.close || 0;
  const prevIhsg = ihsgData[ihsgData.length - 2]?.close || 0;
  const ihsgChange = currentIhsg - prevIhsg;
  const ihsgUp = ihsgChange >= 0;

  if (loading && stocks.length === 0) return (
    <div
      style={{ minHeight: '100vh', background: BG, fontFamily: MONO, color: ACCENT }}
      className="flex items-center justify-center text-xs tracking-[0.3em] uppercase animate-pulse"
    >
      Memuat terminal...
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

      <EmetiqNav active="market" />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 24px 80px' }}>

        {/* IHSG INDEX */}
        <div style={{ ...CARD, padding: 28, marginBottom: 32 }}>
          <div className="flex flex-wrap justify-between items-center mb-5 gap-3">
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: '-.02em' }}>IHSG</h1>
            <div className="flex items-center gap-3">
              <p style={{ fontFamily: MONO, fontSize: 24, fontWeight: 600 }}>{currentIhsg.toLocaleString('id-ID')}</p>
              <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: ihsgUp ? UP : DOWN, background: ihsgUp ? UP_BG : DOWN_BG, padding: '3px 9px', borderRadius: 7, display: 'inline-block' }}>
                {ihsgUp ? '▲' : '▼'} {prevIhsg ? Math.abs((ihsgChange / prevIhsg) * 100).toFixed(2) : '0.00'}%
              </span>
            </div>
          </div>
          <div style={{ height: 224 }}>
            <StockChart data={ihsgData.slice(-44)} height={220} transparent light chartType="line" interactive={false} lineColor={ihsgUp ? UP : DOWN} />
          </div>
        </div>

        {/* MARKET LIST */}
        <div className="mb-5">
          <div className="flex items-center justify-between mb-4 gap-3">
            <h2 style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, letterSpacing: '.18em', textTransform: 'uppercase', color: FAINT }}>Market Terminal</h2>
            <span style={{ fontFamily: MONO, fontSize: 11.5, color: FAINT }}>{visibleStocks.length} saham</span>
          </div>

          {/* Index quick actions */}
          <div className="flex gap-2 overflow-x-auto emx-scroll" style={{ paddingBottom: 4 }}>
            {INDEX_TABS.map(tab => {
              const active = activeIndex === tab.key;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveIndex(tab.key)}
                  style={{ flex: 'none', fontSize: 13, fontWeight: 700, padding: '8px 16px', borderRadius: 999, cursor: 'pointer', transition: 'all .15s ease', border: `1px solid ${active ? ACCENT : HAIR}`, background: active ? ACCENT : '#fff', color: active ? '#fff' : MUTED, boxShadow: active ? `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 70%)` : 'none' }}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Controls: sort + search */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 mb-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span style={{ fontSize: 12, fontWeight: 600, color: FAINT }}>Urut</span>
            {([['name', 'Nama'], ['price', 'Harga'], ['change', '%']] as const).map(([key, label]) => {
              const active = sortKey === key;
              return (
                <button
                  key={key}
                  onClick={() => toggleSort(key)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 12, fontWeight: 700, padding: '6px 11px', borderRadius: 999, cursor: 'pointer', transition: 'all .15s ease', border: `1px solid ${active ? ACCENT : HAIR}`, background: active ? `color-mix(in oklab, ${ACCENT}, white 88%)` : '#fff', color: active ? ACCENT : MUTED }}
                >
                  {label}{active && <span style={{ fontSize: 9 }}>{sortDir === 'asc' ? '▲' : '▼'}</span>}
                </button>
              );
            })}
          </div>
          <input
            type="text"
            placeholder="Cari saham..."
            className="emx-input w-full md:w-72"
            style={{ background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 11, padding: '10px 16px', fontSize: 13, color: INK, fontFamily: SANS }}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {/* List */}
        <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '24px minmax(0,1fr) 100px 82px', gap: 10, alignItems: 'center', padding: '11px 18px', background: '#FBFBF9', borderBottom: `1px solid ${HAIR}`, fontFamily: MONO, fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: FAINT }}>
            <span />
            <span>Saham</span>
            <span style={{ textAlign: 'right' }}>Harga</span>
            <span style={{ textAlign: 'right' }}>Chg</span>
          </div>

          {visibleStocks.length === 0 ? (
            <div style={{ padding: '44px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>
              Tidak ada saham yang cocok dengan filter ini.
            </div>
          ) : (
            shownStocks.map((stock, i) => {
              const owners = (['USER', 'GEMINI', 'CLAUDE'] as const).filter(
                key => portfolio?.[key].assets.some(p => p.ticker === stock.ticker)
              );
              const starred = watchlist.has(stock.ticker);
              const up = stock.change_pct != null && stock.change_pct >= 0;

              return (
                <Link
                  key={stock.ticker}
                  href={`/stocks/${stock.ticker}`}
                  className="emx-listrow"
                  style={{ display: 'grid', gridTemplateColumns: '24px minmax(0,1fr) 100px 82px', gap: 10, alignItems: 'center', padding: '12px 18px', borderBottom: i < shownStocks.length - 1 ? '1px solid #F2F1EC' : 'none', textDecoration: 'none', color: INK }}
                >
                  <button
                    onClick={(e) => toggleWatchlist(e, stock.ticker)}
                    style={{ fontSize: 15, lineHeight: 1, background: 'none', border: 'none', cursor: 'pointer', color: starred ? ACCENT : '#D6D5CE', transition: 'color .15s ease' }}
                    title={starred ? 'Hapus dari watchlist' : 'Tambah ke watchlist'}
                  >★</button>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span style={{ fontWeight: 700, fontSize: 14 }}>{stock.ticker}</span>
                      {owners.map(key => (
                        <span key={key} style={{ fontSize: 9, fontWeight: 700, background: AGENT[key].bg, color: AGENT[key].fg, padding: '1px 6px', borderRadius: 5 }}>{AGENT[key].label}</span>
                      ))}
                    </div>
                    <p style={{ fontFamily: MONO, fontSize: 11, color: FAINT, marginTop: 2 }} className="truncate">{stock.name}</p>
                  </div>
                  <span style={{ fontFamily: MONO, fontSize: 14, fontWeight: 600, textAlign: 'right' }}>
                    {stock.last_price != null ? stock.last_price.toLocaleString('id-ID') : '-'}
                  </span>
                  <span style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    {stock.change_pct != null ? (
                      <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: up ? UP : DOWN, background: up ? UP_BG : DOWN_BG, padding: '2px 7px', borderRadius: 6 }}>
                        {up ? '▲' : '▼'} {Math.abs(stock.change_pct).toFixed(2)}%
                      </span>
                    ) : (
                      <span style={{ fontFamily: MONO, fontSize: 11, color: '#B6B6AE' }}>-</span>
                    )}
                  </span>
                </Link>
              );
            })
          )}

          {hasMore && (
            <div ref={loadMoreRef} style={{ padding: '14px 18px', textAlign: 'center', fontFamily: MONO, fontSize: 11, color: FAINT, borderTop: '1px solid #F2F1EC' }}>
              Memuat saham lainnya...
            </div>
          )}
        </div>
      </div>

      <style jsx global>{`
        .emx-card {
          transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
        }
        .emx-card:hover {
          transform: translateY(-3px);
          border-color: color-mix(in oklab, ${ACCENT}, white 55%);
          box-shadow: 0 22px 48px -26px rgba(20, 20, 15, .3);
        }
        .emx-card:hover h3 {
          color: ${ACCENT};
        }
        .emx-row {
          transition: border-color .15s ease, background .15s ease;
        }
        .emx-row:hover {
          border-color: color-mix(in oklab, ${ACCENT}, white 58%);
          background: #fff;
        }
        .emx-listrow {
          transition: background .14s ease;
        }
        .emx-listrow:hover {
          background: #FBFBF9;
        }
        .emx-input::placeholder {
          color: #A9A9A1;
        }
        .emx-input:focus {
          outline: none;
          border-color: color-mix(in oklab, ${ACCENT}, white 50%);
          box-shadow: 0 0 0 3px color-mix(in oklab, ${ACCENT}, transparent 86%);
        }
        .emx-btn {
          transition: transform .15s ease, filter .15s ease;
        }
        .emx-btn:hover {
          transform: translateY(-1px);
          filter: brightness(1.03);
        }
        .emx-btn:active {
          transform: translateY(0);
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
      `}</style>
    </main>
  );
}
