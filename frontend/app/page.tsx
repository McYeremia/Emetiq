'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

// ── Types ──────────────────────────────────────────────────
interface LiveTicker {
  symbol: string;
  price: string;
  change: string;
  up: boolean;
}

interface IhsgData {
  price: string;
  change: string;
  changePct: string;
  up: boolean;
  date: string;
}

// ── Constants ──────────────────────────────────────────────
const API = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

// Tickers to show on landing page (in order of priority)
const WATCH_LIST = ['BBCA', 'BMRI', 'TLKM', 'ASII', 'GOTO', 'BREN', 'BRIS', 'ICBP', 'MDKA', 'UNVR', 'BBRI', 'BBNI'];

const STRATEGIES = [
  'TRIPLE CONFIRMATION',
  'VOLATILITY SNIPER',
  'INSTITUTIONAL TREND',
  'EXHAUSTION PLAY',
  'TREND ACCELERATOR',
  'PURE MOMENTUM',
  'DEFENSIVE BULL',
  'STOCH-RSI HYBRID',
  'RSI REVERSION',
  'MA CROSS',
];

const NAV_LINKS = [
  { label: 'MARKET',      href: '/dashboard' },
  { label: 'SCREENER',    href: '/screener' },
  { label: 'PORTOFOLIO',  href: '/portfolio' },
  { label: 'BACKTEST',    href: '/backtest' },
  { label: 'BROKER FLOW', href: '/broker-flow' },
];

// Fallback static data (shown while loading / if backend offline)
const STATIC_TICKERS: LiveTicker[] = [
  { symbol: 'BBCA', price: '–', change: '–', up: true },
  { symbol: 'BMRI', price: '–', change: '–', up: true },
  { symbol: 'TLKM', price: '–', change: '–', up: false },
  { symbol: 'ASII', price: '–', change: '–', up: true },
  { symbol: 'GOTO', price: '–', change: '–', up: false },
  { symbol: 'BREN', price: '–', change: '–', up: true },
  { symbol: 'BRIS', price: '–', change: '–', up: true },
  { symbol: 'ICBP', price: '–', change: '–', up: false },
  { symbol: 'MDKA', price: '–', change: '–', up: true },
  { symbol: 'UNVR', price: '–', change: '–', up: false },
];

const STATIC_IHSG: IhsgData = {
  price: '–', change: '–', changePct: '–', up: true, date: '',
};

// ── Formatters ─────────────────────────────────────────────
function fmtPrice(n: number | null): string {
  if (n == null || n === 0) return '–';
  return n.toLocaleString('id-ID');
}

function fmtChange(n: number | null): string {
  if (n == null) return '–';
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

function fmtAbsChange(n: number | null): string {
  if (n == null) return '–';
  return `${n >= 0 ? '+' : ''}${n.toLocaleString('id-ID', { maximumFractionDigits: 2 })}`;
}

// ── Component ──────────────────────────────────────────────
export default function LandingPage() {
  useEffect(() => { document.title = 'IDXAnalyst — Market Terminal'; }, []);
  const [activeTick, setActiveTick] = useState(0);
  const [tickers, setTickers]       = useState<LiveTicker[]>(STATIC_TICKERS);
  const [ihsg, setIhsg]             = useState<IhsgData>(STATIC_IHSG);
  const [dataDate, setDataDate]      = useState('MEMUAT DATA...');

  // Rotating highlight in terminal
  useEffect(() => {
    const id = setInterval(() => setActiveTick(t => (t + 1) % 10), 1800);
    return () => clearInterval(id);
  }, []);

  // Fetch live market data from backend
  useEffect(() => {
    async function loadMarketData() {
      try {
        // Fetch stocks and IHSG in parallel
        const [stocksRes, ihsgRes] = await Promise.all([
          fetch(`${API}/stocks`),
          fetch(`${API}/stocks/ihsg`),
        ]);

        if (stocksRes.ok) {
          const stocks: {
            ticker: string;
            last_price: number | null;
            change_pct: number | null;
            last_date: string | null;
          }[] = await stocksRes.json();

          // Build a lookup map
          const stockMap = new Map(stocks.map(s => [s.ticker, s]));

          // Map WATCH_LIST order, skip if not in DB
          const live: LiveTicker[] = WATCH_LIST
            .map(sym => {
              const s = stockMap.get(sym);
              if (!s || s.last_price == null) return null;
              return {
                symbol: sym,
                price: fmtPrice(s.last_price),
                change: fmtChange(s.change_pct),
                up: (s.change_pct ?? 0) >= 0,
              };
            })
            .filter(Boolean) as LiveTicker[];

          if (live.length > 0) {
            setTickers(live.slice(0, 10));

            // Use last_date of first available stock for the data date label
            const anyDate = stocks.find(s => s.last_date)?.last_date;
            if (anyDate) {
              setDataDate(`DATA PER ${anyDate} — EOD`);
            }
          }
        }

        if (ihsgRes.ok) {
          const ihsgData: {
            price: number | null;
            change: number | null;
            change_pct: number | null;
            date: string | null;
          } = await ihsgRes.json();

          if (ihsgData.price != null) {
            setIhsg({
              price: fmtPrice(ihsgData.price),
              change: fmtAbsChange(ihsgData.change),
              changePct: fmtChange(ihsgData.change_pct),
              up: (ihsgData.change_pct ?? 0) >= 0,
              date: ihsgData.date ?? '',
            });
          }
        }
      } catch {
        // Backend offline — keep static placeholders
        setDataDate('BACKEND OFFLINE');
      }
    }

    loadMarketData();
  }, []);

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white selection:bg-[#3B82F6]/40 selection:text-white">

      {/* ── HERO ───────────────────────────────────────────────── */}
      <section className="relative min-h-screen pt-[60px] border-b-2 border-white/10 overflow-hidden">
        <div
          className="absolute inset-0 opacity-[0.025] pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(#ffffff 1px, transparent 1px), linear-gradient(90deg, #ffffff 1px, transparent 1px)',
            backgroundSize: '64px 64px',
          }}
        />
        <div className="absolute top-1/3 left-1/4 w-[600px] h-[400px] bg-[#3B82F6]/5 blur-[120px] pointer-events-none" />

        <div className="max-w-[1400px] mx-auto px-6 pt-14 pb-24 relative">
          {/* Meta strip */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 mb-12 pb-6 border-b border-white/10">
            <span className="text-[9px] font-mono text-[#22C55E] tracking-[0.3em] uppercase">◆ IDX80 COVERAGE</span>
            <span className="text-[9px] font-mono text-gray-700">|</span>
            <span className="text-[9px] font-mono text-gray-600 tracking-[0.25em] uppercase">3 AI AGENTS COMPETING</span>
            <span className="text-[9px] font-mono text-gray-700">|</span>
            <span className="text-[9px] font-mono text-gray-600 tracking-[0.25em] uppercase">10 QUANT ALGORITHMS</span>
            <span className="text-[9px] font-mono text-gray-700">|</span>
            <span className="text-[9px] font-mono text-gray-600 tracking-[0.25em] uppercase">EOD DATA — YAHOO FINANCE</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
            {/* Left: Main copy */}
            <div className="lg:col-span-7 lg:border-r lg:border-white/10 lg:pr-14">
              <div className="mb-6">
                <span className="text-[9px] font-mono text-[#3B82F6] tracking-[0.4em] uppercase border border-[#3B82F6]/30 bg-[#3B82F6]/5 px-3 py-1.5">
                  AI TRADING COMPETITION — PAPER TRADE
                </span>
              </div>

              <h1 className="font-black leading-[0.86] tracking-tighter uppercase mb-8 text-[clamp(52px,7.5vw,108px)]">
                DOMINATE<br />
                THE IDX<br />
                <span className="text-[#3B82F6]">MARKET.</span>
              </h1>

              <p className="text-gray-400 text-base md:text-lg max-w-xl mb-10 leading-relaxed font-medium">
                Platform intelijen saham IDX yang menggabungkan analisis fundamental dengan 10 algoritma quant otonom.
                Adu strategi Anda melawan Gemini dan Claude dalam AI Battle.
              </p>

              <div className="flex flex-wrap gap-3 mb-12">
                <Link
                  href="/dashboard"
                  className="bg-[#3B82F6] text-white px-8 py-4 text-[11px] font-black tracking-[0.3em] uppercase hover:bg-blue-400 transition-colors duration-100 inline-flex items-center gap-2"
                >
                  ENTER TERMINAL <span className="text-sm">→</span>
                </Link>
                <Link
                  href="/backtest"
                  className="border-2 border-white/20 text-white px-8 py-4 text-[11px] font-black tracking-[0.3em] uppercase hover:border-[#3B82F6] hover:text-[#3B82F6] transition-colors duration-100"
                >
                  BACKTEST
                </Link>
              </div>

              {/* Mini stats */}
              <div className="flex flex-wrap gap-10 pt-8 border-t border-white/10">
                {[
                  { num: '900+', label: 'IDX STOCKS' },
                  { num: '10', label: 'ALGORITHMS' },
                  { num: 'Rp 45M', label: 'TOTAL STAKES' },
                ].map((s, i) => (
                  <div key={i}>
                    <div className="text-3xl font-black text-[#3B82F6] tracking-tight leading-none">{s.num}</div>
                    <div className="text-[9px] font-mono text-gray-600 tracking-[0.25em] mt-1.5 uppercase">{s.label}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Right: Market Terminal — live data */}
            <div className="lg:col-span-5 pt-8 lg:pt-0 lg:pl-14">
              <div className="border-2 border-white/15 bg-[#111111] h-full min-h-[440px]">
                {/* Terminal header */}
                <div className="border-b-2 border-white/10 px-5 py-3.5 flex items-center justify-between bg-[#0F0F0F]">
                  <div className="flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-[#22C55E] animate-pulse" />
                    <span className="text-[9px] font-mono text-gray-500 tracking-[0.2em] uppercase">
                      MARKET TERMINAL — LIVE EOD
                    </span>
                  </div>
                  <span className="text-[9px] font-mono text-gray-700 tracking-wider">IDX.JK</span>
                </div>

                <div className="p-5">
                  {/* IHSG */}
                  <div className={`border p-4 mb-4 ${ihsg.up ? 'border-[#22C55E]/25 bg-[#22C55E]/5' : 'border-[#EF4444]/25 bg-[#EF4444]/5'}`}>
                    <div className="flex items-end justify-between">
                      <div>
                        <div className="text-[8px] font-mono text-gray-600 tracking-[0.3em] uppercase mb-1.5">
                          IHSG COMPOSITE
                          {ihsg.date ? <span className="ml-2 text-gray-700">({ihsg.date})</span> : null}
                        </div>
                        <div className="text-4xl font-black text-white tracking-tight leading-none tabular-nums">
                          {ihsg.price}
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`font-black text-base tabular-nums ${ihsg.up ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
                          {ihsg.change}
                        </div>
                        <div className={`font-mono text-sm tabular-nums ${ihsg.up ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
                          {ihsg.changePct}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Ticker rows */}
                  <div>
                    {tickers.map((t, i) => (
                      <Link
                        key={t.symbol}
                        href={`/stocks/${t.symbol}`}
                        className={`block flex items-center justify-between px-3 py-2.5 border-b border-white/[0.04] transition-colors duration-200 cursor-pointer ${
                          i === activeTick % tickers.length ? 'bg-[#3B82F6]/8' : 'hover:bg-white/[0.03]'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-[9px] font-mono text-gray-700 w-4 tabular-nums">
                            {String(i + 1).padStart(2, '0')}
                          </span>
                          <span className="text-[11px] font-black text-white tracking-wider">{t.symbol}</span>
                        </div>
                        <div className="flex items-center gap-5">
                          <span className="text-[11px] font-mono text-gray-400 tabular-nums">{t.price}</span>
                          <span
                            className={`text-[10px] font-black w-16 text-right tabular-nums ${
                              t.up ? 'text-[#22C55E]' : 'text-[#EF4444]'
                            }`}
                          >
                            {t.change}
                          </span>
                        </div>
                      </Link>
                    ))}
                  </div>

                  <div className="mt-4 pt-4 border-t border-white/10 text-center">
                    <span className="text-[9px] font-mono text-gray-700 tracking-[0.25em] uppercase">
                      {dataDate}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── TICKER TAPE — live data ─────────────────────────────── */}
      <div className="bg-[#1D4ED8] py-4 overflow-hidden border-y-2 border-[#1E40AF]">
        <div className="flex animate-marquee whitespace-nowrap gap-10 uppercase">
          {[...tickers, ...tickers].map((t, i) => (
            <span key={i} className="flex items-center gap-2.5 text-[10px] font-black text-white tracking-[0.15em]">
              <span className="font-mono">{t.symbol}</span>
              <span className="font-mono text-white/50">{t.price}</span>
              <span className={`font-black ${t.up ? 'text-[#86EFAC]' : 'text-[#FCA5A5]'}`}>{t.change}</span>
              <span className="text-white/20 mx-1">◆</span>
            </span>
          ))}
        </div>
      </div>

      {/* ── FEATURES / ARSENAL ─────────────────────────────────── */}
      <section className="border-b-2 border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="px-6 py-7 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-[9px] font-mono text-[#3B82F6] tracking-[0.4em] uppercase">◆ ARSENAL</span>
              <span className="text-[9px] font-mono text-gray-700">—</span>
              <span className="text-[9px] font-mono text-gray-600 tracking-[0.2em] uppercase">TRADING WEAPONS</span>
            </div>
            <span className="text-[9px] font-mono text-gray-700 tracking-[0.3em]">03 CORE MODULES</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3">
            {[
              {
                num: '01',
                title: 'AI BATTLEGROUND',
                desc: 'Tiga portofolio bersaing: USER, CLAUDE, GEMINI. Modal Rp 15 juta per agen. Siapa yang menghasilkan return tertinggi?',
                accent: '#3B82F6',
                tag: 'AUTONOMOUS',
              },
              {
                num: '02',
                title: '10 QUANT ALGORITHMS',
                desc: 'Triple Confirmation, Volatility Sniper, Institutional Trend, dan 7 strategi lainnya. Screener berbasis sinyal multi-konfirmasi.',
                accent: '#22C55E',
                tag: 'ALGORITHMIC',
              },
              {
                num: '03',
                title: 'TECHNO-FUNDAMENTAL',
                desc: 'Validasi teknikal + fundamental PE/PBV/Dividen. Setiap entry dikonfirmasi dari dua sisi — momentum dan nilai intrinsik.',
                accent: '#60A5FA',
                tag: 'HYBRID ANALYSIS',
              },
            ].map((feat, i) => (
              <div
                key={i}
                className="p-10 border-r border-b border-white/10 last:border-r-0 group hover:bg-white/[0.025] transition-colors duration-150"
              >
                <div className="flex items-start justify-between mb-8">
                  <span className="text-6xl font-black text-white/[0.06] tracking-tight leading-none select-none">
                    {feat.num}
                  </span>
                  <span
                    className="text-[8px] font-mono tracking-[0.3em] px-2 py-1 border"
                    style={{ color: feat.accent, borderColor: feat.accent + '40' }}
                  >
                    {feat.tag}
                  </span>
                </div>
                <h3
                  className="text-lg font-black uppercase tracking-tight mb-4 leading-tight"
                  style={{ color: feat.accent }}
                >
                  {feat.title}
                </h3>
                <p className="text-gray-500 text-sm leading-relaxed">{feat.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── BATTLEGROUND ───────────────────────────────────────── */}
      <section className="border-b-2 border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="px-6 py-7 border-b border-white/10 flex items-center gap-4">
            <span className="text-[9px] font-mono text-[#3B82F6] tracking-[0.4em] uppercase">◆ THE COMPETITION</span>
            <span className="text-[9px] font-mono text-gray-700">—</span>
            <span className="text-[9px] font-mono text-gray-600 tracking-[0.2em] uppercase">3 AGENTS. 1 WINNER.</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3">
            {[
              {
                agent: 'HUMAN',
                by: 'YOU',
                desc: 'Strategi manual berbasis intuisi dan pengalaman pasar. Baca grafik, analisa berita, eksekusi sendiri dengan penuh kontrol.',
                accent: '#60A5FA',
                initial: 'H',
                highlight: false,
              },
              {
                agent: 'CLAUDE AI',
                by: 'ANTHROPIC',
                desc: 'Konservatif dan value-oriented. Prioritas fundamental kuat, PE rendah, PBV wajar — proteksi modal lebih utama dari kejaran return.',
                accent: '#3B82F6',
                initial: 'C',
                highlight: true,
              },
              {
                agent: 'GEMINI AI',
                by: 'GOOGLE',
                desc: 'Agresif momentum-based. Mengejar sinyal teknikal cepat dengan risk appetite lebih tinggi dan eksekusi reaktif.',
                accent: '#22C55E',
                initial: 'G',
                highlight: false,
              },
            ].map((agent, i) => (
              <div
                key={i}
                className={`p-10 border-r border-b border-white/10 last:border-r-0 relative overflow-hidden ${
                  agent.highlight ? 'bg-[#3B82F6]/[0.05]' : 'hover:bg-white/[0.02]'
                } transition-colors`}
              >
                {agent.highlight && (
                  <div className="absolute top-0 left-0 right-0 h-0.5 bg-[#3B82F6]" />
                )}
                <div className="flex items-center justify-between mb-8">
                  <div
                    className="w-12 h-12 flex items-center justify-center border-2 font-black text-xl"
                    style={{ borderColor: agent.accent, color: agent.accent }}
                  >
                    {agent.initial}
                  </div>
                  <span className="text-[8px] font-mono text-gray-700 tracking-[0.3em] uppercase">{agent.by}</span>
                </div>
                <h3
                  className="text-xl font-black uppercase tracking-tight mb-1 leading-tight"
                  style={{ color: agent.accent }}
                >
                  {agent.agent}
                </h3>
                <div className="text-[8px] font-mono text-gray-700 tracking-[0.2em] mb-5 uppercase">
                  Rp 15,000,000 MODAL AWAL
                </div>
                <p className="text-gray-500 text-sm leading-relaxed">{agent.desc}</p>
              </div>
            ))}
          </div>

          <div className="px-6 py-5 border-t border-white/10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <span className="text-[9px] font-mono text-gray-700 tracking-[0.2em] uppercase">
              PAPER TRADING — NO REAL MONEY INVOLVED
            </span>
            <Link
              href="/portfolio"
              className="text-[9px] font-mono text-[#3B82F6] tracking-[0.2em] uppercase hover:text-white transition-colors"
            >
              VIEW LEADERBOARD →
            </Link>
          </div>
        </div>
      </section>

      {/* ── STRATEGIES GRID (Deep Navy) ─────────────────────────── */}
      <section className="bg-[#0D1B2A] border-b-2 border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="px-6 py-7 border-b border-white/10 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <span className="text-[9px] font-mono text-[#60A5FA] tracking-[0.4em] uppercase">◆ QUANT STRATEGIES</span>
              <span className="text-[9px] font-mono text-white/20">—</span>
              <span className="text-[9px] font-mono text-white/40 tracking-[0.2em] uppercase">10 ALGORITHMS ACTIVE</span>
            </div>
            <Link
              href="/screener"
              className="text-[9px] font-mono text-[#3B82F6] font-black tracking-[0.2em] uppercase hover:text-white transition-colors"
            >
              OPEN SCREENER →
            </Link>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5">
            {STRATEGIES.map((s, i) => (
              <div
                key={i}
                className="px-6 py-8 border-r border-b border-white/[0.07] last:border-r-0 group hover:bg-[#3B82F6] transition-colors duration-100 cursor-default"
              >
                <div className="text-[8px] font-mono text-white/25 group-hover:text-white/50 mb-2 tabular-nums">
                  {String(i + 1).padStart(2, '0')}
                </div>
                <div className="text-[10px] font-black text-white/60 group-hover:text-white tracking-wide leading-tight uppercase transition-colors">
                  {s}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── BIG STATS ──────────────────────────────────────────── */}
      <section className="border-b-2 border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4">
            {[
              { num: '900+', label: 'IDX STOCKS', sub: 'COVERED' },
              { num: '16', label: 'INDICATORS', sub: 'TECHNICAL' },
              { num: '5Y', label: 'HISTORY', sub: 'BACKTEST DATA' },
              { num: '3', label: 'AI AGENTS', sub: 'COMPETING NOW' },
            ].map((s, i) => (
              <div
                key={i}
                className="px-8 py-14 border-r border-b border-white/10 last:border-r-0 hover:bg-white/[0.02] transition-colors"
              >
                <div className="text-5xl md:text-6xl font-black text-white tracking-tight leading-none mb-3 tabular-nums">
                  {s.num}
                </div>
                <div className="text-[9px] font-mono text-[#3B82F6] tracking-[0.3em] uppercase mb-1">{s.label}</div>
                <div className="text-[8px] font-mono text-gray-700 tracking-[0.2em] uppercase">{s.sub}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ───────────────────────────────────────── */}
      <section className="border-b-2 border-white/10">
        <div className="max-w-[1400px] mx-auto">
          <div className="px-6 py-7 border-b border-white/10 flex items-center gap-4">
            <span className="text-[9px] font-mono text-[#3B82F6] tracking-[0.4em] uppercase">◆ HOW IT WORKS</span>
            <span className="text-[9px] font-mono text-gray-700">—</span>
            <span className="text-[9px] font-mono text-gray-600 tracking-[0.2em] uppercase">4 STEPS</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4">
            {[
              {
                step: '01',
                title: 'PILIH SAHAM',
                desc: 'Buka Market atau Screener. Filter dari 900+ saham IDX berdasarkan sinyal quant dan fundamental.',
                link: '/screener',
              },
              {
                step: '02',
                title: 'ANALISA',
                desc: 'Lihat candlestick, RSI, MACD, Bollinger Bands, dan 13 indikator lainnya dalam satu view.',
                link: '/dashboard',
              },
              {
                step: '03',
                title: 'BACKTEST',
                desc: 'Uji strategi Anda pada data 5 tahun historis. Lihat win rate, drawdown, dan Sharpe ratio.',
                link: '/backtest',
              },
              {
                step: '04',
                title: 'BATTLE',
                desc: 'Masuk ke AI Battleground. Eksekusi trade manual dan pantau performa Anda vs Claude dan Gemini.',
                link: '/portfolio',
              },
            ].map((s, i) => (
              <Link
                key={i}
                href={s.link}
                className="p-8 border-r border-b border-white/10 last:border-r-0 group hover:bg-white/[0.025] transition-colors duration-150 block"
              >
                <div className="text-5xl font-black text-white/[0.06] tracking-tight leading-none mb-6 tabular-nums select-none">
                  {s.step}
                </div>
                <div className="w-8 h-0.5 bg-[#3B82F6] mb-5 group-hover:w-16 transition-all duration-200" />
                <h3 className="text-sm font-black text-white uppercase tracking-wider mb-3">{s.title}</h3>
                <p className="text-gray-500 text-sm leading-relaxed">{s.desc}</p>
                <div className="text-[9px] font-mono text-[#3B82F6] tracking-[0.2em] uppercase mt-5 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                  OPEN →
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ────────────────────────────────────────────────── */}
      <section className="py-24 border-b-2 border-white/10">
        <div className="max-w-[1400px] mx-auto px-6">
          <div className="border-2 border-[#3B82F6] p-12 md:p-20 relative overflow-hidden bg-[#3B82F6]/[0.03]">
            <div className="absolute top-6 right-6 text-[9px] font-mono text-[#3B82F6]/25 tracking-[0.3em] uppercase select-none">
              IDXAnalyst — AI BATTLE v1.0
            </div>
            <div className="absolute bottom-0 right-0 text-[180px] font-black text-[#3B82F6]/[0.05] leading-none tracking-tighter select-none pointer-events-none">
              IDX
            </div>

            <div className="relative max-w-3xl">
              <div className="text-[9px] font-mono text-[#3B82F6] tracking-[0.4em] uppercase mb-6">
                ◆ READY TO COMPETE?
              </div>
              <h2 className="text-4xl md:text-6xl font-black uppercase tracking-tighter leading-[0.88] mb-8 text-white">
                BEAT THE AI.<br />
                BEAT THE MARKET.
              </h2>
              <p className="text-gray-500 text-base mb-10 max-w-xl leading-relaxed">
                Mulai analisis sekarang — gunakan 10 strategi quant, pantau AI Battle secara real-time, dan uji portofolio Anda secara bebas tanpa modal nyata.
              </p>
              <div className="flex flex-wrap gap-4">
                <Link
                  href="/dashboard"
                  className="bg-[#3B82F6] text-white px-10 py-5 font-black text-sm tracking-[0.3em] uppercase hover:bg-blue-400 transition-colors duration-100 inline-flex items-center gap-3"
                >
                  ENTER TERMINAL <span className="text-base">→</span>
                </Link>
                <Link
                  href="/portfolio"
                  className="border-2 border-white/20 text-white px-10 py-5 font-black text-sm tracking-[0.3em] uppercase hover:border-[#3B82F6] hover:text-[#3B82F6] transition-colors duration-100"
                >
                  VIEW BATTLEGROUND
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ─────────────────────────────────────────────── */}
      <footer className="py-10">
        <div className="max-w-[1400px] mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 bg-[#3B82F6] flex items-center justify-center font-black text-[10px] text-white">
              IX
            </div>
            <span className="text-sm font-black tracking-tighter uppercase">
              IDX<span className="text-[#3B82F6]">Analyst</span>
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-6">
            {NAV_LINKS.map(link => (
              <Link
                key={link.label}
                href={link.href}
                className="text-[9px] font-mono text-gray-700 hover:text-[#3B82F6] tracking-[0.2em] uppercase transition-colors"
              >
                {link.label}
              </Link>
            ))}
          </div>

          <p className="text-[9px] font-mono text-gray-800 tracking-[0.3em] uppercase">
            © 2026 IDXAnalyst. Paper Trading Only.
          </p>
        </div>
      </footer>

      <style jsx>{`
        @keyframes marquee {
          0% { transform: translateX(0); }
          100% { transform: translateX(-50%); }
        }
        .animate-marquee {
          display: flex;
          animation: marquee 28s linear infinite;
        }
      `}</style>
    </div>
  );
}
