import type { Metadata } from 'next';

import DashboardClient from './DashboardClient';
import { ambilIhsg, ambilSaham, ambilSinyal, tanggalAwalIhsg } from '@/lib/marketServer';

export const metadata: Metadata = {
  title: 'Dashboard - EMETIQ',
};

/**
 * Komponen server: data pasar diambil di sini, bukan di browser.
 *
 * Sebelumnya halaman ini `'use client'` dan menembak tiga permintaan di
 * `useEffect`, jadi urutannya: kirim cangkang kosong -> unduh bundel JS ->
 * hidrasi React -> baru permintaan pertama berangkat -> tunggu ~4 detik.
 * Itu sumber "kedip-kedip"-nya.
 *
 * Sekarang ketiganya berjalan di server, paralel, dan hasilnya di-cache
 * bersama semua pengunjung selama lima menit. Bersama `loading.tsx`, pembaca
 * langsung melihat kerangka halaman sementara isinya di-stream menyusul.
 *
 * Portofolio TIDAK ikut ke sini: ia butuh token Supabase yang hidup di browser
 * (lihat `lib/api.ts`), jadi ia tetap diambil komponen klien setelah hidrasi.
 */
export default async function Dashboard() {
  const [saham, ihsg, sinyal] = await Promise.all([
    ambilSaham(),
    ambilIhsg(tanggalAwalIhsg()),
    ambilSinyal(),
  ]);

  return (
    <DashboardClient
      sahamAwal={saham ?? []}
      ihsgAwal={ihsg?.data ?? []}
      sinyalAwal={sinyal ?? []}
    />
  );
}
