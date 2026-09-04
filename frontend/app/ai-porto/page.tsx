import type { Metadata } from 'next';

import AiPortoClient from './AiPortoClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'AI Porto — EMETIQ',
  robots: { index: false },
};

export default function AiPortoPage() {
  return <AiPortoClient />;
}
