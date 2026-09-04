import type { Metadata } from 'next';

import AdvisorClient from './AdvisorClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'AI Advisor — EMETIQ',
  robots: { index: false },
};

export default function AdvisorPage() {
  return <AdvisorClient />;
}
