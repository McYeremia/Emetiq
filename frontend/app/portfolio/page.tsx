'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { api, TradeHistory, PortfolioItem, MultiPortfolioResponse } from '@/lib/api';
import { INITIAL_MODAL } from '@/lib/constants';
import { useToast } from '@/components/Toast';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const EquityChart = dynamic(() => import('@/components/EquityChart'), { ssr: false });

type PortfolioTab = 'USER' | 'GEMINI' | 'CLAUDE';
type ViewMode = 'portfolio' | 'analytics';

const DONUT_COLORS = ['#3b82f6','#14b8a6','#a855f7','#f59e0b','#ef4444','#10b981','#f97316','#06b6d4','#8b5cf6'];

function buildDonutPath(s: number, e: number, cx: number, cy: number, ro: number, ri: number) {
  const x1 = cx + ro * Math.cos(s), y1 = cy + ro * Math.sin(s);
  const x2 = cx + ro * Math.cos(e), y2 = cy + ro * Math.sin(e);
  const ix1 = cx + ri * Math.cos(e), iy1 = cy + ri * Math.sin(e);
  const ix2 = cx + ri * Math.cos(s), iy2 = cy + ri * Math.sin(s);
  const la = e - s > Math.PI ? 1 : 0;
  return `M ${x1} ${y1} A ${ro} ${ro} 0 ${la} 1 ${x2} ${y2} L ${ix1} ${iy1} A ${ri} ${ri} 0 ${la} 0 ${ix2} ${iy2} Z`;
}

const TAB_COLORS: Record<PortfolioTab, string> = {
  USER: '#3b82f6',
  GEMINI: '#14b8a6',
  CLAUDE: '#a855f7',
};

const TAB_ACTIVE_CLASS: Record<PortfolioTab, string> = {
  USER: 'bg-blue-600 text-white',
  GEMINI: 'bg-teal-600 text-white',
  CLAUDE: 'bg-purple-600 text-white',
};

interface SellModal {
  open: boolean;
  ticker: string;
  maxLots: number;
  currentPrice: number;
  avgPrice: number;
}

export default function PortfolioPage() {
  useEffect(() => { document.title = 'Portfolio — IDXAnalyst'; }, []);
  const router = useRouter();
  const { toast } = useToast();
  const [data, setData] = useState<MultiPortfolioResponse | null>(null);
  const [growth, setGrowth] = useState<Record<PortfolioTab, { date: string; value: number }[]> | null>(null);
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [tabLoading, setTabLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<PortfolioTab>('USER');
  const [sellModal, setSellModal] = useState<SellModal>({ open: false, ticker: '', maxLots: 0, currentPrice: 0, avgPrice: 0 });
  const [sellQty, setSellQty] = useState(1);
  const [isSelling, setIsSelling] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('portfolio');
  const [histSearch, setHistSearch] = useState('');
  const [histActionFilter, setHistActionFilter] = useState<'ALL' | 'BUY' | 'SELL'>('ALL');
  const [donutHovered, setDonutHovered] = useState<{ ticker: string; pct: number; value: number } | null>(null);

  const isInitialLoad = useRef(true);

  const refresh = useCallback(async () => {
    const [portfolio, growthData, hist] = await Promise.all([
      api.getPortfolio(),
      api.getPortfolioGrowth(),
      api.getTradeHistory(activeTab),
    ]);
    setData(portfolio);
    setGrowth(growthData);
    setHistory(hist);
  }, [activeTab]);

  useEffect(() => {
    if (isInitialLoad.current) {
      isInitialLoad.current = false;
      setLoading(true);
      refresh().finally(() => setLoading(false));
    } else {
      setTabLoading(true);
      refresh().finally(() => setTabLoading(false));
    }
  }, [refresh]);

  const openSellModal = (ticker: string, shares: number, currentPrice: number, avgPrice: number) => {
    const maxLots = Math.floor(shares / 100);
    setSellQty(1);
    setSellModal({ open: true, ticker, maxLots, currentPrice, avgPrice });
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sellModal.open) {
        setSellModal({ open: false, ticker: '', maxLots: 0, currentPrice: 0, avgPrice: 0 });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [sellModal.open]);

  const handleSell = async () => {
    if (sellQty < 1 || sellQty > sellModal.maxLots) return;
    setIsSelling(true);
    try {
      const res = await api.executeTrade(sellModal.ticker, 'SELL', sellQty, undefined, 'MANUAL', 'Sold from portfolio');
      if (res.status === 'ok') {
        setSellModal({ open: false, ticker: '', maxLots: 0, currentPrice: 0, avgPrice: 0 });
        await refresh();
      } else {
        toast(res.detail || 'Gagal menjual saham', 'error');
      }
    } catch {
      toast('Gagal menghubungi server', 'error');
    } finally {
      setIsSelling(false);
    }
  };

  if (loading || !data) return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center text-blue-500 font-mono text-xs uppercase tracking-widest">
      Loading Combat Data...
    </div>
  );

  const current = data[activeTab];
  const growthData = growth?.[activeTab] ?? [];
  const totalReturn = current.total_value - INITIAL_MODAL;
  const totalReturnPct = ((totalReturn / INITIAL_MODAL) * 100).toFixed(2);

  // Trade history filter
  const filteredHistory = history.filter(t => {
    const matchTicker = t.ticker.toLowerCase().includes(histSearch.toLowerCase());
    const matchAction = histActionFilter === 'ALL' || t.action === histActionFilter;
    return matchTicker && matchAction;
  });

  const exportToCSV = () => {
    if (filteredHistory.length === 0) return;
    const header = ['Tanggal', 'Ticker', 'Aksi', 'Harga', 'Lot', 'Total', 'P&L', 'P&L %', 'Strategi', 'Catatan'];
    const rows = filteredHistory.map(t => [
      t.date,
      t.ticker,
      t.action,
      t.price.toString(),
      t.quantity.toString(),
      t.total_value.toLocaleString('id-ID'),
      t.pnl != null ? t.pnl.toLocaleString('id-ID') : '',
      t.pnl_pct != null ? t.pnl_pct.toFixed(2) + '%' : '',
      t.strategy,
      `"${(t.notes || '').replace(/"/g, '""')}"`,
    ]);
    const csv = [header, ...rows].map(r => r.join(',')).join('\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade-history-${activeTab}-${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Analytics
  const sellTrades = history.filter(t => t.action === 'SELL' && t.pnl !== null);
  const winCount = sellTrades.filter(t => t.pnl! > 0).length;
  const winRate = sellTrades.length > 0 ? (winCount / sellTrades.length * 100) : null;

  let maxDrawdownPct = 0;
  if (growthData.length > 1) {
    let peak = growthData[0].value;
    for (const pt of growthData) {
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

  const maxMonthlyAbs = monthlyRows.length > 0
    ? Math.max(...monthlyRows.map(([, v]) => Math.abs(v)))
    : 1;

  return (
    <main className="min-h-screen bg-[#050505] text-white p-6 md:p-10 pt-24 md:pt-28 text-left font-mono">
      <div className="max-w-7xl mx-auto">

        {/* HEADER */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-6 mb-10">
          <div>
            <h1 className="text-4xl font-black tracking-tighter mb-2">Portfolio <span className="text-blue-500">Battleground</span></h1>
            <p className="text-gray-500 text-[10px] uppercase tracking-widest leading-loose font-bold">15 Million Capital Battle: Human vs Gemini vs Claude</p>
          </div>
          <div className="flex flex-wrap gap-2 p-1 bg-white/5 rounded-2xl border border-white/10 overflow-x-auto shadow-inner">
            {(['USER', 'GEMINI', 'CLAUDE'] as PortfolioTab[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-2 rounded-xl text-[10px] font-black tracking-widest transition-all ${activeTab === tab ? TAB_ACTIVE_CLASS[tab] : 'text-gray-500 hover:text-white'}`}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {/* TOTAL VALUE — Hero Number */}
        <div className="bg-gradient-to-r from-white/[0.03] to-transparent border border-white/5 rounded-3xl p-8 mb-6 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <p className="text-[9px] font-black uppercase tracking-[0.4em] text-gray-500 mb-1">Total Portfolio Value</p>
            <p className="text-4xl font-black font-mono">Rp {current.total_value.toLocaleString('id-ID')}</p>
          </div>
          <div className="text-right">
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-1">vs Modal Awal (15 Juta)</p>
            <p className={`text-2xl font-black ${totalReturn >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {totalReturn >= 0 ? '▲' : '▼'} {Math.abs(parseFloat(totalReturnPct))}%
            </p>
            <p className={`text-xs font-mono ${totalReturn >= 0 ? 'text-green-400/60' : 'text-red-400/60'}`}>
              {totalReturn >= 0 ? '+' : ''}Rp {totalReturn.toLocaleString('id-ID')}
            </p>
          </div>
        </div>

        {/* CORE STATS */}
        <div className={`grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 relative transition-opacity duration-200 ${tabLoading ? 'opacity-50' : 'opacity-100'}`}>
          {tabLoading && (
            <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
              <span className="text-[9px] font-black uppercase tracking-[0.4em] text-blue-400 animate-pulse">LOADING...</span>
            </div>
          )}
          <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl shadow-xl">
            <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1 font-black">Kas Tersedia</p>
            <p className={`text-lg font-black ${current.modal < 0 ? 'text-red-400' : 'text-white'}`}>
              Rp {current.modal.toLocaleString('id-ID')}
            </p>
          </div>
          <div className="bg-white/[0.02] border border-blue-500/20 p-6 rounded-2xl shadow-xl">
            <p className="text-[9px] text-blue-500 uppercase tracking-widest mb-1 font-black">Invested</p>
            <p className="text-lg font-black">Rp {current.invested.toLocaleString('id-ID')}</p>
          </div>
          <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl shadow-xl">
            <p className="text-[9px] text-green-500 uppercase tracking-widest mb-1 font-black">Unrealized</p>
            <p className={`text-lg font-black ${current.unrealized >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {current.unrealized >= 0 ? '+' : ''}Rp {current.unrealized.toLocaleString('id-ID')}
            </p>
          </div>
          <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl shadow-xl">
            <p className="text-[9px] text-white uppercase tracking-widest mb-1 font-black">Realized</p>
            <p className={`text-lg font-black ${current.realized >= 0 ? 'text-white' : 'text-red-400'}`}>
              {current.realized >= 0 ? '+' : ''}Rp {current.realized.toLocaleString('id-ID')}
            </p>
          </div>
        </div>

        {/* VIEW TOGGLE */}
        <div className="flex gap-1 p-1 bg-white/5 rounded-2xl border border-white/10 w-fit mb-8 shadow-inner">
          <button
            onClick={() => setViewMode('portfolio')}
            className={`px-5 py-2 rounded-xl text-[10px] font-black tracking-widest transition-all ${viewMode === 'portfolio' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-white'}`}
          >
            PORTFOLIO
          </button>
          <button
            onClick={() => setViewMode('analytics')}
            className={`px-5 py-2 rounded-xl text-[10px] font-black tracking-widest transition-all ${viewMode === 'analytics' ? 'bg-white/10 text-white' : 'text-gray-500 hover:text-white'}`}
          >
            ANALYTICS
          </button>
        </div>

        {viewMode === 'portfolio' && (<>

        {/* GROWTH CHART */}
        <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8 mb-8 shadow-2xl">
          <p className="text-[9px] font-black uppercase tracking-[0.4em] text-gray-500 mb-6">Portfolio Growth</p>
          {growthData.length > 1 ? (
            <EquityChart data={growthData} color={TAB_COLORS[activeTab]} height={220} />
          ) : (
            <div className="h-[220px] flex items-center justify-center text-gray-700 text-xs uppercase font-black tracking-widest opacity-40 italic">
              No trade history to display
            </div>
          )}
        </div>

        {/* ACTIVE POSITIONS */}
        <div className="mb-10">
          <h2 className="text-xs font-black font-mono uppercase tracking-[0.4em] text-gray-500 mb-4 flex items-center gap-4">
            <span className="w-8 h-px bg-white/10" />
            Posisi Aktif
            <span className="flex-1 h-px bg-white/10" />
            <span className="text-gray-700 normal-case tracking-normal">{current.assets.length} posisi</span>
          </h2>

          <div className="bg-white/[0.01] border border-white/5 rounded-3xl overflow-hidden shadow-2xl">
            <div className="overflow-x-auto -mx-2 sm:mx-0">
            <table className="min-w-full text-left font-mono">
              <thead>
                <tr className="border-b border-white/5 text-[9px] font-black text-gray-600 uppercase tracking-[0.4em] bg-white/[0.02]">
                  <th className="px-6 py-5">Instrument</th>
                  <th className="px-6 py-5 text-right">Avg Buy</th>
                  <th className="px-6 py-5 text-right">Harga Kini</th>
                  <th className="px-6 py-5 text-right">Invested</th>
                  <th className="px-6 py-5 text-right">Unrealized</th>
                  <th className="px-6 py-5">Strategi</th>
                  <th className="px-6 py-5 text-center">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {current.assets.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-8 py-24 text-center text-gray-700 italic text-[10px] uppercase font-black opacity-30">
                      Belum ada posisi aktif untuk {activeTab}
                    </td>
                  </tr>
                ) : (
                  current.assets.map((item: PortfolioItem) => (
                    <tr key={item.ticker} className="group hover:bg-white/[0.02] transition-all">
                      <td className="px-6 py-5">
                        <Link href={`/stocks/${item.ticker}`} className="block">
                          <span className="text-lg font-black text-white group-hover:text-blue-400 transition-colors block leading-none">{item.ticker}</span>
                          <span className="text-[9px] text-gray-600 uppercase font-black mt-1 block">{item.shares / 100} LOT</span>
                          {item.last_date && (
                            <span className="text-[8px] text-gray-700 font-mono block mt-0.5">data: {item.last_date}</span>
                          )}
                        </Link>
                      </td>
                      <td className="px-6 py-5 text-right text-xs font-mono text-gray-400">
                        Rp {item.avg_price?.toLocaleString('id-ID')}
                      </td>
                      <td className="px-6 py-5 text-right">
                        <span className="text-sm font-black font-mono text-white">
                          Rp {item.current_price?.toLocaleString('id-ID')}
                        </span>
                      </td>
                      <td className="px-6 py-5 text-right text-sm font-black text-blue-500/60">
                        Rp {item.cost_basis.toLocaleString('id-ID')}
                      </td>
                      <td className="px-6 py-5 text-right">
                        <div>
                          <span className={`text-sm font-black ${item.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {item.unrealized_pnl >= 0 ? '▲' : '▼'} Rp {Math.abs(item.unrealized_pnl).toLocaleString('id-ID')}
                          </span>
                          <span className={`block text-[9px] font-mono ${item.unrealized_pnl >= 0 ? 'text-green-400/60' : 'text-red-400/60'}`}>
                            {item.cost_basis > 0 ? ((item.unrealized_pnl / item.cost_basis) * 100).toFixed(2) : '0.00'}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <span className="text-[9px] font-black bg-white/5 px-2 py-1 rounded-full text-blue-400 uppercase">{item.strategy || 'MANUAL'}</span>
                      </td>
                      <td className="px-6 py-5 text-center">
                        {activeTab === 'USER' && (
                          <button
                            onClick={() => openSellModal(item.ticker, item.shares, item.current_price ?? 0, item.avg_price ?? 0)}
                            className="text-[9px] font-black px-4 py-1.5 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-all uppercase tracking-widest"
                          >
                            SELL
                          </button>
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

        {/* TRADE HISTORY */}
        <div className="mb-10">
          <h2 className="text-xs font-black font-mono uppercase tracking-[0.4em] text-gray-500 mb-4 flex items-center gap-4">
            <span className="w-8 h-px bg-white/10" />
            Trade History — {activeTab}
            <span className="flex-1 h-px bg-white/10" />
            <span className="text-gray-700 normal-case tracking-normal">{filteredHistory.length} transaksi</span>
          </h2>

          {/* FILTER BAR */}
          <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-4 mb-4 flex items-center gap-4 flex-wrap">
            <input
              type="text"
              placeholder="Cari ticker..."
              value={histSearch}
              onChange={e => setHistSearch(e.target.value)}
              className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500/50 w-48 placeholder:text-gray-600"
            />
            <div className="flex p-1 bg-white/5 rounded-xl border border-white/10 gap-0.5">
              {(['ALL', 'BUY', 'SELL'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setHistActionFilter(f)}
                  className={`px-4 py-1.5 rounded-xl text-[9px] font-black uppercase tracking-widest transition-all ${
                    histActionFilter === f
                      ? f === 'ALL' ? 'bg-blue-600 text-white' : f === 'BUY' ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
                      : 'text-gray-500 hover:text-white'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
            {(histSearch || histActionFilter !== 'ALL') && (
              <button
                onClick={() => { setHistSearch(''); setHistActionFilter('ALL'); }}
                className="text-[9px] font-black uppercase tracking-widest text-gray-600 hover:text-white transition-colors"
              >
                Reset
              </button>
            )}
            <span className="text-[9px] font-mono text-gray-700 ml-auto">{filteredHistory.length} / {history.length} transaksi</span>
            <button
              onClick={exportToCSV}
              disabled={filteredHistory.length === 0}
              title="Export ke CSV"
              className="text-[8px] font-black uppercase tracking-widest px-3 py-1.5 rounded-xl border border-white/10 text-gray-500 hover:text-white hover:border-white/30 transition-all disabled:opacity-30"
            >
              ↓ CSV
            </button>
          </div>

          <div className="bg-white/[0.01] border border-white/5 rounded-3xl overflow-hidden shadow-2xl">
            <div className="overflow-x-auto -mx-2 sm:mx-0">
            <table className="min-w-full text-left font-mono">
              <thead>
                <tr className="border-b border-white/5 text-[9px] font-black text-gray-600 uppercase tracking-[0.4em] bg-white/[0.02]">
                  <th className="px-6 py-5">Tanggal</th>
                  <th className="px-6 py-5">Ticker</th>
                  <th className="px-6 py-5 text-center">Aksi</th>
                  <th className="px-6 py-5 text-center">Lot</th>
                  <th className="px-6 py-5 text-right">Harga</th>
                  <th className="px-6 py-5 text-right">Total Nilai</th>
                  <th className="px-6 py-5 text-right">P&L</th>
                  <th className="px-6 py-5">Strategi</th>
                  <th className="px-6 py-5 text-xs text-gray-500 italic max-w-[160px]">Alasan</th>
                  <th className="px-6 py-5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.03]">
                {filteredHistory.length === 0 ? (
                  <tr>
                    <td colSpan={10} className="px-8 py-24 text-center text-gray-700 italic text-[10px] uppercase font-black opacity-30">
                      {history.length === 0 ? `Belum ada riwayat transaksi untuk ${activeTab}` : 'Tidak ada transaksi yang cocok dengan filter'}
                    </td>
                  </tr>
                ) : (
                  filteredHistory.map((t) => (
                    <tr
                      key={t.id}
                      onClick={() => router.push(`/portfolio/trade/${t.id}`)}
                      className="group hover:bg-white/[0.03] transition-all cursor-pointer"
                    >
                      <td className="px-6 py-4 text-xs text-gray-500">{t.date}</td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-black group-hover:text-blue-400 transition-colors">
                          {t.ticker}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className={`text-[9px] font-black px-3 py-1 rounded-full uppercase tracking-widest ${
                          t.action === 'BUY'
                            ? 'bg-green-500/10 text-green-400 border border-green-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                          {t.action}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center text-sm font-bold">{t.quantity}</td>
                      <td className="px-6 py-4 text-right text-sm font-mono">
                        Rp {t.price.toLocaleString('id-ID')}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className={`text-sm font-black font-mono ${t.action === 'BUY' ? 'text-red-400/70' : 'text-green-400/70'}`}>
                          {t.action === 'BUY' ? '-' : '+'}Rp {t.total_value.toLocaleString('id-ID')}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {t.pnl !== null ? (
                          <div>
                            <span className={`text-sm font-black font-mono ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                              {t.pnl >= 0 ? '+' : ''}Rp {Math.abs(t.pnl).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                            </span>
                            <span className={`block text-[9px] font-mono ${t.pnl_pct! >= 0 ? 'text-green-400/60' : 'text-red-400/60'}`}>
                              {t.pnl_pct! >= 0 ? '+' : ''}{t.pnl_pct?.toFixed(2)}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-gray-700 text-xs">—</span>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-[9px] font-black bg-white/5 px-2 py-1 rounded-full text-blue-400 uppercase">{t.strategy}</span>
                      </td>
                      <td className="px-6 py-4 text-xs text-gray-500 italic max-w-[160px] truncate" title={t.notes || ''}>
                        {t.notes || '—'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <span className="text-gray-700 group-hover:text-white transition-colors text-sm font-black">→</span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            </div>
          </div>
        </div>

        </>)}

        {viewMode === 'analytics' && (
          <div className="pb-20">
            {/* RISK METRICS */}
            <h2 className="text-xs font-black font-mono uppercase tracking-[0.4em] text-gray-500 mb-4 flex items-center gap-4">
              <span className="w-8 h-px bg-white/10" />Risk Metrics<span className="flex-1 h-px bg-white/10" />
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
              <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl">
                <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1 font-black">Win Rate</p>
                <p className={`text-2xl font-black ${winRate !== null && winRate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                  {winRate !== null ? `${winRate.toFixed(1)}%` : '—'}
                </p>
                <p className="text-[9px] text-gray-600 mt-1">{winCount} menang / {sellTrades.length} SELL</p>
              </div>
              <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl">
                <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1 font-black">Max Drawdown</p>
                <p className="text-2xl font-black text-red-400">
                  {maxDrawdownPct > 0 ? `-${maxDrawdownPct.toFixed(2)}%` : '—'}
                </p>
                <p className="text-[9px] text-gray-600 mt-1">dari puncak tertinggi</p>
              </div>
              <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl">
                <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1 font-black">Total Trades</p>
                <p className="text-2xl font-black text-white">{history.length}</p>
                <p className="text-[9px] text-gray-600 mt-1">{history.filter(t => t.action === 'BUY').length} BUY · {sellTrades.length} SELL</p>
              </div>
              <div className="bg-white/[0.02] border border-white/5 p-6 rounded-2xl">
                <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1 font-black">Realized P&L</p>
                <p className={`text-2xl font-black ${current.realized >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {current.realized >= 0 ? '+' : ''}Rp {Math.round(current.realized).toLocaleString('id-ID')}
                </p>
                <p className="text-[9px] text-gray-600 mt-1">dari transaksi SELL</p>
              </div>
            </div>

            {/* ALLOCATION + MONTHLY P&L */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8">
                <p className="text-[9px] font-black uppercase tracking-[0.4em] text-gray-500 mb-6">Alokasi Portofolio</p>
                {allocData.length === 0 ? (
                  <div className="h-40 flex items-center justify-center text-gray-700 text-xs uppercase font-black opacity-30 italic">Tidak ada posisi aktif</div>
                ) : (
                  <div className="flex flex-col md:flex-row items-center gap-8">
                    <svg viewBox="0 0 200 200" className="w-40 h-40 shrink-0">
                      {donutSegments.map(seg => (
                        <path
                          key={seg.ticker}
                          d={seg.pathD}
                          fill={seg.color}
                          opacity={donutHovered ? (donutHovered.ticker === seg.ticker ? 1 : 0.75) : 0.9}
                          cursor="pointer"
                          onMouseEnter={() => setDonutHovered({ ticker: seg.ticker, pct: seg.pct, value: seg.value })}
                          onMouseLeave={() => setDonutHovered(null)}
                        />
                      ))}
                      <circle cx="100" cy="100" r="40" fill="#050505" />
                      {donutHovered ? (
                        <>
                          <text x="100" y="93" textAnchor="middle" fill="white" fontSize="10" fontWeight="bold" fontFamily="monospace">
                            {donutHovered.ticker}
                          </text>
                          <text x="100" y="106" textAnchor="middle" fill="#22C55E" fontSize="9" fontFamily="monospace">
                            {donutHovered.pct.toFixed(1)}%
                          </text>
                        </>
                      ) : (
                        <>
                          <text x="100" y="97" textAnchor="middle" fill="white" fontSize="14" fontWeight="bold" fontFamily="monospace">
                            {current.assets.length}
                          </text>
                          <text x="100" y="111" textAnchor="middle" fill="#555" fontSize="8" fontFamily="monospace">STOCKS</text>
                        </>
                      )}
                    </svg>
                    <div className="flex-1 space-y-2.5 min-w-0">
                      {allocData.map(seg => (
                        <div key={seg.ticker} className="flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: seg.color }} />
                          <span className="text-xs font-black text-white shrink-0 w-16">{seg.ticker}</span>
                          <div className="flex-1 bg-white/5 rounded-full h-1.5 min-w-0">
                            <div className="h-1.5 rounded-full transition-all" style={{ width: `${seg.pct}%`, background: seg.color }} />
                          </div>
                          <span className="text-[9px] font-mono text-gray-500 shrink-0 w-10 text-right">{seg.pct.toFixed(1)}%</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="bg-white/[0.01] border border-white/5 rounded-3xl p-8">
                <p className="text-[9px] font-black uppercase tracking-[0.4em] text-gray-500 mb-6">P&L Bulanan</p>
                {monthlyRows.length === 0 ? (
                  <div className="h-40 flex items-center justify-center text-gray-700 text-xs uppercase font-black opacity-30 italic">Belum ada transaksi SELL</div>
                ) : (
                  <div className="space-y-2 max-h-72 overflow-y-auto custom-scrollbar pr-1">
                    {monthlyRows.map(([month, pnl]) => (
                      <div key={month} className="flex items-center gap-4 py-2 border-b border-white/[0.04] last:border-0">
                        <span className="text-xs font-black text-gray-400 shrink-0 w-16">{month}</span>
                        <div className="flex-1 bg-white/5 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.min(100, Math.abs(pnl) / maxMonthlyAbs * 100)}%` }}
                          />
                        </div>
                        <span className={`text-xs font-black font-mono shrink-0 w-36 text-right ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
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

      {/* SELL MODAL */}
      {sellModal.open && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-[#0f0f0f] border border-white/10 rounded-3xl p-8 w-full max-w-sm shadow-2xl">
            <h3 className="text-xl font-black mb-1">Jual <span className="text-red-400">{sellModal.ticker}</span></h3>
            <p className="text-gray-500 text-xs mb-6">Posisi: {sellModal.maxLots} lot tersedia</p>

            <div className="mb-6">
              <label className="text-[9px] font-black uppercase tracking-widest text-gray-500 block mb-2">Jumlah Lot</label>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => setSellQty(q => Math.max(1, q - 1))}
                  className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 font-black text-lg hover:bg-white/10 transition-all"
                >
                  −
                </button>
                <input
                  type="number"
                  value={sellQty}
                  min={1}
                  max={sellModal.maxLots}
                  onChange={(e) => setSellQty(Math.min(sellModal.maxLots, Math.max(1, parseInt(e.target.value) || 1)))}
                  className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-3 text-center font-black text-xl text-red-400 focus:outline-none focus:border-red-500/50"
                />
                <button
                  onClick={() => setSellQty(q => Math.min(sellModal.maxLots, q + 1))}
                  className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 font-black text-lg hover:bg-white/10 transition-all"
                >
                  +
                </button>
              </div>
              <button
                onClick={() => setSellQty(sellModal.maxLots)}
                className="mt-2 text-[9px] text-red-400/60 hover:text-red-400 font-black uppercase tracking-widest transition-colors"
              >
                Jual semua ({sellModal.maxLots} lot)
              </button>
            </div>

            {/* P&L Preview */}
            <div className="mb-6 bg-white/[0.02] border border-white/5 rounded-2xl p-4 space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">Estimasi Dana Masuk</span>
                <span className="text-sm font-black font-mono text-white">
                  Rp {(sellModal.currentPrice * sellQty * 100).toLocaleString('id-ID')}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">Est. P&amp;L</span>
                {(() => {
                  const pnl = (sellModal.currentPrice - sellModal.avgPrice) * sellQty * 100;
                  const isProfit = pnl >= 0;
                  return (
                    <span className={`text-sm font-black font-mono ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                      {isProfit ? '+' : ''}Rp {Math.abs(pnl).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                    </span>
                  );
                })()}
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={() => setSellModal({ open: false, ticker: '', maxLots: 0, currentPrice: 0, avgPrice: 0 })}
                className="flex-1 py-3 rounded-xl border border-white/10 text-[10px] font-black uppercase tracking-widest text-gray-500 hover:text-white hover:border-white/20 transition-all"
              >
                Batal
              </button>
              <button
                onClick={handleSell}
                disabled={isSelling}
                className="flex-1 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white text-[10px] font-black uppercase tracking-widest transition-all disabled:opacity-50"
              >
                {isSelling ? 'Menjual...' : `Jual ${sellQty} Lot`}
              </button>
            </div>
          </div>
        </div>
      )}
      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
      `}</style>
    </main>
  );
}
