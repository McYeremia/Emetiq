import type { Metadata } from 'next';

import PesanGalat, { tombolKedua, tombolUtama } from '@/components/PesanGalat';

export const metadata: Metadata = {
  title: 'Halaman tak ditemukan — EMETIQ',
  // Halaman ini tak boleh masuk indeks: sebuah 404 yang terindeks membuat mesin
  // pencari menawarkan tautan mati kepada orang yang mencari EMETIQ.
  robots: { index: false, follow: true },
};

/**
 * 404 kustom. Server component, jadi HTML-nya utuh di byte pertama — perayap dan
 * pratinjau tautan tak perlu menjalankan JS untuk tahu ini halaman hilang.
 *
 * Ia juga yang muncul saat `notFound()` dipanggil, dan itu jalur nyata di
 * aplikasi ini: `app/big-money/page.tsx` memakainya sebagai gerbang dev-mode.
 */
export default function NotFound() {
  return (
    <PesanGalat
      kode="404"
      judul="Halaman ini tidak ada"
      penjelasan="Alamatnya mungkin salah ketik, atau halamannya sudah dipindahkan. Kode saham yang tak terdaftar di IDX juga berakhir di sini."
    >
      <a href="/overview" style={tombolUtama}>Ke Overview</a>
      <a href="/dashboard" style={tombolKedua}>Lihat pasar</a>
    </PesanGalat>
  );
}
