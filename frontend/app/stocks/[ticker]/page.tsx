import type { Metadata } from 'next';

import StockDetailClient from './StockDetailClient';

/**
 * Satu-satunya halaman yang judulnya ikut isi, jadi ia memakai
 * `generateMetadata`, bukan `metadata` statis — lihat catatan pola di
 * `app/page.tsx`.
 *
 * `params` adalah Promise sejak Next 15; menunggunya di sini tak menambah
 * permintaan apa pun, tickernya sudah ada di URL.
 *
 * Ticker sengaja TIDAK divalidasi ke backend di sini. Halaman ini dirender
 * dinamis untuk ribuan ticker; menembak API cuma demi judul berarti satu
 * permintaan tambahan di server untuk tiap kunjungan, sementara kliennya toh
 * langsung menariknya sendiri. Ticker ngawur akan tetap membalas 200 dengan
 * judulnya sendiri — itu perilaku yang sama seperti sebelum perubahan ini.
 */
export async function generateMetadata(
  { params }: { params: Promise<{ ticker: string }> },
): Promise<Metadata> {
  const { ticker } = await params;
  const kode = decodeURIComponent(ticker).toUpperCase();

  return {
    title: `${kode} — EMETIQ`,
    description: `Harga, grafik, dan indikator teknikal saham ${kode} di Bursa Efek Indonesia.`,
  };
}

export default function StockDetailPage() {
  return <StockDetailClient />;
}
