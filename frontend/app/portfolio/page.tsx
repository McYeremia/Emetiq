import type { Metadata } from 'next';

import PortfolioClient from './PortfolioClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Portofolio — EMETIQ',
  robots: { index: false },
};

export default function PortfolioPage() {
  return <PortfolioClient />;
}
