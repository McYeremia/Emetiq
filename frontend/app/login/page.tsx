import type { Metadata } from 'next';

import LoginClient from './LoginClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Masuk — EMETIQ',
  description: 'Masuk ke EMETIQ untuk membuka watchlist, portofolio, dan AI Advisor.',
};

export default function LoginPage() {
  return <LoginClient />;
}
