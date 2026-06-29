'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api, OHLCV } from '@/lib/api';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const StockChart = dynamic(() => import('@/components/StockChart'), { ssr: false });

type TradeDetail = Awaited<ReturnType<typeof api.getTradeDetail>>;

const AGENT_COLOR: Record<string, string> = {
  USER:   'text-blue-400 bg-blue-500/10 border-blue-500/20',
  GEMINI: 'text-teal-400 bg-teal-500/10 border-teal-500/20',
  CLAUDE: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
};

export default function TradeDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [trade, setTrade] = useState<TradeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.getTradeDetail(Number(id))
      .then(setTrade)
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center text-blue-500 font-mono text-xs uppercase tracking-widest animate-pulse">
      Loading Trade Data...
    </div>
  );

  if (error || !trade) return (
    <div className="min-h-screen bg-[#050505] flex flex-col items-center justify-center gap-4 text-white font-mono">
      <p className="text-red-400 text-sm uppercase tracking-widest font-black">Trade Not Found</p>
      <Link href="/portfolio" className="text-xs text-gray-500 hover:text-white transition-colors">← Kembali ke Portfolio</Link>
    </div>
  );

  const isBuy  = trade.action === 'BUY';
  const hasPnl = trade.pnl !== null && trade.pnl_pct !== null;
  const profitColor = (v: number) => v >= 0 ? 'text-green-400' : 'text-red-400';
  const profitBg    = (v: number) => v >= 0
    ? 'bg-green-500/10 border-green-500/20'
    : 'bg-red-500/10 border-red-500/20';

  return (
    <main className="min-h-screen bg-[#050505] text-white p-6 md:p-10 pt-24 md:pt-28 font-mono">
      <div className="max-w-4xl mx-auto">

        {/* BACK */}
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-[9px] font-black uppercase tracking-widest text-gray-600 hover:text-white transition-colors mb-8 group"
        >
          <span className="group-hover:-translate-x-1 transition-transform">←</span>
          Kembali
        </button>

        {/* HEADER */}
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-6 mb-8">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`text-[9px] font-black px-3 py-1 rounded-full uppercase tracking-widest border ${
                isBuy
                  ? 'bg-green-500/10 text-green-400 border-green-500/20'
                  : 'bg-red-500/10 text-red-400 border-red-500/20'
              }`}>
                {trade.action}
              </span>
              <span className={`text-[9px] font-black px-3 py-1 rounded-full uppercase tracking-widest border ${AGENT_COLOR[trade.agent]}`}>
                {trade.agent}
              </span>
              <span className="text-[9px] font-black px-3 py-1 rounded-full uppercase tracking-widest border border-white/10 bg-white/5 text-gray-400">
                #{trade.id}
              </span>
            </div>
            <h1 className="text-4xl font-black tracking-tighter leading-none mb-1">
              <Link href={`/stocks/${trade.ticker}`} className="hover:text-blue-400 transition-colors">
                {trade.ticker}
              </Link>
            </h1>
            <p className="text-gray-500 text-xs uppercase tracking-widest">{trade.name}</p>
            {trade.sector && (
              <p className="text-gray-700 text-[9px] uppercase tracking-widest mt-0.5">{trade.sector}</p>
            )}
          </div>
          <div className="text-right shrink-0">
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-1">Tanggal Transaksi</p>
            <p className="text-xl font-black">{trade.date}</p>
          </div>
        </div>

        {/* CHART */}
        {trade.ohlcv.length > 5 && (
          <div className="bg-white/[0.02] border border-white/5 rounded-3xl p-6 mb-6 shadow-2xl">
            <div className="flex justify-between items-center mb-4">
              <p className="text-[9px] font-black uppercase tracking-widest text-gray-500">
                Grafik Harga — 90 hari sebelum transaksi
              </p>
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${isBuy ? 'bg-green-400' : 'bg-red-400'}`} />
                <span className="text-[9px] font-mono text-gray-500">
                  {isBuy ? 'Entry' : 'Exit'} @ Rp {trade.price.toLocaleString('id-ID')}
                </span>
              </div>
            </div>
            <StockChart
              data={trade.ohlcv as OHLCV[]}
              height={200}
              transparent
              markerDate={trade.date}
              markerColor={isBuy ? '#22c55e' : '#ef4444'}
            />
          </div>
        )}

        {/* CORE STATS */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-2">Harga Transaksi</p>
            <p className="text-2xl font-black">Rp {trade.price.toLocaleString('id-ID')}</p>
          </div>
          <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-2">Volume</p>
            <p className="text-2xl font-black">{trade.quantity_lots} <span className="text-gray-500 text-sm font-bold">LOT</span></p>
            <p className="text-[9px] font-mono text-gray-600 mt-1">{trade.quantity_shares.toLocaleString('id-ID')} lembar</p>
          </div>
          <div className={`rounded-2xl p-6 border ${isBuy ? 'bg-red-500/5 border-red-500/10' : 'bg-green-500/5 border-green-500/10'}`}>
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-2">Total Nilai</p>
            <p className={`text-2xl font-black ${isBuy ? 'text-red-400' : 'text-green-400'}`}>
              {isBuy ? '-' : '+'}Rp {trade.total_value.toLocaleString('id-ID')}
            </p>
          </div>
        </div>

        {/* P&L SECTION (hanya untuk SELL) */}
        {hasPnl && (
          <div className={`rounded-2xl p-6 border mb-6 ${profitBg(trade.pnl!)}`}>
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-500 mb-4">Hasil Transaksi (Realized P&L)</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Avg Buy Price</p>
                <p className="text-lg font-black font-mono">
                  Rp {trade.avg_buy_price?.toLocaleString('id-ID')}
                </p>
              </div>
              <div>
                <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Harga Jual</p>
                <p className="text-lg font-black font-mono">Rp {trade.price.toLocaleString('id-ID')}</p>
              </div>
              <div>
                <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Realized P&L</p>
                <p className={`text-2xl font-black font-mono ${profitColor(trade.pnl!)}`}>
                  {trade.pnl! >= 0 ? '+' : ''}Rp {Math.abs(trade.pnl!).toLocaleString('id-ID', { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div>
                <p className="text-[9px] text-gray-600 uppercase tracking-widest mb-1">Return</p>
                <p className={`text-2xl font-black font-mono ${profitColor(trade.pnl_pct!)}`}>
                  {trade.pnl_pct! >= 0 ? '+' : ''}{trade.pnl_pct?.toFixed(2)}%
                </p>
              </div>
            </div>
          </div>
        )}

        {/* STRATEGY & NOTES */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-3">Strategi</p>
            <span className="text-xs font-black bg-blue-500/10 border border-blue-500/20 text-blue-400 px-3 py-1.5 rounded-full uppercase tracking-widest">
              {trade.strategy}
            </span>
          </div>
          <div className="md:col-span-2 bg-white/[0.02] border border-white/5 rounded-2xl p-6">
            <p className="text-[9px] font-black uppercase tracking-widest text-gray-600 mb-3">Reasoning / Catatan</p>
            {trade.notes ? (
              <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{trade.notes}</p>
            ) : (
              <p className="text-xs text-gray-700 italic">Tidak ada catatan</p>
            )}
          </div>
        </div>

        {/* FOOTER LINKS */}
        <div className="flex gap-4 pt-4 border-t border-white/5">
          <Link
            href={`/stocks/${trade.ticker}`}
            className="text-[9px] font-black uppercase tracking-widest text-gray-500 hover:text-blue-400 transition-colors"
          >
            Lihat Saham {trade.ticker} →
          </Link>
          <Link
            href="/portfolio"
            className="text-[9px] font-black uppercase tracking-widest text-gray-500 hover:text-white transition-colors"
          >
            Kembali ke Portfolio →
          </Link>
        </div>

      </div>
    </main>
  );
}
