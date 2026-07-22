// Hanya dipanggil dari Server Component. Paket `server-only` belum terpasang di
// proyek ini, jadi tak ada pagar impor — jangan panggil dari komponen klien.
import type { OHLCV, StockRingkas } from './api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

/** Data pasar hanya berganti sekali sehari, setelah `daily_sync` jalan. Lima
 *  menit sudah jauh lebih sering daripada perlu, dan cache ini dipakai BERSAMA
 *  oleh semua pengunjung: berapa pun yang membuka dashboard, backend paling
 *  banyak ditanya sekali per lima menit. */
const REVALIDASI_DETIK = 300;

export interface Sinyal {
  ticker: string;
  name: string;
  type: string;
  strategies: string[];
  max_strength: number;
  date: string;
  market_cap: number | null;
}

/** Kegagalan backend tak boleh menjatuhkan halaman — kembalikan `null` dan
 *  biarkan komponen klien mencoba lagi lewat polling. Halaman kosong yang
 *  memuat ulang sendiri jauh lebih baik daripada layar galat. */
async function ambil<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`, {
      next: { revalidate: REVALIDASI_DETIK },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export function ambilSaham() {
  return ambil<StockRingkas[]>('/stocks?ringkas=true');
}

export function ambilSinyal() {
  return ambil<Sinyal[]>('/stocks/signals');
}

export function ambilIhsg(dariTanggal: string) {
  return ambil<{ data: OHLCV[] }>(
    `/stocks/${encodeURIComponent('^JKSE')}/ohlcv?from=${dariTanggal}`,
  );
}

/** Tanggal awal grafik IHSG: dua bulan ke belakang, sama seperti sebelumnya. */
export function tanggalAwalIhsg(): string {
  const d = new Date();
  d.setMonth(d.getMonth() - 2);
  return d.toISOString().slice(0, 10);
}
