'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, Stock, PortfolioItem, OHLCV } from '@/lib/api';
import { createChartSync } from '@/lib/chartSync';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import strategyRegistry from '../../../strategies_local/registry.json';
import { useToast } from '@/components/Toast';

const StockChart = dynamic(() => import("@/components/StockChart"), { ssr: false });
const IndicatorSubChart = dynamic(() => import("@/components/IndicatorSubChart"), { ssr: false });

type SubPanelType = 'rsi' | 'macd' | 'stoch' | 'volume';
type Timeframe = '1M' | '3M' | '6M' | '1Y' | 'ALL';

type StrategyConfig = {
  ma20: boolean; ma50: boolean; ema12: boolean;
  ma200: boolean; ema26: boolean; bb: boolean;
  subPanel: SubPanelType | null;
};

const STRATEGY_INDICATORS: Record<string, StrategyConfig> = {
  'manual-intuition':    { ma20: true,  ma50: true,  ema12: false, ma200: false, ema26: false, bb: false, subPanel: null    },
  'rsi-reversion':       { ma20: false, ma50: false, ema12: false, ma200: false, ema26: false, bb: false, subPanel: 'rsi'   },
  'triple-confirmation': { ma20: true,  ma50: false, ema12: false, ma200: false, ema26: false, bb: false, subPanel: 'macd'  },
  'volatility-sniper':   { ma20: false, ma50: false, ema12: false, ma200: false, ema26: false, bb: true,  subPanel: 'stoch' },
  'institutional-trend': { ma20: false, ma50: false, ema12: true,  ma200: true,  ema26: true,  bb: false, subPanel: null    },
  'exhaustion-play':     { ma20: false, ma50: false, ema12: false, ma200: false, ema26: false, bb: true,  subPanel: 'rsi'   },
  'trend-accelerator':   { ma20: false, ma50: true,  ema12: false, ma200: false, ema26: false, bb: false, subPanel: 'macd'  },
  'pure-momentum':       { ma20: false, ma50: false, ema12: true,  ma200: false, ema26: true,  bb: false, subPanel: 'macd'  },
  'defensive-bull':      { ma20: false, ma50: true,  ema12: false, ma200: true,  ema26: false, bb: false, subPanel: 'rsi'   },
  'stoch-rsi-hybrid':    { ma20: false, ma50: false, ema12: false, ma200: false, ema26: false, bb: false, subPanel: 'stoch' },
  'ma-cross':            { ma20: true,  ma50: true,  ema12: false, ma200: false, ema26: false, bb: false, subPanel: null    },
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
  if (!v) return "text-gray-500";
  if (v < 30) return "text-green-400";
  if (v > 70) return "text-red-400";
  return "text-blue-400";
}

function fmt(v: number | null) {
  if (v === null || v === undefined) return "-";
  return v.toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

export default function TradingTerminalPage() {
  const params = useParams();
  const router = useRouter();
  const ticker = params?.ticker as string;

  useEffect(() => {
    if (ticker) document.title = `${ticker} — IDXAnalyst`;
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
  const [mlTraining, setMlTraining] = useState(false);

  // Professional Order State
  const [orderSide, setOrderSide] = useState<'BUY' | 'SELL'>('BUY');
  const [tradeQty, setTradeQty] = useState(1);
  const [isTrading, setIsTrading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  // Watchlist state
  const [watchlist, setWatchlist] = useState<Set<string>>(new Set());

  // Sidebar sort state
  const [sidebarSort, setSidebarSort] = useState<'default' | 'change_asc' | 'change_desc'>('default');
  
  // Discipline Fields
  const [selectedStrategy, setSelectedStrategy] = useState('manual-intuition');
  const [reasoning, setReasoning] = useState('');

  // Shared time scale sync between price chart and indicator sub-panels
  const chartSync = useRef(createChartSync());

  // Chart Visibility State
  const [showMA20, setShowMA20] = useState(true);
  const [showMA50, setShowMA50] = useState(true);
  const [showMA200, setShowMA200] = useState(false);
  const [showEMA12, setShowEMA12] = useState(false);
  const [showEMA26, setShowEMA26] = useState(false);
  const [showBB, setShowBB] = useState(false);
  const [activeSubPanel, setActiveSubPanel] = useState<SubPanelType | null>(null);
  const [timeframe, setTimeframe] = useState<Timeframe>('1Y');

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
      // Jika model sudah ada, langsung ambil prediksi
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

  const handleMlTrain = async () => {
    setMlTraining(true);
    setMlResult(null);
    try {
      const res = await api.trainMlModel(ticker);
      if (res.status === 'trained') {
        setMlStatus({ trained: true, trained_at: new Date().toISOString(), accuracy: res.accuracy, auc: res.auc });
        setMlLoading(true);
        api.getMlPrediction(ticker).then(setMlResult).finally(() => setMlLoading(false));
      } else {
        setMlResult({ status: 'error', message: res.message });
      }
    } catch {
      setMlResult({ status: 'error', message: 'Gagal menghubungi server' });
    } finally {
      setMlTraining(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-apply indicators when strategy changes
  useEffect(() => {
    const cfg = STRATEGY_INDICATORS[selectedStrategy];
    if (!cfg) return;
    setShowMA20(cfg.ma20);
    setShowMA50(cfg.ma50);
    setShowMA200(cfg.ma200);
    setShowEMA12(cfg.ema12);
    setShowEMA26(cfg.ema26);
    setShowBB(cfg.bb);
    setActiveSubPanel(cfg.subPanel);
  }, [selectedStrategy]);

  const handleTrade = async () => {
    if (!ticker) return;
    if (orderSide === 'BUY' && !reasoning) {
        toast("Harap masukkan alasan beli!", 'error');
        return;
    }

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
  const filteredStocks = stocks
    .filter(s => s.ticker !== '^JKSE' && s.ticker.toLowerCase().includes(searchTerm.toLowerCase()))
    .sort((a, b) => {
      if (sidebarSort === 'change_desc') return (b.change_pct ?? -999) - (a.change_pct ?? -999);
      if (sidebarSort === 'change_asc') return (a.change_pct ?? 999) - (b.change_pct ?? 999);
      return 0;
    });
  const currentStockInfo = stocks.find(s => s.ticker === ticker);

  const displayedOhlcv = (() => {
    if (timeframe === 'ALL' || ohlcv.length === 0) return ohlcv;
    const months = { '1M': 1, '3M': 3, '6M': 6, '1Y': 12 }[timeframe];
    const cutoff = new Date();
    cutoff.setMonth(cutoff.getMonth() - months);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return ohlcv.filter(d => d.date >= cutoffStr);
  })();

  return (
    <div className="flex flex-col md:flex-row h-screen bg-[#050505] text-white overflow-hidden pt-16">
      {/* Sidebar: Market Watch */}
      <aside className="hidden md:flex w-64 border-r border-white/10 flex-col bg-[#0a0a0a] shrink-0">
        <div className="p-4 border-b border-white/10">
          <div className="flex items-center gap-2 mb-4 text-left">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-[10px] text-black shadow-lg shadow-blue-600/20">IX</div>
            <span className="text-xs font-black tracking-widest uppercase text-blue-500">Market Hub</span>
          </div>
          <input
            type="text"
            placeholder="Quick search..."
            className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs focus:outline-none focus:border-blue-500/50"
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <div className="flex items-center gap-1 mt-2">
            <span className="text-[8px] text-gray-700 font-mono uppercase tracking-widest">Sort:</span>
            {[
              { val: 'default' as const, label: 'DEF' },
              { val: 'change_desc' as const, label: '▲%' },
              { val: 'change_asc' as const, label: '▼%' },
            ].map(opt => (
              <button
                key={opt.val}
                onClick={() => setSidebarSort(opt.val)}
                className={`text-[8px] font-black px-2 py-0.5 rounded transition-colors ${sidebarSort === opt.val ? 'bg-blue-600/20 text-blue-400' : 'text-gray-700 hover:text-gray-400'}`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto custom-scrollbar">
          {filteredStocks.map(stock => (
            <div
              key={stock.ticker}
              onClick={() => router.push(`/stocks/${stock.ticker}`)}
              role="button"
              tabIndex={0}
              className={`w-full p-4 flex justify-between items-center hover:bg-white/5 transition-all border-b border-white/[0.02] cursor-pointer ${ticker === stock.ticker ? 'bg-blue-600/10 border-r-4 border-r-blue-500' : ''}`}
            >
              <div className="text-left">
                <p className={`text-sm font-black ${ticker === stock.ticker ? 'text-blue-400' : 'text-gray-300'}`}>{stock.ticker}</p>
                <p className="text-[9px] text-gray-600 uppercase truncate w-24">{stock.name}</p>
              </div>
              <button
                onClick={(e) => toggleWatchlist(e, stock.ticker)}
                className="text-[10px] px-1 transition-colors"
                style={{ color: watchlist.has(stock.ticker) ? '#F59E0B' : 'rgba(255,255,255,0.1)' }}
              >
                ★
              </button>
              <div className="text-right text-xs font-mono font-bold">
                Rp {stock.last_price?.toLocaleString('id-ID')}
                {stock.change_pct != null && (
                  <span className={`text-[8px] font-mono block ${stock.change_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
        <Link href="/dashboard" className="p-4 text-[10px] text-gray-500 hover:text-white text-center border-t border-white/10 uppercase tracking-widest font-black bg-black/40">
          Exit Terminal
        </Link>
      </aside>

      {/* Main Trading Area */}
      <main className="flex-1 flex flex-col overflow-hidden bg-gradient-to-br from-[#050505] to-black">
        {/* Mobile stock selector — visible only on small screens */}
        <div className="md:hidden px-4 pt-3 pb-2 border-b border-white/10 bg-[#0a0a0a]">
          <select
            value={ticker}
            onChange={e => router.push(`/stocks/${e.target.value}`)}
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none"
          >
            {filteredStocks.map(s => (
              <option key={s.ticker} value={s.ticker} className="bg-[#0a0a0a]">
                {s.ticker} — {s.name || ''}
              </option>
            ))}
          </select>
        </div>
        {/* Top Header */}
        <header className="h-auto md:h-24 border-b border-white/10 bg-[#0a0a0a]/80 backdrop-blur-md flex flex-col md:flex-row items-start md:items-center justify-between px-4 md:px-8 py-4 md:py-0 shrink-0 gap-4 md:gap-0">
          <div className="flex items-center gap-8">
            <div className="text-left">
              <h1 className="text-4xl font-black tracking-tighter leading-none mb-1">{ticker}</h1>
              <p className="text-gray-600 text-[10px] font-mono tracking-[0.3em] uppercase">{currentStockInfo?.sector || 'UNKNOWN SECTOR'}</p>
            </div>
            <div className="h-10 w-px bg-white/10" />
            <div className="flex flex-col text-left">
              <span className="text-2xl font-mono font-bold text-blue-400 italic">Rp {latestPrice.toLocaleString('id-ID')}</span>
              <span className="text-[9px] text-gray-500 font-mono uppercase tracking-widest">Live Market Price</span>
            </div>
          </div>

          {/* DISCIPLINED TRADE PANEL */}
          <div className="flex flex-wrap items-center gap-4 bg-white/5 p-3 rounded-2xl border border-white/10 shadow-2xl w-full md:w-auto">
            <div className="flex flex-col gap-2">
               <div className="flex items-center gap-2">
                  <select 
                    value={selectedStrategy}
                    onChange={(e) => setSelectedStrategy(e.target.value)}
                    className="bg-black/40 border border-white/10 rounded-lg px-2 py-1 text-[9px] font-bold text-blue-400 uppercase outline-none"
                  >
                     <option value="manual-intuition">Manual Intuition</option>
                     {strategyRegistry.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                  <input 
                    type="text" 
                    placeholder="Reason for buying..." 
                    value={reasoning}
                    onChange={(e) => setReasoning(e.target.value)}
                    className="bg-black/40 border border-white/10 rounded-lg px-3 py-1.5 text-[10px] w-48 focus:border-blue-500/50 outline-none"
                  />
               </div>
               <div className="flex items-center gap-2">
                  <input 
                    type="number" 
                    value={tradeQty} 
                    onChange={(e) => setTradeQty(Math.max(1, parseInt(e.target.value) || 1))}
                    className="bg-black/60 border border-white/20 rounded-lg px-3 py-1.5 text-xs w-16 text-center font-bold text-blue-400 focus:outline-none"
                  />
                  <button onClick={() => setOrderSide('BUY')} className={`text-[8px] font-black px-3 py-1.5 rounded ${orderSide === 'BUY' ? 'bg-green-600 text-white' : 'bg-white/5 text-gray-500'}`}>BUY</button>
                  <button onClick={() => setOrderSide('SELL')} className={`text-[8px] font-black px-3 py-1.5 rounded ${orderSide === 'SELL' ? 'bg-red-600 text-white' : 'bg-white/5 text-gray-500'}`}>SELL</button>
                  <button onClick={handleTrade} disabled={isTrading} className="ml-2 bg-white text-black text-[9px] font-black px-6 py-1.5 rounded-lg hover:bg-blue-400 transition-all uppercase tracking-widest disabled:opacity-50">
                    {isTrading ? '...' : 'EXECUTE'}
                  </button>
               </div>
            </div>
            <div className="flex flex-col px-6 border-l border-white/10 text-right">
              <span className="text-[9px] text-gray-500 font-mono uppercase">Your Position</span>
              <span className="text-sm font-black text-blue-400 font-mono leading-none mt-1">{portfolio ? `${portfolio.shares / 100} Lot` : '0 Lot'}</span>
            </div>
          </div>
        </header>

        {/* Workspace */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 custom-scrollbar">
           <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
              <div className="flex gap-2 flex-wrap items-center">
                {/* Price overlay toggles */}
                {[
                  { label: "MA 20",  state: showMA20,  toggle: () => setShowMA20(!showMA20),   color: "border-yellow-500/50 text-yellow-500" },
                  { label: "MA 50",  state: showMA50,  toggle: () => setShowMA50(!showMA50),   color: "border-purple-500/50 text-purple-500" },
                  { label: "MA 200", state: showMA200, toggle: () => setShowMA200(!showMA200), color: "border-orange-500/50 text-orange-500" },
                  { label: "EMA 12", state: showEMA12, toggle: () => setShowEMA12(!showEMA12), color: "border-blue-400/50 text-blue-400"     },
                  { label: "EMA 26", state: showEMA26, toggle: () => setShowEMA26(!showEMA26), color: "border-cyan-400/50 text-cyan-400"     },
                  { label: "BB",     state: showBB,    toggle: () => setShowBB(!showBB),       color: "border-pink-500/50 text-pink-500"     },
                ].map(({ label, state, toggle, color }) => (
                  <button
                    key={label}
                    onClick={toggle}
                    className={`text-[9px] font-black tracking-widest uppercase px-4 py-2 rounded-xl border transition-all ${
                      state ? `${color} bg-white/5` : "border-white/5 text-gray-700 hover:text-gray-500"
                    }`}
                  >
                    {label}
                  </button>
                ))}
                <div className="w-px h-6 bg-white/10 mx-1" />
                {/* Oscillator sub-panel toggles */}
                {([
                  { label: "RSI",   panel: 'rsi'    as SubPanelType, color: "border-amber-400/50 text-amber-400"    },
                  { label: "MACD",  panel: 'macd'   as SubPanelType, color: "border-blue-400/50 text-blue-400"      },
                  { label: "STOCH", panel: 'stoch'  as SubPanelType, color: "border-emerald-400/50 text-emerald-400" },
                  { label: "VOL",   panel: 'volume' as SubPanelType, color: "border-violet-400/50 text-violet-400"  },
                ] as { label: string; panel: SubPanelType; color: string }[]).map(({ label, panel, color }) => (
                  <button
                    key={label}
                    onClick={() => setActiveSubPanel(p => p === panel ? null : panel)}
                    className={`text-[9px] font-black tracking-widest uppercase px-4 py-2 rounded-xl border transition-all ${
                      activeSubPanel === panel ? `${color} bg-white/5` : "border-white/5 text-gray-700 hover:text-gray-500"
                    }`}
                  >
                    {label}
                  </button>
                ))}
                <div className="w-px h-6 bg-white/10 mx-1" />
                {(['1M', '3M', '6M', '1Y', 'ALL'] as Timeframe[]).map(tf => (
                  <button
                    key={tf}
                    onClick={() => setTimeframe(tf)}
                    className={`text-[9px] font-black tracking-widest uppercase px-4 py-2 rounded-xl border transition-all ${
                      timeframe === tf
                        ? 'border-white/30 bg-white/10 text-white'
                        : 'border-white/5 text-gray-600 hover:text-gray-400'
                    }`}
                  >
                    {tf}
                  </button>
                ))}
              </div>
              
              <div className="grid grid-cols-3 sm:grid-cols-3 gap-3 p-4 bg-white/[0.02] border border-white/5 rounded-2xl">
                 <div>
                    <p className="text-[8px] text-gray-500 font-bold uppercase tracking-widest">P/E Ratio</p>
                    <p className="text-xs font-bold font-mono text-white">{currentStockInfo?.pe_ratio?.toFixed(2) || '-'}</p>
                 </div>
                 <div>
                    <p className="text-[8px] text-gray-500 font-bold uppercase tracking-widest">P/B Ratio</p>
                    <p className="text-xs font-bold font-mono text-white">{currentStockInfo?.pbv_ratio?.toFixed(2) || '-'}</p>
                 </div>
                 <div>
                    <p className="text-[8px] text-gray-500 font-bold uppercase tracking-widest">Div. Yield</p>
                    <p className="text-xs font-bold font-mono text-green-400">{currentStockInfo?.dividend_yield ? `${(currentStockInfo.dividend_yield * 100).toFixed(2)}%` : '-'}</p>
                 </div>
              </div>
           </div>

           <div className="bg-white/[0.02] border border-white/5 rounded-[2.5rem] overflow-hidden mb-12 shadow-2xl relative">
              {loading ? (
                <div className="h-[450px] flex items-center justify-center text-gray-600 font-mono text-sm italic tracking-widest uppercase">Syncing Market Data...</div>
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
                    sync={chartSync.current}
                  />
                  {activeSubPanel && ohlcv.length > 0 && (
                    <IndicatorSubChart data={displayedOhlcv} type={activeSubPanel} sync={chartSync.current} />
                  )}
                </>
              )}
           </div>

           {/* ── ML PREDICTION CARD ── */}
           <div className="mb-10 bg-white/[0.02] border border-white/5 rounded-[2rem] overflow-hidden shadow-2xl">
             <div className="flex items-center justify-between px-8 py-5 border-b border-white/5 bg-white/[0.01]">
               <div className="flex items-center gap-3">
                 <span className="w-2 h-2 rounded-full bg-purple-500" />
                 <h2 className="text-[9px] font-black uppercase tracking-[0.4em] text-purple-400">ML Price Prediction</h2>
                 <span className="text-[8px] font-mono text-gray-700 bg-white/5 px-2 py-0.5 rounded-full">5-Day Horizon</span>
               </div>
               <div className="flex items-center gap-3">
                 {mlStatus?.trained && mlStatus.trained_at && (
                   <span className="text-[8px] font-mono text-gray-700 hidden md:block">
                     Trained: {new Date(mlStatus.trained_at).toLocaleDateString('id-ID')}
                     {mlStatus.accuracy ? ` · Acc ${(mlStatus.accuracy * 100).toFixed(1)}%` : ''}
                   </span>
                 )}
                 <button
                   onClick={handleMlTrain}
                   disabled={mlTraining}
                   className="text-[8px] font-black uppercase tracking-widest px-4 py-1.5 rounded-full border border-purple-500/30 text-purple-400 bg-purple-500/5 hover:bg-purple-500/10 disabled:opacity-40 transition-all"
                 >
                   {mlTraining ? 'TRAINING...' : mlStatus?.trained ? 'RE-TRAIN' : 'TRAIN MODEL'}
                 </button>
               </div>
             </div>

             <div className="p-8">
               {/* Belum di-train */}
               {!mlStatus?.trained && !mlTraining && (
                 <div className="flex flex-col items-center justify-center py-8 gap-3 opacity-50">
                   <p className="text-xs font-mono text-gray-500">Model belum dilatih untuk saham ini.</p>
                   <p className="text-[9px] text-gray-700">Klik TRAIN MODEL untuk memulai (~5 detik)</p>
                 </div>
               )}

               {/* Sedang training */}
               {mlTraining && (
                 <div className="flex flex-col items-center justify-center py-8 gap-3">
                   <div className="w-6 h-6 border-2 border-purple-500/30 border-t-purple-400 rounded-full animate-spin" />
                   <p className="text-[9px] font-mono text-gray-500 uppercase tracking-widest animate-pulse">Melatih model GradientBoosting...</p>
                 </div>
               )}

               {/* Loading prediksi */}
               {mlLoading && !mlTraining && (
                 <div className="flex items-center justify-center py-8">
                   <p className="text-[9px] font-mono text-gray-600 animate-pulse uppercase tracking-widest">Menghitung prediksi...</p>
                 </div>
               )}

               {/* Error */}
               {mlResult?.status === 'error' && (
                 <div className="text-red-400 text-xs font-mono py-4 text-center">{mlResult.message}</div>
               )}

               {/* Hasil prediksi */}
               {mlResult?.status === 'ok' && !mlLoading && (
                 <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                   {/* Kolom kiri: Arah + Confidence */}
                   <div>
                     {/* Direction badge */}
                     <div className={`inline-flex items-center gap-3 px-5 py-3 rounded-2xl border mb-5 ${
                       mlResult.direction === 'BULLISH'
                         ? 'bg-green-500/10 border-green-500/20 text-green-400'
                         : mlResult.direction === 'BEARISH'
                           ? 'bg-red-500/10 border-red-500/20 text-red-400'
                           : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400'
                     }`}>
                       <span className="text-xl font-black">
                         {mlResult.direction === 'BULLISH' ? '▲' : mlResult.direction === 'BEARISH' ? '▼' : '◆'}
                       </span>
                       <div>
                         <p className="text-lg font-black tracking-tight leading-none">{mlResult.direction}</p>
                         <p className="text-[8px] font-mono opacity-70 uppercase tracking-widest mt-0.5">Rekomendasi: {mlResult.recommendation}</p>
                       </div>
                     </div>

                     {/* Confidence bar */}
                     <div className="mb-5">
                       <div className="flex justify-between items-center mb-2">
                         <span className="text-[9px] font-black uppercase tracking-widest text-gray-500">Confidence</span>
                         <span className="text-sm font-black font-mono text-white">{mlResult.confidence}%</span>
                       </div>
                       <div className="w-full bg-white/5 rounded-full h-2">
                         <div
                           className={`h-2 rounded-full transition-all duration-700 ${
                             mlResult.direction === 'BULLISH' ? 'bg-green-500' :
                             mlResult.direction === 'BEARISH' ? 'bg-red-500' : 'bg-yellow-500'
                           }`}
                           style={{ width: `${mlResult.confidence}%` }}
                         />
                       </div>
                     </div>

                     {/* Probabilitas naik/turun */}
                     <div className="grid grid-cols-2 gap-3 mb-4">
                       <div className="bg-green-500/5 border border-green-500/10 rounded-xl p-4 text-center">
                         <p className="text-[8px] text-gray-600 uppercase tracking-widest mb-1 font-black">Prob. Naik</p>
                         <p className="text-xl font-black font-mono text-green-400">
                           {((mlResult.probability_up ?? 0) * 100).toFixed(1)}%
                         </p>
                       </div>
                       <div className="bg-red-500/5 border border-red-500/10 rounded-xl p-4 text-center">
                         <p className="text-[8px] text-gray-600 uppercase tracking-widest mb-1 font-black">Prob. Turun</p>
                         <p className="text-xl font-black font-mono text-red-400">
                           {((mlResult.probability_down ?? 0) * 100).toFixed(1)}%
                         </p>
                       </div>
                     </div>

                     {/* Model stats */}
                     {mlResult.model_accuracy && (
                       <div className="flex gap-4 text-[8px] font-mono text-gray-600">
                         <span>Akurasi model: <span className="text-gray-400 font-black">{((mlResult.model_accuracy) * 100).toFixed(1)}%</span></span>
                         {mlResult.model_auc && <span>AUC: <span className="text-gray-400 font-black">{mlResult.model_auc.toFixed(3)}</span></span>}
                         {mlResult.samples_train && <span>Train: <span className="text-gray-400 font-black">{mlResult.samples_train} bar</span></span>}
                       </div>
                     )}
                   </div>

                   {/* Kolom kanan: Top Feature Drivers */}
                   <div>
                     <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-4">Top Faktor Penentu</p>
                     <div className="space-y-3">
                       {mlResult.top_features?.map((f, i) => {
                         const maxImp = mlResult.top_features![0].importance;
                         const pct    = Math.round((f.importance / maxImp) * 100);
                         return (
                           <div key={i}>
                             <div className="flex justify-between items-center mb-1">
                               <span className="text-[9px] font-bold text-gray-400">{f.name}</span>
                               <span className="text-[8px] font-mono text-gray-600">{(f.importance * 100).toFixed(1)}%</span>
                             </div>
                             <div className="w-full bg-white/5 rounded-full h-1.5">
                               <div
                                 className="h-1.5 rounded-full bg-purple-500/60"
                                 style={{ width: `${pct}%` }}
                               />
                             </div>
                           </div>
                         );
                       })}
                     </div>
                     <p className="text-[7px] font-mono text-gray-700 mt-5 leading-relaxed">
                       ⚠ Prediksi berbasis probabilitas historis — bukan jaminan. Selalu gunakan analisa teknikal dan fundamental sebagai konfirmasi.
                     </p>
                   </div>
                 </div>
               )}
             </div>
           </div>

           <h2 className="text-sm font-black font-mono uppercase tracking-[0.5em] text-gray-700 mb-8 flex items-center gap-6">
              <span className="w-12 h-px bg-white/10"></span>
              Technical Intelligence Core
              <span className="flex-1 h-px bg-white/10"></span>
           </h2>
           
           <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-16">
             {[
               { label: "RSI (14)", value: indicators?.RSI_14, valueClass: rsiColor(indicators?.RSI_14 ?? null), extra: indicators?.RSI_14 ? (indicators.RSI_14 < 30 ? "OVERSOLD" : indicators.RSI_14 > 70 ? "OVERBOUGHT" : "NEUTRAL") : null },
               { label: "MA 20", value: indicators?.MA_20 },
               { label: "MA 50", value: indicators?.MA_50 },
               { label: "MA 200", value: indicators?.MA_200 },
               { label: "EMA 12", value: indicators?.EMA_12 },
               { label: "EMA 26", value: indicators?.EMA_26 },
               { label: "MACD Line", value: indicators?.MACD_LINE },
               { label: "MACD Signal", value: indicators?.MACD_SIGNAL },
               { label: "MACD Hist", value: indicators?.MACD_HIST },
               { label: "BB Upper", value: indicators?.BB_UPPER },
               { label: "BB Middle", value: indicators?.BB_MIDDLE },
               { label: "BB Lower", value: indicators?.BB_LOWER },
               { label: "ATR (14)", value: indicators?.ATR_14 },
               { label: "Stoch %K", value: indicators?.STOCH_K },
               { label: "Stoch %D", value: indicators?.STOCH_D },
             ].map((ind, i) => (
               <div key={i} className="bg-white/[0.03] border border-white/5 p-6 rounded-3xl hover:bg-white/[0.06] transition-all text-center group shadow-sm">
                 <p className="text-[9px] text-gray-600 font-black uppercase mb-2 tracking-widest group-hover:text-blue-500 transition-colors">{ind.label}</p>
                 <p className={`text-base font-black font-mono ${ind.valueClass ?? "text-white"}`}>
                   {fmt(ind.value ?? null)}
                 </p>
                 {ind.extra && <p className={`text-[9px] mt-2 font-black ${ind.valueClass} tracking-tighter`}>{ind.extra}</p>}
               </div>
             ))}
           </div>
        </div>
      </main>

      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
      `}</style>
    </div>
  );
}
