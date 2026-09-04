import type { Metadata } from 'next';

import LandingClient from './LandingClient';

/**
 * Pembungkus server untuk metadata. Pola yang sama dipakai 12 halaman sejak
 * 4 Sep 2026; catatan lengkapnya ada di sini, yang lain hanya menunjuk ke sini.
 *
 * MASALAHNYA: 12 halaman menyetel judulnya lewat `document.title` di dalam
 * `useEffect`. Itu berjalan SETELAH hidrasi, jadi HTML yang benar-benar terkirim
 * membawa judul dari root layout untuk semua halaman. Yang melihat judul asli
 * hanyalah pengunjung yang menjalankan JS; perayap mesin pencari, pratinjau
 * tautan WhatsApp/Telegram, dan riwayat browser melihat "EMETIQ — Monitoring
 * Saham" di mana-mana. Terukur di HTML hasil `next build`: 2 dari 14 rute punya
 * judulnya sendiri.
 *
 * BENTUK PERBAIKANNYA: `metadata` hanya boleh diekspor server component,
 * sementara halaman-halaman ini `'use client'` karena memang penuh interaksi.
 * Jadi isinya dipindahkan apa adanya ke `XxxClient.tsx` (tanpa satu baris pun
 * berubah selain `document.title` yang dibuang), dan `page.tsx` menjadi
 * pembungkus server setipis ini. Nol biaya di sisi klien: bundelnya sama, cuma
 * judulnya kini ikut di byte pertama.
 *
 * Halaman di balik `RequireAuth` diberi `robots: { index: false }` — yang
 * dilihat perayap di sana cuma dinding login, dan itu tak layak masuk indeks.
 */
export const metadata: Metadata = {
  title: 'EMETIQ — Monitoring Saham',
  description:
    'Pantau saham IDX dalam satu layar: watchlist, portofolio, screener teknikal, dan AI Advisor.',
};

export default function LandingPage() {
  return <LandingClient />;
}
