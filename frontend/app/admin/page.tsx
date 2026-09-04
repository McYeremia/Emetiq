import type { Metadata } from 'next';

import AdminClient from './AdminClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Admin — EMETIQ',
  robots: { index: false },
};

export default function AdminPage() {
  return <AdminClient />;
}
