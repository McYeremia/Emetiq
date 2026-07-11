import { notFound } from 'next/navigation';

import { isBigMoneyEnabled } from '@/lib/flags';
import BigMoneyClient from './BigMoneyClient';

/** Gerbang dev-mode. Server component supaya rute benar-benar 404 di produksi —
 *  menyembunyikan lewat CSS atau redirect di klien berarti HTML-nya tetap terkirim. */
export default function BigMoneyPage() {
  if (!isBigMoneyEnabled) notFound();

  return <BigMoneyClient />;
}
