import type { Metadata } from 'next';

import OverviewClient from './OverviewClient';
import { ambilIhsg, ambilSaham, tanggalAwalIhsg } from '@/lib/marketServer';

export const metadata: Metadata = {
  title: 'Overview - EMETIQ',
};

/** Lihat catatan di `app/dashboard/page.tsx` — pola yang sama: data pasar
 *  diambil di server dan di-cache bersama, watchlist tetap di klien karena
 *  butuh token login. */
export default async function Overview() {
  const [saham, ihsg] = await Promise.all([
    ambilSaham(),
    ambilIhsg(tanggalAwalIhsg()),
  ]);

  return <OverviewClient sahamAwal={saham ?? []} ihsgAwal={ihsg?.data ?? []} />;
}
