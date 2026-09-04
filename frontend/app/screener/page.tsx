import type { Metadata } from 'next';

import ScreenerClient from './ScreenerClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Screener — EMETIQ',
  robots: { index: false },
};

export default function ScreenerPage() {
  return <ScreenerClient />;
}
