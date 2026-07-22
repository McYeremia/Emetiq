'use client';

import { useEffect, useRef } from 'react';

/** Jeda default: 5 menit.
 *
 * Sebelumnya 30 detik, yang berarti satu tab menganggur menarik ulang seluruh
 * daftar saham 2.880 kali sehari. Tak ada gunanya: harga di aplikasi ini berasal
 * dari `daily_sync` yang jalan sekali sehari setelah bursa tutup, dan sinyal dari
 * `scan_market_signals` di run yang sama. Menyegarkan tiap 30 detik menarik data
 * yang persis sama, berulang-ulang, lewat bandwidth Space gratis. */
export const JEDA_MUAT_ULANG = 5 * 60 * 1000;

/**
 * Panggil `muat` secara berkala, tapi hanya selama tab benar-benar dilihat.
 *
 * Tab yang tersembunyi tidak menarik apa pun. Saat pengguna kembali, data
 * disegarkan langsung bila yang ada sudah lebih tua dari satu jeda — jadi
 * layar tak pernah menampilkan angka basi, tanpa membayar polling saat
 * tak seorang pun melihat.
 */
export function usePollingSaatTerlihat(
  muat: () => void,
  { jedaMs = JEDA_MUAT_ULANG, muatSegera = true }: {
    jedaMs?: number;
    /** Setel `false` bila data awal sudah dikirim server — tanpa ini komponen
     *  langsung menembak ulang permintaan yang barusan dijawab. */
    muatSegera?: boolean;
  } = {},
) {
  // Ref supaya closure `muat` yang baru selalu terpakai tanpa memasang ulang
  // interval tiap render
  const muatRef = useRef(muat);
  muatRef.current = muat;

  const terakhirMs = useRef(0);

  useEffect(() => {
    const jalankan = () => {
      terakhirMs.current = Date.now();
      muatRef.current();
    };

    if (muatSegera) jalankan();
    else terakhirMs.current = Date.now();   // data server dianggap baru

    const interval = setInterval(() => {
      if (document.visibilityState === 'visible') jalankan();
    }, jedaMs);

    const saatKembali = () => {
      if (document.visibilityState !== 'visible') return;
      // Jangan menembak tiap kali pengguna berpindah tab sekilas
      if (Date.now() - terakhirMs.current >= jedaMs) jalankan();
    };
    document.addEventListener('visibilitychange', saatKembali);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', saatKembali);
    };
  }, [jedaMs, muatSegera]);
}
