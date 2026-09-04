'use client';

import PesanGalat, { tombolKedua, tombolUtama } from '@/components/PesanGalat';

/**
 * Batas galat untuk seluruh isi aplikasi. Next mewajibkan berkas ini client
 * component — ia harus bisa memasang `onClick` untuk `reset()`.
 *
 * `reset()` merender ulang segmen yang gagal TANPA memuat ulang halaman. Itu yang
 * paling sering menolong di sini: penyebab galat yang wajar di aplikasi ini adalah
 * backend yang sedang bangun dari tidur (Space gratis tidur saat idle, permintaan
 * pertamanya bisa gagal), dan percobaan kedua beberapa detik kemudian berhasil.
 *
 * `error.message` sengaja TIDAK ditampilkan: di produksi Next menyensornya jadi
 * teks generik, dan menampilkan pesan mentah dari server hanya membocorkan bentuk
 * dalam aplikasi tanpa menolong siapa pun. Yang ditampilkan `error.digest` —
 * penanda yang bisa dicocokkan dengan log server.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <PesanGalat
      kode="500"
      judul="Ada yang gagal dimuat"
      penjelasan="Halaman ini berhenti di tengah jalan. Biasanya sesaat saja — coba lagi dulu sebelum menyimpulkan datanya bermasalah."
      jejak={error.digest}
    >
      <button type="button" onClick={reset} style={tombolUtama}>Coba lagi</button>
      <a href="/overview" style={tombolKedua}>Ke Overview</a>
    </PesanGalat>
  );
}
