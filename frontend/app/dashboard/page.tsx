'use client';

import { useEffect, useRef, useState } from 'react';
import { api, Stock, MultiPortfolioResponse, OHLCV } from '@/lib/api';
import Link from 'next/link';
import { useToast } from '@/components/Toast';
import dynamic from 'next/dynamic';

const StockChart = dynamic(() => import("@/components/StockChart"), { ssr: false });

interface Signal {
  ticker: string;
  name: string;
  type: string;
  strategies: string[];
  max_strength: number;
  date: string;
  market_cap: number | null;
}

interface SyncStatus {
  is_running: boolean;
  phase: string;
  phase_label: string;
  total: number;
  done: number;
  current: string;
  errors: number;
  message: string;
}

export default function Dashboard() {
  useEffect(() => { document.title = 'Dashboard — IDXAnalyst'; }, []);
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [portfolio, setPortfolio] = useState<MultiPortfolioResponse | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [ihsgData, setIhsgData] = useState<OHLCV[]>([]);
  const [loading, setLoading] = useState(true);
  const [isScanning, setIsRunningScan] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const syncPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set());
  const [showWatchlistOnly, setShowWatchlistOnly] = useState(false);

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

  useEffect(() => {
    const saved = localStorage.getItem('watchlist');
    if (saved) {
      try { setWatchlist(new Set(JSON.parse(saved))); } catch {}
    }
  }, []);

  const toggleWatchlist = (e: React.MouseEvent, ticker: string) => {
    e.preventDefault();
    e.stopPropagation();
    setWatchlist(prev => {
      const next = new Set(prev);
      next.has(ticker) ? next.delete(ticker) : next.add(ticker);
      localStorage.setItem('watchlist', JSON.stringify([...next]));
      return next;
    });
  };

  const loadData = async () => {
    try {
      const [stocksData, portfolioData, ihsg, signalsData] = await Promise.all([
        api.getStocks(),
        api.getPortfolio(),
        api.getOHLCV('^JKSE'),
        api.getSignals()
      ]);
      setStocks(stocksData);
      setPortfolio(portfolioData);
      setIhsgData(ihsg.data || []);
      setSignals(signalsData || []);
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

  useEffect(() => {
    return () => { if (syncPollRef.current) clearInterval(syncPollRef.current); };
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

  const handleSync = async () => {
    if (syncPollRef.current) clearInterval(syncPollRef.current);
    setIsSyncing(true);
    setSyncStatus(null);
    try {
      await api.refreshData();

      syncPollRef.current = setInterval(async () => {
        try {
          const status = await api.getSyncStatus();
          setSyncStatus(status);
          if (!status.is_running) {
            clearInterval(syncPollRef.current!);
            syncPollRef.current = null;
            setIsSyncing(false);
            await loadData();
            // Auto-hide done toast setelah 4 detik
            setTimeout(() => setSyncStatus(null), 4000);
          }
        } catch {
          clearInterval(syncPollRef.current!);
          syncPollRef.current = null;
          setIsSyncing(false);
        }
      }, 1000);
    } catch (err) {
      toast('Sync gagal. Periksa koneksi backend.', 'error');
      setIsSyncing(false);
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
    (!showWatchlistOnly || watchlist.has(s.ticker)) &&
    (s.ticker.toLowerCase().includes(searchTerm.toLowerCase()) || s.name.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const currentIhsg = ihsgData[ihsgData.length - 1]?.close || 0;
  const prevIhsg = ihsgData[ihsgData.length - 2]?.close || 0;
  const ihsgChange = currentIhsg - prevIhsg;

  const dataLastDate = stocks.length > 0
    ? stocks.filter(s => s.last_date).map(s => s.last_date!).sort().at(-1) ?? null
    : null;

  const isDataStale = (() => {
    if (!dataLastDate) return false;
    const last = new Date(dataLastDate);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - last.getTime()) / (1000 * 60 * 60 * 24));
    return diffDays >= 2; // stale if 2+ days old (accounts for weekends)
  })();

  if (loading && stocks.length === 0) return <div className="min-h-screen bg-[#050505] flex items-center justify-center animate-pulse text-blue-500 font-mono tracking-widest uppercase text-xs">Initializing Terminal...</div>;

  return (
    <main className="min-h-screen bg-[#050505] text-white p-4 md:p-8 pt-24 md:pt-28">
      <div className="max-w-7xl mx-auto">

        {isDataStale && (
          <div className="bg-amber-500/10 border border-amber-500/20 rounded-2xl px-5 py-3 mb-6 flex items-center gap-3">
            <span className="text-amber-400 text-sm">⚠</span>
            <span className="text-[10px] font-black text-amber-400 uppercase tracking-widest">
              Data terakhir: {dataLastDate} — Sync diperlukan
            </span>
            <span className="text-[9px] font-mono text-amber-400/60 ml-auto">
              Klik SYNC DATA untuk memperbarui
            </span>
          </div>
        )}

        {/* TOP SECTION: IHSG & AI SIGNALS */}
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 mb-10 text-left">
          <div className="xl:col-span-7 bg-white/[0.02] border border-white/10 rounded-[2.5rem] p-8 shadow-2xl relative overflow-hidden group">
            <div className="flex justify-between items-start mb-6">
               <div>
                  <p className="text-[9px] font-black text-blue-500 uppercase tracking-[0.4em] mb-1">Jakarta Composite</p>
                  <h1 className="text-3xl font-black">IHSG INDEX</h1>
               </div>
               <div className="text-right">
                  <p className="text-2xl font-mono font-bold">Rp {currentIhsg.toLocaleString('id-ID')}</p>
                  <p className={`text-xs font-mono font-bold ${ihsgChange >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {ihsgChange >= 0 ? '▲' : '▼'} {Math.abs((ihsgChange/prevIhsg)*100).toFixed(2)}%
                  </p>
               </div>
            </div>
            <div className="h-56">
               <StockChart data={ihsgData} height={220} transparent={true} />
            </div>
          </div>

          <div className="xl:col-span-5 flex flex-col gap-6">
             <div className="bg-gradient-to-br from-teal-600/10 to-transparent border border-teal-500/20 rounded-[2.5rem] p-8 flex-1 flex flex-col">
                <div className="flex justify-between items-center mb-3">
                   <h2 className="text-[10px] font-black text-teal-400 uppercase tracking-[0.4em]">AI Intelligence Signals</h2>
                   <div className="flex gap-2">
                     <button onClick={handleSync} disabled={isSyncing} className="bg-white/10 hover:bg-white/20 text-white px-3 py-1.5 rounded-full text-[8px] font-black tracking-widest uppercase disabled:opacity-50 transition-all">
                       {isSyncing ? 'SYNCING...' : '⟳ SYNC'}
                     </button>
                     <button onClick={handleScan} disabled={isScanning} className="bg-teal-500 hover:bg-teal-400 text-black px-4 py-1.5 rounded-full text-[8px] font-black tracking-widest uppercase disabled:opacity-50 transition-all">
                       {isScanning ? 'SCANNING...' : 'AUTO SCAN'}
                     </button>
                   </div>
                </div>
                <div className="flex gap-1.5 mb-4">
                  {MARKET_CAP_FILTERS.map(f => (
                    <button
                      key={f.value}
                      onClick={() => setMinMarketCap(f.value)}
                      className={`text-[7px] font-black uppercase tracking-widest px-2.5 py-1 rounded-full transition-all ${
                        minMarketCap === f.value
                          ? 'bg-teal-500 text-black'
                          : 'bg-white/10 text-gray-400 hover:bg-white/20'
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
                <div className="flex-1 overflow-y-auto max-h-[180px] custom-scrollbar pr-2">
                   {filteredSignals.length === 0 ? (
                     <div className="h-full flex flex-col items-center justify-center opacity-30 italic text-xs">
                        <p>{signals.length === 0 ? 'No active signals found.' : 'No signals match this filter.'}</p>
                     </div>
                   ) : (
                     <div className="space-y-3">
                        {filteredSignals.map((sig, i) => (
                          <Link href={`/stocks/${sig.ticker}`} key={i} className="block group bg-white/5 border border-white/5 hover:border-teal-500/30 p-4 rounded-2xl transition-all">
                             <div className="flex justify-between items-center mb-1">
                                <div>
                                  <span className="text-sm font-black group-hover:text-teal-400 transition-colors">{sig.ticker}</span>
                                  {sig.name && <p className="text-[7px] text-gray-600 font-mono truncate w-28">{sig.name}</p>}
                                </div>
                                <span className="text-[8px] font-black bg-teal-500 text-black px-2 py-0.5 rounded uppercase tracking-tighter">{sig.max_strength}%</span>
                             </div>
                             <div className="flex flex-wrap gap-1 mt-1.5">
                                {sig.strategies.map((strategy, j) => (
                                  <span key={j} className="text-[7px] font-bold bg-white/10 text-gray-300 px-1.5 py-0.5 rounded uppercase tracking-tight">{strategy}</span>
                                ))}
                             </div>
                          </Link>
                        ))}
                     </div>
                   )}
                </div>
             </div>
          </div>
        </div>

        {/* STATS */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10 text-left text-left">
          <div className="col-span-1 md:col-span-2 p-8 rounded-3xl bg-white/[0.03] border border-white/5 flex flex-col justify-center">
             <p className="text-gray-500 text-[10px] font-mono uppercase tracking-[0.3em] mb-2">Assets Tracked</p>
             <p className="text-5xl font-black font-mono">{stocks.length}</p>
          </div>
          <div className="p-8 rounded-3xl bg-white/[0.02] border border-white/5 flex flex-col justify-center">
             <p className="text-gray-600 text-[9px] font-mono uppercase mb-4 tracking-widest font-bold text-gray-500">Total Unrealized</p>
             <p className={`text-2xl font-black font-mono ${totalUnrealized >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                Rp {totalUnrealized.toLocaleString('id-ID')}
             </p>
          </div>
          <div className="p-8 rounded-3xl bg-white/[0.02] border border-white/5 flex flex-col justify-center text-right">
             <p className="text-gray-600 text-[9px] font-mono uppercase mb-2 tracking-widest font-bold">Positions</p>
             <div className="flex flex-col gap-1">
                <span className="text-xs font-bold text-blue-400 font-mono">User: {portfolio?.USER.assets.length || 0}</span>
                <span className="text-xs font-bold text-teal-400 font-mono">Gemini: {portfolio?.GEMINI.assets.length || 0}</span>
                <span className="text-xs font-bold text-purple-400 font-mono">Claude: {portfolio?.CLAUDE.assets.length || 0}</span>
             </div>
          </div>
        </div>

        {/* MARKET GRID */}
        <div className="flex flex-col md:flex-row justify-between items-center mb-8 gap-4 px-2">
           <div className="flex items-center gap-4">
             <h2 className="text-xs font-black font-mono uppercase tracking-[0.4em] text-gray-500">Market Terminal</h2>
             <button
               onClick={() => setShowWatchlistOnly(v => !v)}
               className={`text-[9px] font-black uppercase tracking-widest px-3 py-1.5 rounded-full transition-all ${showWatchlistOnly ? 'bg-yellow-400 text-black' : 'bg-white/5 text-gray-500 hover:bg-white/10'}`}
             >
               ★ Watchlist {showWatchlistOnly && `(${watchlist.size})`}
             </button>
           </div>
           <input
              type="text"
              placeholder="Search assets..."
              className="bg-white/5 border border-white/10 rounded-xl px-6 py-3 text-xs focus:outline-none focus:border-blue-500/50 w-full md:w-80 shadow-inner"
              onChange={(e) => setSearchTerm(e.target.value)}
            />
        </div>
        
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pb-20 px-2 text-left text-left text-left">
          {filteredStocks.map((stock) => {
            const hasUser = portfolio?.USER.assets.some(p => p.ticker === stock.ticker);
            const hasGemini = portfolio?.GEMINI.assets.some(p => p.ticker === stock.ticker);
            const hasClaude = portfolio?.CLAUDE.assets.some(p => p.ticker === stock.ticker);
            
            return (
              <Link key={stock.ticker} href={`/stocks/${stock.ticker}`} className="group p-6 rounded-3xl bg-white/[0.02] border border-white/5 hover:border-blue-500/30 hover:bg-white/[0.04] transition-all relative overflow-hidden shadow-sm">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-2xl font-black group-hover:text-blue-400 transition-colors leading-none mb-1">{stock.ticker}</h3>
                    <p className="text-[9px] text-gray-600 font-mono uppercase truncate w-32">{stock.name}</p>
                  </div>
                  <div className="flex flex-col gap-1 items-end">
                    <button
                      onClick={(e) => toggleWatchlist(e, stock.ticker)}
                      className={`text-base leading-none transition-colors ${watchlist.has(stock.ticker) ? 'text-yellow-400' : 'text-gray-700 hover:text-yellow-400'}`}
                      title={watchlist.has(stock.ticker) ? 'Remove from watchlist' : 'Add to watchlist'}
                    >★</button>
                    {hasUser && <span className="px-2 py-0.5 rounded bg-blue-500 text-black text-[7px] font-black uppercase">User</span>}
                    {hasGemini && <span className="px-2 py-0.5 rounded bg-teal-500 text-black text-[7px] font-black uppercase">Gemini</span>}
                    {hasClaude && <span className="px-2 py-0.5 rounded bg-purple-500 text-white text-[7px] font-black uppercase tracking-tighter">Claude</span>}
                  </div>
                </div>
                <div className="flex justify-between items-end border-t border-white/[0.03] pt-4">
                   <div>
                      <p className="text-[8px] font-mono text-gray-700 uppercase mb-1 font-black">Quote Value</p>
                      <p className="text-sm font-bold font-mono">Rp {stock.last_price?.toLocaleString('id-ID')}</p>
                   </div>
                   <div className="flex flex-col items-end gap-1">
                      {stock.change_pct != null && (
                        <span className={`text-[10px] font-black font-mono ${stock.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {stock.change_pct >= 0 ? '▲' : '▼'} {Math.abs(stock.change_pct).toFixed(2)}%
                        </span>
                      )}
                      {stock.last_date && (
                        <p className="text-[8px] font-mono text-gray-700">{stock.last_date}</p>
                      )}
                   </div>
                </div>
              </Link>
            );
          })}
        </div>
      </div>
      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
      `}</style>

      {/* Sync Progress Toast */}
      {isSyncing && (
        <div className="fixed bottom-6 right-6 z-50 w-80 bg-[#0d0d0d] border border-white/10 rounded-2xl p-5 shadow-2xl">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
              <span className="text-[9px] font-black text-teal-400 uppercase tracking-widest">
                {syncStatus?.phase_label || 'Memulai sync...'}
              </span>
            </div>
            {syncStatus && syncStatus.total > 0 && (
              <span className="text-[9px] font-mono text-gray-500">
                {syncStatus.done} / {syncStatus.total}
              </span>
            )}
          </div>

          {/* Progress bar */}
          <div className="w-full bg-white/5 rounded-full h-1.5 mb-3">
            <div
              className="bg-teal-500 h-1.5 rounded-full transition-all duration-500"
              style={{
                width: syncStatus && syncStatus.total > 0
                  ? `${Math.round((syncStatus.done / syncStatus.total) * 100)}%`
                  : '5%'
              }}
            />
          </div>

          <div className="flex items-center justify-between">
            {syncStatus?.current ? (
              <p className="text-[8px] font-mono text-gray-600 truncate flex-1">
                <span className="text-gray-500">→</span> {syncStatus.current}
              </p>
            ) : (
              <p className="text-[8px] font-mono text-gray-700 italic">Menghubungi server...</p>
            )}
            {syncStatus && syncStatus.errors > 0 && (
              <span className="text-[8px] font-mono text-red-500 ml-2 shrink-0">
                {syncStatus.errors} error
              </span>
            )}
          </div>
        </div>
      )}

      {/* Sync Done Toast — tampil sebentar setelah selesai */}
      {!isSyncing && syncStatus?.phase === 'done' && (
        <div className="fixed bottom-6 right-6 z-50 w-80 bg-[#0d0d0d] border border-teal-500/30 rounded-2xl p-5 shadow-2xl">
          <div className="flex items-center gap-2">
            <span className="text-teal-400 text-sm">✓</span>
            <span className="text-[9px] font-black text-teal-400 uppercase tracking-widest">Sync Selesai</span>
          </div>
          <p className="text-[8px] font-mono text-gray-500 mt-1">{syncStatus.message}</p>
        </div>
      )}
    </main>
  );
}
