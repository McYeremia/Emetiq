import type { Metadata } from 'next';

import ProfileClient from './ProfileClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Profil — EMETIQ',
  robots: { index: false },
};

export default function ProfilePage() {
  return <ProfileClient />;
}
