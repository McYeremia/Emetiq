'use client';

import { useEffect, useState, useCallback } from 'react';
import { api, BrokerFlowEntry, BrokerFlowResponse } from '@/lib/api';

function fmtValue(n: number) {
  if (n >= 1_000_000_000_000) return `${(n / 1_000_000_000_000).toFixed(1)}T`;
  if (n >= 1_000_000_000)     return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000)         return `${(n / 1_000_000).toFixed(0)}M`;
  return n.toLocaleString('id-ID');
}

function fmtLots(n: number) {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}jt`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(0)}rb`;
  return n.toLocaleString('id-ID');
}

type SortKey = 'total_value' | 'volume' | 'frequency';

export default function BrokerFlowPage() {
  useEffect(() => { document.title = 'Broker Flow — IDXAnalyst'; }, []);
  const [data, setData]             = useState<BrokerFlowResponse | null>(null);
  const [dates, setDates]           = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [loading, setLoading]       = useState(false);
  const [scraping, setScraping]     = useState(false);
  const [scrapeMsg, setScrapeMsg]   = useState('');
  const [sortKey, setSortKey]       = useState<SortKey>('total_value');
  const [sortDir, setSortDir]       = useState<'asc' | 'desc'>('desc');

  const loadDates = useCallback(async () => {
    const res = await api.getBrokerFlowDates().catch(() => ({ dates: [] }));
    setDates(res.dates);
    setSelectedDate(prev => (prev || res.dates[0] || ''));
  }, []);

  useEffect(() => { loadDates(); }, []);

  const loadData = useCallback(async (date: string) => {
    if (!date) return;
    setLoading(true);
    try {
      const res = await api.getBrokerFlow(date);
      setData(res);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedDate) loadData(selectedDate);
  }, [selectedDate, loadData]);

  const handleScrape = async () => {
    setScraping(true);
    setScrapeMsg('');
    try {
      const res = await api.scrapeBrokerFlow(selectedDate || undefined);
      if (res.status === 'ok') {
        setScrapeMsg(`✓ Berhasil menyimpan data ${res.brokers_saved} broker`);
        await loadDates();
        if (selectedDate) loadData(selectedDate);
      } else {
        setScrapeMsg(`✗ ${res.detail || 'Gagal scrape'}`);
      }
    } catch {
      setScrapeMsg('✗ Gagal menghubungi server');
    } finally {
      setScraping(false);
    }
  };

  const sorted: BrokerFlowEntry[] = data?.data
    ? [...data.data].sort((a, b) => {
        const diff = a[sortKey] - b[sortKey];
        return sortDir === 'desc' ? -diff : diff;
      })
    : [];

  const top10 = data?.data
    ? [...data.data]
        .sort((a, b) => b.total_value - a.total_value)
        .slice(0, 10)
    : [];

  const maxVal = Math.max(...top10.map(r => r.total_value), 1);

  function toggleSort(key: SortKey) {
    if (sortKey === key) setSortDir(d => (d === 'desc' ? 'asc' : 'desc'));
    else { setSortKey(key); setSortDir('desc'); }
  }

  function SortIcon({ k }: { k: SortKey }) {
    if (sortKey !== k) return <span className="text-white/20 ml-1">↕</span>;
    return <span className="text-[#3B82F6] ml-1">{sortDir === 'desc' ? '↓' : '↑'}</span>;
  }

  const totalValue = data?.data.reduce((s, r) => s + r.total_value, 0) ?? 0;
  const totalVol   = data?.data.reduce((s, r) => s + r.volume, 0) ?? 0;

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white selection:bg-[#3B82F6]/40">
      <div className="max-w-[1400px] mx-auto px-6 pt-[80px] pb-16">

        {/* ── HEADER ──────────────────────────────────────────────── */}
        <div className="border-b border-white/10 pb-6 mb-8 flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div>
            <div className="text-[9px] font-mono text-[#3B82F6] tracking-[0.4em] uppercase mb-2">◆ BROKER ACTIVITY</div>
            <h1 className="text-3xl font-black uppercase tracking-tight">BROKER MARKET SUMMARY</h1>
            <p className="text-gray-500 text-sm mt-1">
              Aktivitas broker IDX harian — total nilai, volume, dan frekuensi transaksi per sekuritas
            </p>
            <p className="text-[9px] font-mono text-gray-700 mt-1 tracking-wider">
              Source: idx.co.id · Data aggregate seluruh pasar, bukan per-saham
            </p>
          </div>
          <div className="flex flex-col gap-2 items-start md:items-end shrink-0">
            <button
              onClick={handleScrape}
              disabled={scraping}
              className="px-6 py-3 text-[10px] font-black tracking-[0.2em] uppercase bg-[#3B82F6] hover:bg-blue-400 disabled:opacity-50 transition-colors"
            >
              {scraping ? 'MENGAMBIL DATA IDX...' : 'SCRAPE HARI INI'}
            </button>
            {scrapeMsg && (
              <span className={`text-[9px] font-mono tracking-wider ${scrapeMsg.startsWith('✓') ? 'text-[#22C55E]' : 'text-[#EF4444]'}`}>
                {scrapeMsg}
              </span>
            )}
          </div>
        </div>

        {/* ── DATE SELECTOR ───────────────────────────────────────── */}
        <div className="mb-8 flex flex-wrap items-center gap-4">
          <div>
            <div className="text-[8px] font-mono text-gray-600 tracking-[0.3em] uppercase mb-2">PILIH TANGGAL</div>
            {dates.length > 0 ? (
              <select
                value={selectedDate}
                onChange={e => setSelectedDate(e.target.value)}
                className="bg-[#111] border border-white/15 px-4 py-2.5 text-sm font-mono text-white focus:outline-none focus:border-[#3B82F6]"
              >
                {dates.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            ) : (
              <div className="text-[10px] font-mono text-gray-600 px-4 py-2.5 border border-white/10">
                Belum ada data — klik "SCRAPE HARI INI"
              </div>
            )}
          </div>
        </div>

        {/* ── LOADING ─────────────────────────────────────────────── */}
        {loading && (
          <div className="border border-white/10 p-16 text-center">
            <p className="text-[#3B82F6] font-mono text-sm tracking-wider animate-pulse">MEMUAT DATA...</p>
          </div>
        )}

        {/* ── NO DATA ─────────────────────────────────────────────── */}
        {!loading && !data && dates.length === 0 && (
          <div className="border border-white/10 p-16 text-center">
            <p className="text-gray-600 font-mono text-sm mb-2">Belum ada data broker tersimpan</p>
            <p className="text-gray-700 font-mono text-xs">Klik "SCRAPE HARI INI" untuk mengambil data dari IDX</p>
          </div>
        )}

        {/* ── DATA ────────────────────────────────────────────────── */}
        {!loading && data && data.data.length > 0 && (
          <>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 border border-white/10 mb-6">
              {[
                { label: 'TANGGAL',       val: data.date ?? '—',          color: 'text-gray-300' },
                { label: 'TOTAL NILAI',   val: `Rp ${fmtValue(totalValue)}`, color: 'text-[#3B82F6]' },
                { label: 'TOTAL VOLUME',  val: `${fmtLots(totalVol)} lot`,  color: 'text-[#22C55E]' },
                { label: 'ACTIVE BROKER', val: String(data.data.length),    color: 'text-white' },
              ].map((c, i) => (
                <div key={i} className="px-5 py-4 border-r border-b border-white/10 last:border-r-0 md:border-b-0">
                  <div className="text-[8px] font-mono text-gray-600 tracking-[0.3em] uppercase mb-1">{c.label}</div>
                  <div className={`text-lg font-black tabular-nums ${c.color}`}>{c.val}</div>
                </div>
              ))}
            </div>

            {/* Bar chart top 10 */}
            <div className="border border-white/10 mb-6">
              <div className="border-b border-white/10 px-5 py-3">
                <span className="text-[9px] font-mono text-[#3B82F6] tracking-[0.3em] uppercase">
                  ◆ TOP 10 BROKER BY NILAI TRANSAKSI
                </span>
              </div>
              <div className="p-5 space-y-2">
                {top10.map((row, i) => {
                  const pct = (row.total_value / maxVal) * 100;
                  const colors = ['#3B82F6','#60A5FA','#93C5FD','#BFDBFE','#DBEAFE'];
                  const color  = colors[Math.min(i, colors.length - 1)];
                  return (
                    <div key={row.broker_code} className="flex items-center gap-3">
                      <span className="text-[8px] font-mono text-gray-700 w-4 tabular-nums shrink-0">{i + 1}</span>
                      <span className="text-[9px] font-black text-gray-300 w-8 shrink-0">{row.broker_code}</span>
                      <div className="flex-1 h-5 bg-white/[0.03] relative overflow-hidden">
                        <div
                          className="h-full transition-all duration-500"
                          style={{ width: `${pct}%`, backgroundColor: color + '40', borderRight: `2px solid ${color}` }}
                        />
                      </div>
                      <span className="text-[9px] font-black tabular-nums w-20 text-right shrink-0" style={{ color }}>
                        {fmtValue(row.total_value)}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Full table */}
            <div className="border border-white/10">
              <div className="border-b border-white/10 px-5 py-3 flex items-center justify-between">
                <span className="text-[9px] font-mono text-[#3B82F6] tracking-[0.3em] uppercase">
                  ◆ ALL BROKERS — {data.data.length} SEKURITAS
                </span>
                <span className="text-[8px] font-mono text-gray-700">Klik header untuk sort</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr className="border-b border-white/10 bg-[#0F0F0F]">
                      {(
                        [
                          { key: null,          label: '#' },
                          { key: null,          label: 'KODE' },
                          { key: null,          label: 'NAMA SEKURITAS' },
                          { key: 'total_value', label: 'NILAI TRANSAKSI' },
                          { key: 'volume',      label: 'VOLUME (LOT)' },
                          { key: 'frequency',   label: 'FREKUENSI' },
                        ] as { key: SortKey | null; label: string }[]
                      ).map((col, i) => (
                        <th
                          key={i}
                          onClick={col.key ? () => toggleSort(col.key!) : undefined}
                          className={`px-4 py-3 text-[8px] font-mono tracking-[0.25em] uppercase text-gray-600 whitespace-nowrap ${
                            col.key ? 'cursor-pointer hover:text-gray-300 select-none' : ''
                          }`}
                        >
                          {col.label}
                          {col.key && <SortIcon k={col.key} />}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {sorted.map((row, i) => (
                      <tr key={row.broker_code} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-2.5 text-[9px] font-mono text-gray-700 tabular-nums">{i + 1}</td>
                        <td className="px-4 py-2.5 text-[10px] font-black text-white">{row.broker_code}</td>
                        <td className="px-4 py-2.5 text-[10px] font-mono text-gray-400 max-w-[220px] truncate">
                          {row.broker_name || '—'}
                        </td>
                        <td className="px-4 py-2.5 text-[10px] font-black text-[#3B82F6] tabular-nums">
                          Rp {fmtValue(row.total_value)}
                        </td>
                        <td className="px-4 py-2.5 text-[10px] font-mono text-gray-300 tabular-nums">
                          {fmtLots(row.volume)}
                        </td>
                        <td className="px-4 py-2.5 text-[10px] font-mono text-gray-500 tabular-nums">
                          {row.frequency.toLocaleString('id-ID')}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
