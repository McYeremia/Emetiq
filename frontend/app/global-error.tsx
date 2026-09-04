'use client';

import PesanGalat, { tombolUtama } from '@/components/PesanGalat';

/**
 * Jaring terakhir: galat yang terjadi di ROOT LAYOUT sendiri — mis. `AuthProvider`
 * melempar saat memeriksa sesi. `app/error.tsx` tak bisa menangkapnya, karena ia
 * hidup DI DALAM layout yang barusan gagal.
 *
 * Karena layout-nya tak jadi dipakai, berkas ini wajib menyediakan `<html>` dan
 * `<body>` sendiri — dan sengaja tak bergantung pada apa pun yang bisa ikut rusak:
 * tak ada `next/font` (tumpukan font sistem saja), tak ada provider, tak ada
 * `next/link`. Tautannya `<a>` biasa supaya ia memuat ulang halaman dari nol,
 * yang justru diinginkan ketika kerangka aplikasinya sendiri yang bermasalah.
 *
 * Judulnya dipasang lewat komponen `<title>` React, bukan ekspor `metadata`:
 * dokumentasi Next 16 menyebut `metadata`/`generateMetadata` TIDAK didukung di
 * `global-error` justru karena berkas ini wajib client component. Tanpa itu, tab
 * browser menampilkan URL mentah — terbukti saat layar ini diuji.
 *
 * Layar ini nyaris tak pernah muncul. Kalau ia muncul, ia harus tetap tampil benar.
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="id">
      <body style={{ margin: 0, fontFamily: 'system-ui, -apple-system, Segoe UI, sans-serif' }}>
        <title>EMETIQ gagal dimuat</title>
        <PesanGalat
          kode="500"
          judul="EMETIQ gagal dimuat"
          penjelasan="Aplikasinya berhenti sebelum sempat tampil. Muat ulang biasanya cukup; kalau berulang, sertakan kode kejadian di bawah saat melapor."
          jejak={error.digest}
        >
          <button type="button" onClick={reset} style={tombolUtama}>Muat ulang</button>
        </PesanGalat>
      </body>
    </html>
  );
}
