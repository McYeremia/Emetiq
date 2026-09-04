'use client';

import { useEffect, useState, useSyncExternalStore } from 'react';

const PERINGATAN = '#B7791F';
const PULIH = '#138A50';

/** Berapa lama pesan "koneksi kembali" bertahan sebelum menghilang sendiri. */
const JEDA_PESAN_PULIH = 12_000;

function berlangganan(ubah: () => void) {
  window.addEventListener('online', ubah);
  window.addEventListener('offline', ubah);
  return () => {
    window.removeEventListener('online', ubah);
    window.removeEventListener('offline', ubah);
  };
}

/**
 * Bilah tipis di puncak halaman saat koneksi putus.
 *
 * Kenapa perlu: seluruh angka di aplikasi ini datang dari jaringan, dan
 * `usePollingSaatTerlihat` menyegarkannya tiap lima menit. Ketika koneksi hilang,
 * permintaan itu gagal **diam-diam** — layar tetap menampilkan angka terakhir tanpa
 * satu pun tanda bahwa ia sudah berhenti diperbarui. Bilah ini yang mengatakannya.
 *
 * `navigator.onLine` cuma melaporkan koneksi di tingkat sistem operasi, bukan apakah
 * server kita benar-benar terjangkau. Jadi `true` berarti "mungkin online" — tak bisa
 * dipercaya — sementara `false` berarti "pasti offline". Komponen ini hanya memakai
 * arah yang bisa dipercaya itu: ia tampil saat `false`, dan tak pernah mengklaim
 * apa pun saat `true`.
 *
 * Statusnya dibaca lewat `useSyncExternalStore`, bukan `useState` + efek. Itu memang
 * bentuk yang disediakan React untuk nilai yang hidup di luar React seperti ini, dan
 * ia menyelesaikan soal server sekaligus: snapshot server-nya `true` (online), jadi
 * HTML yang dikirim tak pernah memuat bilah yang kemudian hilang saat hidrasi.
 *
 * Sengaja TIDAK sticky. Menu atas tiap halaman sudah `position: sticky; top: 0`, dan
 * dua elemen lengket di posisi sama akan saling menimpa saat digulir. Bilah ini
 * mengalir normal di puncak halaman; yang menjaga informasinya tetap terlihat setelah
 * digulir adalah label `TanggalData` yang menempel persis di sebelah angkanya.
 */
export default function BilahKoneksi() {
  const online = useSyncExternalStore(
    berlangganan,
    () => navigator.onLine,
    () => true,
  );
  const [barusanPulih, setBarusanPulih] = useState(false);

  useEffect(() => {
    // setState hanya dari dalam callback event, bukan dari badan efek — badan efek
    // yang menyetel state memicu render berantai (dan aturan lint react-hooks).
    const keOnline = () => setBarusanPulih(true);
    const keOffline = () => setBarusanPulih(false);
    window.addEventListener('online', keOnline);
    window.addEventListener('offline', keOffline);
    return () => {
      window.removeEventListener('online', keOnline);
      window.removeEventListener('offline', keOffline);
    };
  }, []);

  // Pesan "koneksi kembali" menghilang sendiri. Ia cuma perlu ada cukup lama untuk
  // dibaca dan ditindaklanjuti.
  useEffect(() => {
    if (!barusanPulih) return;
    const t = setTimeout(() => setBarusanPulih(false), JEDA_PESAN_PULIH);
    return () => clearTimeout(t);
  }, [barusanPulih]);

  const offline = !online;
  if (!offline && !barusanPulih) return null;

  const warna = offline ? PERINGATAN : PULIH;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        gap: 10, flexWrap: 'wrap',
        padding: '9px 16px',
        background: `color-mix(in oklab, ${warna}, white 88%)`,
        borderBottom: `1px solid color-mix(in oklab, ${warna}, white 70%)`,
        color: `color-mix(in oklab, ${warna}, black 12%)`,
        fontSize: 13, fontWeight: 600, lineHeight: 1.4, textAlign: 'center',
      }}
    >
      {offline ? (
        <span>Sedang offline — angka di layar berhenti diperbarui.</span>
      ) : (
        <>
          <span>Koneksi kembali.</span>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              minHeight: 32, padding: '0 14px', borderRadius: 8, cursor: 'pointer',
              border: `1px solid color-mix(in oklab, ${PULIH}, white 60%)`,
              background: '#fff', color: `color-mix(in oklab, ${PULIH}, black 12%)`,
              fontSize: 13, fontWeight: 700,
            }}
          >
            Muat ulang data
          </button>
        </>
      )}
    </div>
  );
}
