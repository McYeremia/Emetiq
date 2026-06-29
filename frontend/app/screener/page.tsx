'use client';

import { useEffect, useState } from 'react';
import { api, Stock } from '@/lib/api';
import Link from 'next/link';
import strategyRegistry from '../../strategies_local/registry.json';

type FundSortKey = 'last_price' | 'change_pct' | 'pe_ratio' | 'pbv_ratio' | 'dividend_yield' | 'market_cap';

function fmtCap(n: number | null) {
  if (n == null || n <= 0) return '—';
  if (n >= 1_000_000_000_000) return `${(n / 1_000_000_000_000).toFixed(1)}T`;
  if (n >= 1_000_000_000)     return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000)         return `${(n / 1_000_000).toFixed(0)}M`;
  return n.toLocaleString('id-ID');
}

function fmtRatio(n: number | null) {
  if (n == null || n <= 0) return '—';
  return n.toFixed(2);
}

export default function ScreenerPage() {
  useEffect(() => { document.title = 'Screener — IDXAnalyst'; }, []);
  // ── Tab ─────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<'teknikal' | 'fundamental'>('teknikal');

  // ── Teknikal states ──────────────────────────────────────
  const [selectedStratId, setSelectedStratId] = useState<string | null>(null);
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

  // ── Load fundamental data on tab switch ─────────────────
  useEffect(() => {
    if (activeTab === 'fundamental' && fundStocks.length === 0) {
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

  function toggleFundSort(key: FundSortKey) {
    if (fundSortKey === key) setFundSortDir(d => (d === 'desc' ? 'asc' : 'desc'));
    else { setFundSortKey(key); setFundSortDir('desc'); }
  }

  function SortIcon({ k }: { k: FundSortKey }) {
    if (fundSortKey !== k) return <span className="text-gray-700 ml-1">↕</span>;
    return <span className="text-blue-500 ml-1">{fundSortDir === 'desc' ? '↓' : '↑'}</span>;
  }

  const activeStrat = strategyRegistry.find(s => s.id === selectedStratId);

  // ── Shared tab bar ───────────────────────────────────────
  function TabBar() {
    return (
      <div className="flex flex-wrap items-center gap-1 mb-10 p-1 bg-white/5 rounded-2xl border border-white/10 w-fit">
        {(['teknikal', 'fundamental'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-6 py-2.5 rounded-xl text-[9px] font-black tracking-[0.25em] uppercase transition-all ${
              activeTab === tab ? 'bg-blue-600 text-white' : 'text-gray-500 hover:text-white'
            }`}
          >
            {tab === 'teknikal' ? 'STRATEGI TEKNIKAL' : 'FUNDAMENTAL'}
          </button>
        ))}
      </div>
    );
  }

  // ── FUNDAMENTAL VIEW ─────────────────────────────────────
  if (activeTab === 'fundamental') {
    return (
      <main className="min-h-screen bg-[#050505] text-white p-6 md:p-10 pt-24 md:pt-28">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-black tracking-tighter mb-2">
              Fundamental <span className="text-blue-500">Screener</span>
            </h1>
            <p className="text-gray-500 font-mono text-[10px] uppercase tracking-[0.4em]">
              Filter saham berdasarkan valuasi & dividen
            </p>
          </div>

          <TabBar />

          {/* Filter panel */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 p-6 rounded-[2rem] bg-white/[0.02] border border-white/5">
            <div>
              <label className="text-[8px] font-black text-gray-600 uppercase tracking-[0.3em] block mb-2">
                PE Ratio Maks
              </label>
              <input
                type="number"
                min="0"
                placeholder="cth: 20"
                value={peMax}
                onChange={e => setPeMax(e.target.value)}
                className="w-full bg-white/5 border border-white/10 px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500/50 rounded-xl"
              />
            </div>
            <div>
              <label className="text-[8px] font-black text-gray-600 uppercase tracking-[0.3em] block mb-2">
                PBV Ratio Maks
              </label>
              <input
                type="number"
                min="0"
                placeholder="cth: 3"
                value={pbvMax}
                onChange={e => setPbvMax(e.target.value)}
                className="w-full bg-white/5 border border-white/10 px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500/50 rounded-xl"
              />
            </div>
            <div>
              <label className="text-[8px] font-black text-gray-600 uppercase tracking-[0.3em] block mb-2">
                Div. Yield Min (%)
              </label>
              <input
                type="number"
                min="0"
                step="0.1"
                placeholder="cth: 3"
                value={divYieldMin}
                onChange={e => setDivYieldMin(e.target.value)}
                className="w-full bg-white/5 border border-white/10 px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500/50 rounded-xl"
              />
            </div>
            <div>
              <label className="text-[8px] font-black text-gray-600 uppercase tracking-[0.3em] block mb-2">
                Sektor
              </label>
              <select
                value={selectedSector}
                onChange={e => setSelectedSector(e.target.value)}
                className="w-full bg-[#111] border border-white/10 px-3 py-2 text-sm font-mono text-white focus:outline-none focus:border-blue-500/50 rounded-xl"
              >
                <option value="">Semua Sektor</option>
                {sectors.map(s => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Results count + reset */}
          <div className="flex items-center justify-between mb-4">
            <span className="text-[9px] font-mono text-blue-500 tracking-[0.3em] uppercase">
              ◆ {filtered.length} SAHAM DITEMUKAN
            </span>
            {(peMax || pbvMax || divYieldMin || selectedSector) && (
              <button
                onClick={() => { setPeMax(''); setPbvMax(''); setDivYieldMin(''); setSelectedSector(''); }}
                className="text-[9px] font-mono text-gray-600 hover:text-gray-400 tracking-wider uppercase transition-colors"
              >
                RESET FILTER ✕
              </button>
            )}
          </div>

          {/* Table */}
          <div className="bg-white/[0.01] border border-white/5 rounded-[2.5rem] overflow-hidden">
            {fundLoading ? (
              <div className="flex items-center justify-center py-32">
                <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-white/5 text-[9px] font-black text-gray-600 uppercase tracking-[0.3em]">
                      <th className="px-8 py-6 text-left">Saham</th>
                      <th className="px-8 py-6 text-left">Sektor</th>
                      <th
                        className="px-8 py-6 text-right cursor-pointer hover:text-gray-400 select-none"
                        onClick={() => toggleFundSort('last_price')}
                      >
                        Harga <SortIcon k="last_price" />
                      </th>
                      <th
                        className="px-8 py-6 text-right cursor-pointer hover:text-gray-400 select-none"
                        onClick={() => toggleFundSort('change_pct')}
                      >
                        Chg% <SortIcon k="change_pct" />
                      </th>
                      <th
                        className="px-8 py-6 text-right cursor-pointer hover:text-gray-400 select-none"
                        onClick={() => toggleFundSort('pe_ratio')}
                      >
                        PE <SortIcon k="pe_ratio" />
                      </th>
                      <th
                        className="px-8 py-6 text-right cursor-pointer hover:text-gray-400 select-none"
                        onClick={() => toggleFundSort('pbv_ratio')}
                      >
                        PBV <SortIcon k="pbv_ratio" />
                      </th>
                      <th
                        className="px-8 py-6 text-right cursor-pointer hover:text-gray-400 select-none"
                        onClick={() => toggleFundSort('dividend_yield')}
                      >
                        Div. Yield <SortIcon k="dividend_yield" />
                      </th>
                      <th
                        className="px-8 py-6 text-right cursor-pointer hover:text-gray-400 select-none"
                        onClick={() => toggleFundSort('market_cap')}
                      >
                        Mkt Cap <SortIcon k="market_cap" />
                      </th>
                      <th className="px-8 py-6" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-mono">
                    {filtered.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="px-8 py-24 text-center text-gray-700 text-sm italic">
                          Tidak ada saham yang memenuhi kriteria filter.
                        </td>
                      </tr>
                    ) : (
                      filtered.map(s => {
                        const up = (s.change_pct ?? 0) >= 0;
                        return (
                          <tr key={s.ticker} className="group hover:bg-white/[0.02] transition-all">
                            <td className="px-8 py-5">
                              <span className="text-sm font-black text-white group-hover:text-blue-400 transition-colors block">
                                {s.ticker}
                              </span>
                              <span className="text-[8px] text-gray-600 truncate w-36 block mt-0.5">{s.name}</span>
                            </td>
                            <td className="px-8 py-5 text-[9px] text-gray-500 whitespace-nowrap">{s.sector || '—'}</td>
                            <td className="px-8 py-5 text-right text-sm font-black text-white tabular-nums">
                              {s.last_price?.toLocaleString('id-ID') ?? '—'}
                            </td>
                            <td className={`px-8 py-5 text-right text-xs font-bold tabular-nums ${up ? 'text-green-400' : 'text-red-400'}`}>
                              {s.change_pct != null
                                ? `${up ? '+' : ''}${s.change_pct.toFixed(2)}%`
                                : '—'}
                            </td>
                            <td className="px-8 py-5 text-right text-xs text-gray-300 tabular-nums">
                              {fmtRatio(s.pe_ratio)}
                            </td>
                            <td className="px-8 py-5 text-right text-xs text-gray-300 tabular-nums">
                              {fmtRatio(s.pbv_ratio)}
                            </td>
                            <td className="px-8 py-5 text-right text-xs font-bold tabular-nums text-blue-400">
                              {s.dividend_yield != null && s.dividend_yield > 0
                                ? `${s.dividend_yield.toFixed(2)}%`
                                : '—'}
                            </td>
                            <td className="px-8 py-5 text-right text-xs text-gray-400 tabular-nums">
                              {fmtCap(s.market_cap)}
                            </td>
                            <td className="px-8 py-5 text-right">
                              <Link
                                href={`/stocks/${s.ticker}`}
                                className="inline-block bg-white/5 hover:bg-blue-600 border border-white/10 px-5 py-1.5 rounded-xl text-[8px] font-black tracking-widest transition-all"
                              >
                                ANALISA
                              </Link>
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
        </div>
      </main>
    );
  }

  // ── TEKNIKAL: OVERVIEW ───────────────────────────────────
  if (!selectedStratId) {
    return (
      <main className="min-h-screen bg-[#050505] text-white p-6 md:p-10 pt-24 md:pt-28">
        <div className="max-w-7xl mx-auto">
          <div className="mb-8">
            <h1 className="text-4xl font-black tracking-tighter mb-2">
              Strategy <span className="text-blue-500">Screener</span>
            </h1>
            <p className="text-gray-500 font-mono text-[10px] uppercase tracking-[0.4em]">
              Select an algorithm to scan the market
            </p>
          </div>

          <TabBar />

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {strategyRegistry.map((strat) => (
              <button
                key={strat.id}
                onClick={() => setSelectedStratId(strat.id)}
                className="group p-8 rounded-[2.5rem] bg-white/[0.02] border border-white/5 hover:border-blue-500/40 hover:bg-white/[0.04] transition-all text-left relative overflow-hidden"
              >
                <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 group-hover:scale-110 transition-all">
                  <svg className="w-20 h-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <span className="text-[8px] font-black text-blue-500 uppercase tracking-widest">{strat.indicator}</span>
                <h3 className="text-2xl font-black mt-2 mb-4 group-hover:text-blue-400 transition-colors">{strat.name}</h3>
                <p className="text-xs text-gray-500 leading-relaxed line-clamp-2 mb-6">{strat.description}</p>
                <div className="flex items-center gap-2 text-[10px] font-bold text-gray-400 uppercase tracking-widest">
                  START SCANNING →
                </div>
              </button>
            ))}
          </div>
        </div>
      </main>
    );
  }

  // ── TEKNIKAL: STRATEGY DETAIL ────────────────────────────
  return (
    <main className="min-h-screen bg-[#050505] text-white p-6 md:p-10 pt-24 md:pt-28">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-8 mb-8">
          <div className="flex items-center gap-6">
            <button
              onClick={() => setSelectedStratId(null)}
              className="p-4 rounded-2xl bg-white/5 border border-white/10 hover:bg-white/10 transition-all"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div>
              <h1 className="text-3xl font-black tracking-tighter mb-1 text-blue-500">{activeStrat?.name}</h1>
              <p className="text-gray-500 font-mono text-[10px] uppercase tracking-widest">
                Real-time Scanner: {matches.length} Assets Found
                {scanTime && <span className="ml-3 text-gray-700">— Scan {scanTime}</span>}
              </p>
            </div>
          </div>
          <div className="p-1 bg-white/5 rounded-2xl border border-white/10 flex w-full sm:w-auto">
            <select
              value={selectedStratId}
              onChange={e => setSelectedStratId(e.target.value)}
              className="bg-transparent text-white px-6 py-2 text-[10px] font-black tracking-widest uppercase focus:outline-none cursor-pointer w-full"
            >
              {strategyRegistry.map(s => (
                <option key={s.id} value={s.id} className="bg-black">{s.name}</option>
              ))}
            </select>
          </div>
        </div>

        <TabBar />

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          <div className="lg:col-span-1 space-y-6">
            <div className="p-8 rounded-[2rem] bg-white/[0.03] border border-white/5 shadow-xl">
              <h3 className="text-[10px] font-black text-blue-400 uppercase tracking-[0.3em] mb-4">Execution Logic</h3>
              <div className="space-y-4">
                {activeStrat?.rules?.map((rule: string, i: number) => (
                  <div key={i} className="flex gap-3 items-start">
                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500/50 mt-1" />
                    <span className={`text-[10px] font-mono leading-tight ${
                      rule.startsWith('ENTRY') ? 'text-green-400' : 'text-gray-500'
                    }`}>
                      {rule}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="bg-white/[0.01] border border-white/5 rounded-[2.5rem] overflow-hidden backdrop-blur-md relative shadow-2xl">
              {loading && (
                <div className="absolute inset-0 bg-black/60 backdrop-blur-sm z-10 flex items-center justify-center">
                  <div className="flex flex-col items-center gap-4">
                    <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                    <p className="text-[9px] font-black tracking-widest text-blue-500 uppercase">Scanning 400+ Assets...</p>
                  </div>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="min-w-full">
                  <thead>
                    <tr className="border-b border-white/5 text-[9px] font-black text-gray-600 uppercase tracking-[0.4em]">
                      <th className="px-10 py-8 text-left">Instrument</th>
                      {activeStrat?.display_columns.map(col => (
                        <th
                          key={col}
                          className="px-10 py-8 text-left cursor-pointer hover:text-gray-400 select-none"
                          onClick={() => toggleSort(col)}
                        >
                          {col.replace('_', ' ')}
                          {sortCol === col ? (sortDir === 'desc' ? ' ↓' : ' ↑') : <span className="text-gray-700 ml-1">↕</span>}
                        </th>
                      ))}
                      <th className="px-10 py-8 text-right">Terminal</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5 font-mono">
                    {sortedMatches.length === 0 ? (
                      <tr>
                        <td colSpan={10} className="px-10 py-32 text-center text-gray-700 italic text-sm">
                          No assets currently meet this criteria. Market is neutral.
                        </td>
                      </tr>
                    ) : (
                      sortedMatches.map(m => (
                        <tr key={m.ticker} className="group hover:bg-white/[0.02] transition-all">
                          <td className="px-10 py-6 whitespace-nowrap">
                            <span className="text-base font-black text-white group-hover:text-blue-400 transition-colors block">
                              {m.ticker}
                            </span>
                            <span className="text-[8px] text-gray-600 uppercase truncate w-32 block mt-1">{m.name}</span>
                          </td>
                          {activeStrat?.display_columns.map(col => (
                            <td key={col} className="px-10 py-6 whitespace-nowrap">
                              <span className={`text-xs font-bold ${
                                typeof m[col] === 'number' && m[col] > 0 ? 'text-blue-400' :
                                typeof m[col] === 'number' && m[col] < 0 ? 'text-red-400' : 'text-gray-300'
                              }`}>
                                {typeof m[col] === 'number'
                                  ? m[col].toLocaleString('id-ID', { maximumFractionDigits: 2 })
                                  : m[col]}
                                {col.includes('Dist') || col.includes('Surge') ? '%' : ''}
                              </span>
                            </td>
                          ))}
                          <td className="px-10 py-6 text-right">
                            <Link
                              href={`/stocks/${m.ticker}`}
                              className="inline-block bg-white/5 hover:bg-blue-600 border border-white/10 px-6 py-2 rounded-xl text-[8px] font-black tracking-widest transition-all"
                            >
                              TRADE
                            </Link>
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
      </div>
    </main>
  );
}
