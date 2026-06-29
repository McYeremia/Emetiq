'use client';

import { useEffect, useState } from 'react';
import { api, BacktestResult } from '@/lib/api';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import strategyRegistry from '../../strategies_local/registry.json';

const EquityChart = dynamic(() => import('@/components/EquityChart'), { ssr: false });
const CompareEquityChart = dynamic(() => import('@/components/CompareEquityChart'), { ssr: false });

const STRATEGY_COLORS: Record<string, string> = {
  'triple-confirmation':  '#3b82f6',
  'volatility-sniper':    '#10b981',
  'institutional-trend':  '#8b5cf6',
  'exhaustion-play':      '#f59e0b',
  'trend-accelerator':    '#06b6d4',
  'pure-momentum':        '#ec4899',
  'defensive-bull':       '#84cc16',
  'stoch-rsi-hybrid':     '#f97316',
  'rsi-reversion':        '#ef4444',
  'ma-cross':             '#a78bfa',
};

export default function BacktestPage() {
  useEffect(() => { document.title = 'Backtest — IDXAnalyst'; }, []);
  const [results, setResults] = useState<Record<string, BacktestResult>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<string | null>(null);
  const [selectedTicker, setSelectedTicker] = useState('BBCA');
  const [capitalInput, setCapitalInput] = useState('10000000');
  const [isRunningAll, setIsRunningAll] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);

  const parsedCapital = Math.max(1_000_000, parseInt(capitalInput.replace(/\D/g, '')) || 10_000_000);

  const formatCapitalDisplay = (val: string) => {
    const num = parseInt(val.replace(/\D/g, '')) || 0;
    if (num >= 1_000_000_000) return `Rp ${(num / 1_000_000_000).toFixed(1)}M (miliar)`;
    if (num >= 1_000_000) return `Rp ${(num / 1_000_000).toFixed(0)} juta`;
    return `Rp ${num.toLocaleString('id-ID')}`;
  };

  const runSingleTest = async (strategyId: string) => {
    setLoading(strategyId);
    setErrors(prev => { const n = {...prev}; delete n[strategyId]; return n; });
    try {
      const res = await api.runBacktest(selectedTicker, strategyId, parsedCapital);
      if ('error' in res) {
        setErrors(prev => ({ ...prev, [strategyId]: (res as any).error }));
      } else {
        setResults(prev => ({ ...prev, [strategyId]: res }));
        setExpandedId(strategyId);
      }
    } catch (err) {
      setErrors(prev => ({ ...prev, [strategyId]: 'Gagal terhubung ke server' }));
    } finally {
      setLoading(null);
    }
  };

  const runAllTests = async () => {
    setIsRunningAll(true);
    setResults({});
    setShowCompare(false);
    await Promise.allSettled(strategyRegistry.map(strat => runSingleTest(strat.id)));
    setIsRunningAll(false);
    setShowCompare(true);
  };

  const validResults = Object.values(results).filter(r => r.metrics);
  const rankedResults = [...validResults].sort((a, b) => b.metrics.total_return_pct - a.metrics.total_return_pct);
  const bestStrategy = rankedResults[0] ?? null;
  const bestStratInfo = strategyRegistry.find(s => s.id === bestStrategy?.strategy_id);

  const compareSeriesData = validResults
    .filter(r => r.equity_curve?.length > 1)
    .map(r => ({
      id: r.strategy_id,
      name: strategyRegistry.find(s => s.id === r.strategy_id)?.name ?? r.strategy_id,
      color: STRATEGY_COLORS[r.strategy_id] ?? '#64748b',
      data: r.equity_curve,
    }));

  return (
    <main className="min-h-screen bg-[#050505] text-white p-6 md:p-10 pt-24 md:pt-28">
      <div className="max-w-7xl mx-auto">

        {/* HEADER */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12">
          <div>
            <h1 className="text-4xl font-black tracking-tighter mb-2">Quant <span className="text-blue-500">Intelligence</span></h1>
            <p className="text-gray-500 font-mono text-[10px] uppercase tracking-widest italic">Statistical Validation Center</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {/* Ticker Input */}
            <div className="flex items-center gap-3 bg-white/5 p-2 rounded-2xl border border-white/10">
              <span className="text-[10px] font-bold text-gray-500 ml-3 uppercase tracking-widest">Asset</span>
              <input
                type="text"
                value={selectedTicker}
                onChange={(e) => { setSelectedTicker(e.target.value.toUpperCase()); setResults({}); setErrors({}); }}
                className="bg-black/40 border border-white/10 rounded-xl px-4 py-2 font-mono font-bold text-blue-400 w-24 focus:outline-none"
              />
            </div>

            {/* Modal Input */}
            <div className="flex flex-col bg-white/5 px-4 py-2 rounded-2xl border border-white/10">
              <span className="text-[8px] font-black text-gray-600 uppercase tracking-widest mb-1">Modal Simulasi</span>
              <div className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500 font-mono">Rp</span>
                <input
                  type="text"
                  value={capitalInput}
                  onChange={(e) => { setCapitalInput(e.target.value); setResults({}); setErrors({}); }}
                  className="bg-black/40 border border-white/10 rounded-xl px-3 py-1.5 font-mono font-bold text-green-400 w-36 focus:outline-none text-sm"
                  placeholder="10000000"
                />
              </div>
              <span className="text-[8px] text-gray-600 mt-1 font-mono">{formatCapitalDisplay(capitalInput)}</span>
            </div>

            <button
              onClick={runAllTests}
              disabled={isRunningAll}
              className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-4 rounded-2xl text-[10px] font-black tracking-widest shadow-xl shadow-blue-600/20 active:scale-95 disabled:opacity-50 transition-all"
            >
              {isRunningAll ? 'RUNNING ALL...' : 'RUN ALL STRATEGIES'}
            </button>
            {validResults.length >= 2 && (
              <button
                onClick={() => setShowCompare(v => !v)}
                className={`px-6 py-4 rounded-2xl text-[10px] font-black tracking-widest transition-all ${
                  showCompare
                    ? 'bg-teal-500 text-black'
                    : 'bg-white/5 border border-white/10 hover:bg-white/10 text-white'
                }`}
              >
                {showCompare ? 'HIDE COMPARE' : 'COMPARE VIEW'}
              </button>
            )}
          </div>
        </div>

        {/* BEST STRATEGY BANNER */}
        {bestStrategy && (
          <div className="mb-12 p-10 rounded-[3rem] bg-gradient-to-br from-blue-600/20 to-teal-500/10 border border-blue-500/30 backdrop-blur-2xl relative overflow-hidden">
            <div className="relative z-10 flex flex-col md:flex-row justify-between items-start gap-6">
              <div>
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-[0.5em] mb-4 block">Best Strategy for {selectedTicker}</span>
                <h2 className="text-3xl font-black mb-2">
                  {bestStratInfo?.name} <span className="text-blue-500">wins</span>
                </h2>
                <p className="text-gray-400 text-sm leading-relaxed">
                  Return <span className="text-green-400 font-black">{bestStrategy.metrics.total_return_pct}%</span>
                  {' · '}Win Rate <span className="text-blue-400 font-black">{bestStrategy.metrics.win_rate}%</span>
                  {' · '}Max DD <span className="text-red-400 font-black">{bestStrategy.metrics.max_drawdown_pct}%</span>
                </p>
              </div>
              <Link
                href={`/stocks/${selectedTicker}`}
                className="shrink-0 inline-flex items-center gap-3 bg-white text-black px-8 py-3 rounded-2xl text-[10px] font-black tracking-widest hover:bg-blue-400 hover:text-white transition-all uppercase"
              >
                Trade {selectedTicker}
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
              </Link>
            </div>
          </div>
        )}

        {/* COMPARE VIEW */}
        {showCompare && validResults.length >= 2 && (
          <div className="mb-12 space-y-6">

            {/* Ranked Table */}
            <div className="bg-white/[0.02] border border-white/5 rounded-3xl p-8">
              <p className="text-[9px] font-black text-teal-400 uppercase tracking-[0.4em] mb-6">
                Strategy Ranking — {selectedTicker} — {validResults.length} strategies tested
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="text-gray-600 text-[9px] uppercase tracking-widest border-b border-white/5">
                      <th className="text-left pb-3 pr-4 font-black">#</th>
                      <th className="text-left pb-3 pr-4 font-black">Strategy</th>
                      <th className="text-right pb-3 pr-4 font-black">Return</th>
                      <th className="text-right pb-3 pr-4 font-black">Win Rate</th>
                      <th className="text-right pb-3 pr-4 font-black">Max DD</th>
                      <th className="text-right pb-3 pr-4 font-black">Trades</th>
                      <th className="text-right pb-3 font-black">Final Value</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.03]">
                    {rankedResults.map((r, idx) => {
                      const info = strategyRegistry.find(s => s.id === r.strategy_id);
                      const color = STRATEGY_COLORS[r.strategy_id] ?? '#64748b';
                      return (
                        <tr key={r.strategy_id} className={`hover:bg-white/[0.02] transition-colors ${idx === 0 ? 'bg-blue-600/5' : ''}`}>
                          <td className="py-3 pr-4 text-gray-500 font-black text-[11px]">{idx + 1}</td>
                          <td className="py-3 pr-4">
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                              <span className="font-bold text-white text-[11px]">{info?.name ?? r.strategy_id}</span>
                              {idx === 0 && (
                                <span className="text-[7px] font-black bg-blue-500 text-black px-1.5 py-0.5 rounded uppercase">BEST</span>
                              )}
                            </div>
                          </td>
                          <td className={`py-3 pr-4 text-right font-black text-sm ${r.metrics.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {r.metrics.total_return_pct >= 0 ? '+' : ''}{r.metrics.total_return_pct}%
                          </td>
                          <td className={`py-3 pr-4 text-right font-bold ${r.metrics.win_rate >= 50 ? 'text-blue-400' : 'text-orange-400'}`}>
                            {r.metrics.win_rate}%
                          </td>
                          <td className="py-3 pr-4 text-right text-orange-400">
                            -{r.metrics.max_drawdown_pct}%
                          </td>
                          <td className="py-3 pr-4 text-right text-gray-400">
                            {r.metrics.total_trades}
                          </td>
                          <td className={`py-3 text-right font-black ${r.metrics.final_value >= r.metrics.initial_capital ? 'text-green-400' : 'text-red-400'}`}>
                            Rp {(r.metrics.final_value / 1_000_000).toFixed(1)}M
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Overlay Equity Chart */}
            {compareSeriesData.length >= 2 && (
              <div className="bg-white/[0.02] border border-white/5 rounded-3xl p-8">
                <p className="text-[9px] font-black text-teal-400 uppercase tracking-[0.4em] mb-6">
                  Equity Curve Overlay
                </p>
                <div className="rounded-2xl overflow-hidden bg-black/20 mb-5">
                  <CompareEquityChart series={compareSeriesData} height={280} />
                </div>
                <div className="flex flex-wrap gap-x-5 gap-y-2">
                  {compareSeriesData.map(s => {
                    const r = results[s.id];
                    return (
                      <div key={s.id} className="flex items-center gap-2 text-[9px] font-mono">
                        <div className="w-4 h-0.5 rounded-full" style={{ backgroundColor: s.color }} />
                        <span className="text-gray-400">{s.name}</span>
                        {r?.metrics && (
                          <span className={`font-black ${r.metrics.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {r.metrics.total_return_pct >= 0 ? '+' : ''}{r.metrics.total_return_pct}%
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* STRATEGY CARDS */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {strategyRegistry.map((strat) => {
            const res = results[strat.id];
            const isExpanded = expandedId === strat.id;
            const isBest = bestStrategy?.strategy_id === strat.id;

            return (
              <div
                key={strat.id}
                className={`rounded-3xl border transition-all duration-300 ${
                  isBest
                    ? 'bg-blue-600/10 border-blue-500/40 ring-1 ring-blue-500/20'
                    : isExpanded
                    ? 'bg-white/5 border-white/10'
                    : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.04]'
                }`}
              >
                <div className="p-8">
                  {/* Card Header */}
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <p className="text-[9px] font-bold text-gray-500 uppercase tracking-widest mb-1">{strat.indicator}</p>
                      <h3 className="text-xl font-black tracking-tight">
                        {strat.name}
                        {isBest && <span className="ml-2 text-[8px] bg-blue-500 text-black px-2 py-0.5 rounded-full uppercase font-black">BEST</span>}
                      </h3>
                    </div>
                    <div className="flex items-center gap-3">
                      {res?.metrics && (
                        <span className={`text-lg font-mono font-black ${res.metrics.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {res.metrics.total_return_pct >= 0 ? '+' : ''}{res.metrics.total_return_pct}%
                        </span>
                      )}
                      {res?.metrics && (
                        <button onClick={() => setExpandedId(isExpanded ? null : strat.id)} className="p-2 rounded-full hover:bg-white/10 transition-colors">
                          <svg className={`w-4 h-4 text-gray-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>

                  <p className="text-xs text-gray-500 leading-relaxed mb-5">{strat.description}</p>

                  {/* Rules */}
                  <div className="space-y-1.5 mb-5">
                    {strat.rules.map((rule, i) => (
                      <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
                        <div className={`w-1 h-1 rounded-full ${rule.startsWith('ENTRY') ? 'bg-green-500' : 'bg-red-500'}`} />
                        <span className={rule.startsWith('ENTRY') ? 'text-green-400/70' : 'text-red-400/70'}>{rule}</span>
                      </div>
                    ))}
                  </div>

                  <button
                    onClick={() => runSingleTest(strat.id)}
                    disabled={!!loading || isRunningAll}
                    className="bg-white/5 hover:bg-blue-600 border border-white/10 px-5 py-2 rounded-xl text-[9px] font-black tracking-widest transition-all disabled:opacity-40"
                  >
                    {loading === strat.id ? 'RUNNING...' : res?.metrics ? 'RE-RUN' : 'RUN TEST'}
                  </button>

                  {errors[strat.id] && (
                    <div className="mt-3 flex items-start gap-2 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                      <span className="text-red-400 text-lg leading-none">⚠</span>
                      <p className="text-[10px] text-red-400/80 font-mono leading-relaxed">{errors[strat.id]}</p>
                    </div>
                  )}

                  {/* EXPANDED: Metrics + Chart + Trades */}
                  {isExpanded && res?.metrics && (
                    <div className="mt-8 pt-8 border-t border-white/10 space-y-8">

                      {/* Metrics Row */}
                      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                        {[
                          { label: 'Return', value: `${res.metrics.total_return_pct}%`, color: res.metrics.total_return_pct >= 0 ? 'text-green-400' : 'text-red-400' },
                          { label: 'Win Rate', value: `${res.metrics.win_rate}%`, color: res.metrics.win_rate >= 50 ? 'text-blue-400' : 'text-orange-400' },
                          { label: 'Trades', value: res.metrics.total_trades, color: 'text-white' },
                          { label: 'Wins', value: res.metrics.wins, color: 'text-green-400' },
                          { label: 'Losses', value: res.metrics.losses, color: 'text-red-400' },
                          { label: 'Max DD', value: `-${res.metrics.max_drawdown_pct}%`, color: 'text-orange-400' },
                        ].map(({ label, value, color }) => (
                          <div key={label} className="bg-white/[0.03] rounded-2xl p-3 text-center">
                            <p className="text-[8px] text-gray-600 font-black uppercase tracking-widest mb-1">{label}</p>
                            <p className={`text-sm font-black font-mono ${color}`}>{value}</p>
                          </div>
                        ))}
                      </div>

                      {/* Equity Curve */}
                      {res.equity_curve && res.equity_curve.length > 1 && (
                        <div>
                          <p className="text-[9px] font-black text-gray-500 uppercase tracking-widest mb-3">Equity Curve</p>
                          <div className="rounded-2xl overflow-hidden bg-black/20">
                            <EquityChart data={res.equity_curve} color="#3b82f6" height={200} />
                          </div>
                          <div className="flex justify-between text-[9px] font-mono text-gray-600 mt-2 px-1">
                            <span>Initial: Rp {res.metrics.initial_capital.toLocaleString('id-ID')}</span>
                            <span className={res.metrics.final_value >= res.metrics.initial_capital ? 'text-green-400' : 'text-red-400'}>
                              Final: Rp {res.metrics.final_value.toLocaleString('id-ID')}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Trade Log */}
                      {res.trades && res.trades.length > 0 && (
                        <div>
                          <p className="text-[9px] font-black text-gray-500 uppercase tracking-widest mb-3">
                            Trade Log — {res.trades.filter(t => t.type === 'BUY').length} beli · {res.trades.filter(t => t.type === 'SELL').length} jual
                          </p>
                          <div className="max-h-64 overflow-y-auto custom-scrollbar">
                            <table className="w-full text-[9px] font-mono">
                              <thead className="sticky top-0 bg-[#050505]">
                                <tr className="text-gray-600 uppercase tracking-widest border-b border-white/5">
                                  <th className="text-left py-2 pr-3">Tanggal</th>
                                  <th className="text-left py-2 pr-3">Aksi</th>
                                  <th className="text-right py-2 pr-3">Harga</th>
                                  <th className="text-right py-2 pr-3">Lot</th>
                                  <th className="text-right py-2 pr-3">Nilai</th>
                                  <th className="text-right py-2 pr-3">Kas Sisa</th>
                                  <th className="text-right py-2 pr-3">Hold</th>
                                  <th className="text-right py-2">P&L</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-white/[0.03]">
                                {res.trades.map((t, i) => (
                                  <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                                    <td className="py-2 pr-3 text-gray-500">{t.date}</td>
                                    <td className="py-2 pr-3">
                                      <span className={`font-black px-2 py-0.5 rounded-md ${t.type === 'BUY' ? 'bg-green-500/10 text-green-400' : t.exit_reason === 'stop-loss' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/10 text-orange-400'}`}>
                                        {t.type}{t.exit_reason === 'stop-loss' ? ' ⚠' : ''}
                                      </span>
                                    </td>
                                    <td className="py-2 pr-3 text-right text-white">
                                      {t.price.toLocaleString('id-ID')}
                                    </td>
                                    <td className="py-2 pr-3 text-right text-blue-400 font-black">
                                      {t.lots ?? '-'}
                                    </td>
                                    <td className="py-2 pr-3 text-right text-gray-300">
                                      {t.total_value != null ? (t.total_value / 1_000_000).toFixed(1) + 'M' : '-'}
                                    </td>
                                    <td className="py-2 pr-3 text-right text-gray-400">
                                      {t.capital_after != null ? (t.capital_after / 1_000_000).toFixed(1) + 'M' : '-'}
                                    </td>
                                    <td className="py-2 pr-3 text-right text-gray-500">
                                      {t.hold_days != null ? `${t.hold_days}h` : '-'}
                                    </td>
                                    <td className="py-2 text-right">
                                      {t.pnl != null ? (
                                        <span className={`font-black ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                          {t.pnl >= 0 ? '+' : ''}{(t.pnl / 1_000_000).toFixed(2)}M
                                          <span className="text-[8px] ml-1 opacity-70">({t.pnl_pct?.toFixed(1)}%)</span>
                                        </span>
                                      ) : (
                                        <span className="text-gray-600">—</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
      `}</style>
    </main>
  );
}
