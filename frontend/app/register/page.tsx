import type { Metadata } from 'next';

import RegisterClient from './RegisterClient';

/** Pembungkus metadata — lihat catatan pola di `app/page.tsx`. */
export const metadata: Metadata = {
  title: 'Daftar — EMETIQ',
  description: 'Buat akun EMETIQ gratis dan mulai memantau saham IDX.',
};

export default function RegisterPage() {
  return <RegisterClient />;
}
