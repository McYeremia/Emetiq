import type { Metadata } from 'next';

import CallbackClient from './CallbackClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Masuk — EMETIQ',
  robots: { index: false },
};

export default function AuthCallbackPage() {
  return <CallbackClient />;
}
