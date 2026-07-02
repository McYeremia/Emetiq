'use client';

import { useEffect, useState } from 'react';
import { api, Stock, OHLCV } from '@/lib/api';
import Link from 'next/link';
import EmetiqNav from '@/components/EmetiqNav';
import { useToast } from '@/components/Toast';
import { useAuth } from '@/components/AuthProvider';
import { useWatchlist } from '@/components/WatchlistProvider';
import dynamic from 'next/dynamic';

const StockChart = dynamic(() => import('@/components/StockChart'), { ssr: false });

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

function QuoteRow({ stock, starred, onStar }: { stock: Stock; starred?: boolean; onStar?: (e: React.MouseEvent) => void }) {
  const up = stock.change_pct != null && stock.change_pct >= 0;
  return (
    <Link href={`/stocks/${stock.ticker}`} className="emx-listrow" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '11px 16px', textDecoration: 'none', color: INK }}>
      <div className="min-w-0" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {onStar && (
          <button
            onClick={onStar}
            title={starred ? 'Hapus dari watchlist' : 'Tambah ke watchlist'}
            style={{ fontSize: 14, lineHeight: 1, background: 'none', border: 'none', cursor: 'pointer', color: starred ? ACCENT : '#D6D5CE', flex: 'none' }}
          >★</button>
        )}
        <div className="min-w-0">
          <div style={{ fontWeight: 700, fontSize: 14 }}>{stock.ticker}</div>
          <div style={{ fontFamily: MONO, fontSize: 11, color: FAINT }} className="truncate">{stock.name}</div>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 'none' }}>
        <span style={{ fontFamily: MONO, fontSize: 13.5, fontWeight: 600 }}>{stock.last_price != null ? stock.last_price.toLocaleString('id-ID') : '-'}</span>
        {stock.change_pct != null && (
          <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: up ? UP : DOWN, background: up ? UP_BG : DOWN_BG, padding: '2px 7px', borderRadius: 6, minWidth: 66, textAlign: 'right' }}>
            {up ? '▲' : '▼'} {Math.abs(stock.change_pct).toFixed(2)}%
          </span>
        )}
      </div>
    </Link>
  );
}

function CardHead({ title, accent, badge }: { title: string; accent?: string; badge?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 18px', borderBottom: `1px solid ${HAIR}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {accent && <span style={{ width: 8, height: 8, borderRadius: '50%', background: accent }} />}
        <h2 style={{ fontSize: 14.5, fontWeight: 700 }}>{title}</h2>
      </div>
      {badge && <span style={{ fontFamily: MONO, fontSize: 11, color: FAINT }}>{badge}</span>}
    </div>
  );
}

export default function Overview() {
  useEffect(() => { document.title = 'Overview - EMETIQ'; }, []);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [ihsgData, setIhsgData] = useState<OHLCV[]>([]);
  const [loading, setLoading] = useState(true);
  const { toast } = useToast();
  const { user } = useAuth();
  const { watchlist, toggle } = useWatchlist();

  const loadData = async () => {
    try {
      const fromDate = new Date();
      fromDate.setMonth(fromDate.getMonth() - 2);
      const ihsgFrom = fromDate.toISOString().slice(0, 10);
      const [stocksData, ihsg] = await Promise.all([
        api.getStocks(),
        api.getOHLCV('^JKSE', ihsgFrom),
      ]);
      setStocks(stocksData);
      setIhsgData(ihsg.data || []);
    } catch (err) {
      toast('Gagal memuat data pasar. Periksa koneksi backend.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  const currentIhsg = ihsgData[ihsgData.length - 1]?.close || 0;
  const prevIhsg = ihsgData[ihsgData.length - 2]?.close || 0;
  const ihsgChange = currentIhsg - prevIhsg;
  const ihsgUp = ihsgChange >= 0;

  const tradable = stocks.filter(s => s.ticker !== '^JKSE' && s.change_pct != null);
  const gainers = [...tradable].sort((a, b) => (b.change_pct ?? 0) - (a.change_pct ?? 0)).slice(0, 5);
  const losers = [...tradable].sort((a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0)).slice(0, 5);
  const watchlistStocks = stocks.filter(s => watchlist.has(s.ticker));

  if (loading && stocks.length === 0) return (
    <div style={{ minHeight: '100vh', background: BG, fontFamily: MONO, color: ACCENT }} className="flex items-center justify-center text-xs tracking-[0.3em] uppercase animate-pulse">
      Memuat overview...
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

      <EmetiqNav active="overview" />

      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '28px 24px 80px' }}>
        <div className="mb-6">
          <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>Overview</h1>
          <p style={{ marginTop: 4, fontSize: 14.5, color: MUTED }}>Ringkasan pasar hari ini, watchlist, dan pergerakan teratas.</p>
        </div>

        <div className="ov-grid" style={{ display: 'grid', gap: 24 }}>
          {/* LEFT: IHSG + Watchlist */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            {/* IHSG Today */}
            <div style={{ ...CARD, padding: 24 }}>
              <div className="mb-4">
                <p style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, letterSpacing: '.16em', textTransform: 'uppercase', color: ACCENT, marginBottom: 6 }}>IHSG Today</p>
                <div className="flex flex-wrap justify-between items-center gap-3">
                  <h2 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>JCX</h2>
                  <div className="flex items-center gap-3">
                    <p style={{ fontFamily: MONO, fontSize: 22, fontWeight: 600 }}>{currentIhsg.toLocaleString('id-ID')}</p>
                    <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, color: ihsgUp ? UP : DOWN, background: ihsgUp ? UP_BG : DOWN_BG, padding: '3px 9px', borderRadius: 7, display: 'inline-block' }}>
                      {ihsgUp ? '▲' : '▼'} {prevIhsg ? Math.abs((ihsgChange / prevIhsg) * 100).toFixed(2) : '0.00'}%
                    </span>
                  </div>
                </div>
              </div>
              <div style={{ height: 210 }}>
                <StockChart data={ihsgData.slice(-44)} height={206} transparent light chartType="line" interactive={false} lineColor={ihsgUp ? UP : DOWN} />
              </div>
            </div>

            {/* Watchlist */}
            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              <CardHead title="Watchlist" badge={`${watchlistStocks.length} saham`} />
              {!user ? (
                <div style={{ padding: '32px 18px', textAlign: 'center' }}>
                  <p style={{ fontSize: 13.5, color: MUTED }}>Masuk untuk menyimpan watchlist pribadi.</p>
                  <Link href="/login?next=/overview" style={{ display: 'inline-block', marginTop: 12, fontSize: 13, fontWeight: 700, color: '#fff', background: ACCENT, padding: '9px 16px', borderRadius: 11, textDecoration: 'none' }} className="emx-btn">
                    Masuk
                  </Link>
                </div>
              ) : watchlistStocks.length === 0 ? (
                <div style={{ padding: '32px 18px', textAlign: 'center' }}>
                  <p style={{ fontSize: 13.5, color: MUTED }}>Belum ada saham di watchlist.</p>
                  <Link href="/dashboard" style={{ display: 'inline-block', marginTop: 12, fontSize: 13, fontWeight: 700, color: '#fff', background: ACCENT, padding: '9px 16px', borderRadius: 11, textDecoration: 'none' }} className="emx-btn">
                    Tambah dari Market
                  </Link>
                </div>
              ) : (
                <div className="emx-rows">
                  {watchlistStocks.map(stock => (
                    <QuoteRow key={stock.ticker} stock={stock} starred={watchlist.has(stock.ticker)} onStar={(e) => toggle(e, stock.ticker)} />
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT: Top Gainer + Top Loser */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              <CardHead title="Top Gainer" accent={UP} badge="Hari ini" />
              {gainers.length === 0 ? (
                <div style={{ padding: '28px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>Belum ada data.</div>
              ) : (
                <div className="emx-rows">
                  {gainers.map(stock => <QuoteRow key={stock.ticker} stock={stock} />)}
                </div>
              )}
            </div>

            <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
              <CardHead title="Top Loser" accent={DOWN} badge="Hari ini" />
              {losers.length === 0 ? (
                <div style={{ padding: '28px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>Belum ada data.</div>
              ) : (
                <div className="emx-rows">
                  {losers.map(stock => <QuoteRow key={stock.ticker} stock={stock} />)}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style jsx global>{`
        .ov-grid {
          grid-template-columns: 1.5fr 1fr;
        }
        /* Grid tracks default to min-width:auto, which lets non-wrapping
           card content push the whole page wider than the viewport. */
        .ov-grid > * {
          min-width: 0;
        }
        @media (max-width: 900px) {
          .ov-grid {
            grid-template-columns: 1fr !important;
          }
        }
        .emx-rows > a {
          border-bottom: 1px solid #F2F1EC;
        }
        .emx-rows > a:last-child {
          border-bottom: none;
        }
        .emx-listrow {
          transition: background .14s ease;
        }
        .emx-listrow:hover {
          background: #FBFBF9;
        }
        .emx-btn {
          transition: transform .15s ease, filter .15s ease;
        }
        .emx-btn:hover {
          transform: translateY(-1px);
          filter: brightness(1.03);
        }
        ::selection {
          background: color-mix(in oklab, ${ACCENT}, white 70%);
        }
      `}</style>
    </main>
  );
}
