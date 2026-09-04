import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import { isBigMoneyEnabled } from '@/lib/flags';
import BigMoneyClient from './BigMoneyClient';

/** Judulnya dulu disetel `document.title` di dalam BigMoneyClient — lihat
 *  catatan pola di `app/page.tsx`. Halaman ini sudah server component sejak awal,
 *  jadi cukup menambah ekspor di bawah. */
export const metadata: Metadata = {
  title: 'Big Money — EMETIQ',
  robots: { index: false },
};

/** Gerbang dev-mode. Server component supaya rute benar-benar 404 di produksi —
 *  menyembunyikan lewat CSS atau redirect di klien berarti HTML-nya tetap terkirim. */
export default function BigMoneyPage() {
  if (!isBigMoneyEnabled) notFound();

  return <BigMoneyClient />;
}
