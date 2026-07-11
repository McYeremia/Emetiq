/** Feature flag Big Money.
 *
 * Fitur ini belum siap rilis: sinyalnya masih dikalibrasi dan laporannya ditulis
 * LLM. Halaman disembunyikan di produksi (route 404, link nav tak dirender) dan
 * backend menolak siapa pun selain tier `dev` dengan 403. Dua lapis, sengaja —
 * flag frontend saja bukan pengamanan.
 *
 * Dev: `NEXT_PUBLIC_ENABLE_BIGMONEY=true` di .env.local, atau otomatis aktif
 * saat `next dev`. Produksi (Vercel): jangan set variabelnya sama sekali.
 */
export const isBigMoneyEnabled =
  process.env.NEXT_PUBLIC_ENABLE_BIGMONEY === 'true' ||
  process.env.NODE_ENV === 'development';
