'use client';

import { useSyncExternalStore } from 'react';

const REDUP = '#8A8A82';
const PERINGATAN = '#B7791F';

/** Di atas ini, label berubah jadi peringatan berwarna.
 *
 *  Tujuh hari kalender ≈ lima hari bursa ditambah akhir pekan. Data yang lebih tua
 *  dari itu berarti sinkronisasi harian gagal beberapa kali berturut-turut, atau
 *  sahamnya memang disuspensi — dua hal yang harus terlihat, bukan disembunyikan. */
const AMBANG_HARI = 7;

// Tak pernah berubah setelah hidrasi, jadi tak perlu berlangganan apa pun.
const tanpaLangganan = () => () => {};

// "Sekarang" versi browser, dibaca SEKALI lalu dibekukan.
//
// Dua alasan, dan keduanya penting:
//
// 1. `useSyncExternalStore` mewajibkan snapshot yang stabil — kalau `Date.now()`
//    dipanggil tiap kali, tiap pembacaan memberi nilai baru dan React merender tanpa
//    henti.
// 2. Membacanya langsung di badan komponen adalah pembacaan tak murni saat render
//    (React 19 melarangnya, dan lint repo ini menangkapnya). Di sini ia hidup di luar
//    render, dipanggil React lewat snapshot.
//
// Membekukannya tidak masalah: yang dihitung umur data dalam HARI, dan halaman ini
// tak pernah terbuka cukup lama untuk membuat selisihnya berarti.
let sekarangKlien: number | null = null;

function sekarangDiKlien(): number {
  if (sekarangKlien === null) sekarangKlien = Date.now();
  return sekarangKlien;
}

/** `null` saat dirender di server, cap waktu browser setelah hidrasi.
 *
 *  Halaman ini dirender lebih dulu di server dan HTML-nya dipakai ulang sampai lima
 *  menit (ISR), jadi "sekarang" versi server bisa berjam-jam lebih tua daripada versi
 *  browser — dan React menganggap perbedaan hasilnya sebagai ketidakcocokan hidrasi.
 *  `useSyncExternalStore` adalah cara React sendiri menyatakan "nilai ini hanya ada
 *  di klien", tanpa efek maupun setState. */
function useSekarang(): number | null {
  return useSyncExternalStore(tanpaLangganan, sekarangDiKlien, () => null);
}

/**
 * Label kecil "Data 3 Sep 2026" di dekat angka pasar.
 *
 * Sebelum 4 Sep 2026 aplikasi ini **tak pernah** menampilkan tanggal data di mana
 * pun. Akibatnya tak ada cara membedakan harga hasil sinkronisasi tadi sore dari
 * harga Jumat pekan lalu ketika cron gagal tiga hari berturut-turut — layarnya sama
 * persis, sama-sama penuh percaya diri. Ini jawabannya.
 *
 * Tanggalnya diambil dari data yang SUDAH ada di halaman (baris terakhir deret
 * harga), bukan dari permintaan baru, jadi label ini tak menambah satu byte pun ke
 * jaringan. Payload ringkas yang dipakai dashboard sengaja tak membawa `last_date`
 * sejak Tahap 2 optimalisasi, dan itu tak perlu diubah.
 *
 * Jam sengaja tidak ditampilkan: data harian hanya membawa TANGGAL, jadi menuliskan
 * "17:37" berarti mengarang ketelitian yang tak dimiliki datanya.
 */
export default function TanggalData({
  tanggal,
  awalan = 'Data',
}: {
  /** Format `YYYY-MM-DD` dari deret OHLCV. */
  tanggal?: string | null;
  awalan?: string;
}) {
  const sekarang = useSekarang();

  if (!tanggal) return null;
  const d = new Date(`${tanggal}T00:00:00`);
  if (Number.isNaN(d.getTime())) return null;

  // Teks tanggalnya murni dari props — sama di server dan klien. Hanya umurnya yang
  // menunggu hidrasi.
  const umur = sekarang === null ? null : Math.floor((sekarang - d.getTime()) / 86_400_000);
  const lama = umur !== null && umur > AMBANG_HARI;
  const teks = d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' });

  return (
    <span
      title={
        lama
          ? `Harga terakhir yang tersimpan berumur ${umur} hari. Sinkronisasi harian mungkin gagal, atau saham ini sedang disuspensi.`
          : 'Tanggal perdagangan terakhir yang datanya tersimpan'
      }
      style={{
        fontFamily: 'var(--font-plex-mono), monospace',
        fontSize: 11,
        color: lama ? PERINGATAN : REDUP,
        fontWeight: lama ? 700 : 400,
        whiteSpace: 'nowrap',
      }}
    >
      {awalan} {teks}
      {lama && ` · ${umur} hari lalu`}
    </span>
  );
}
