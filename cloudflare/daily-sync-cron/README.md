# Pemicu Daily Sync lewat Cloudflare Worker

Cron GitHub Actions tertunda berjam-jam di antrean penjadwal (run #52: dijadwalkan
17:00 WIB, mulai 20:56). `workflow_dispatch` **tidak** ikut antre. Worker ini
menekan tombol itu tiap hari kerja pukul 17:30 WIB.

Alur: cron Cloudflare → `POST /repos/McYeremia/Emetiq/actions/workflows/daily-sync.yml/dispatches`
→ job jalan di runner GitHub seperti biasa.

## Biaya

Gratis, dan tidak mepet. Kuota Workers free plan:

| Batas (free) | Angka | Pemakaian kita |
|---|---|---|
| Permintaan / hari | 100.000 | ~1 (≈22/bulan) |
| Waktu CPU / pemanggilan cron | 10 ms | ~1 ms (nunggu `fetch` itu I/O, bukan CPU) |
| Cron trigger / akun | 5 | 1 |
| Durasi wall-clock / pemanggilan | 15 menit | < 1 detik |

Tak perlu kartu kredit. Repo `McYeremia/Emetiq` publik, jadi menit GitHub Actions
juga tak terbatas.

## Langkah

### 1. Buat GitHub token

GitHub → Settings → Developer settings → **Personal access tokens → Fine-grained tokens**
→ *Generate new token*:

- Repository access: **Only select repositories** → `McYeremia/Emetiq`
- Permissions → Repository permissions → **Actions: Read and write**
  (`Metadata: Read-only` ikut otomatis; jangan tambah yang lain)
- Expiration: catat tanggalnya — token kedaluwarsa = sinkron diam-diam berhenti

Salin tokennya sekarang; GitHub tak menampilkannya lagi.

### 2. Login wrangler

```bash
cd cloudflare/daily-sync-cron
npx wrangler login          # buka browser, izinkan
```

### 3. Deploy

```bash
npx wrangler deploy
```

Deploy dulu, baru rahasia — `wrangler secret put` butuh Worker-nya sudah ada.
Catat URL `https://emetiq-daily-sync-cron.<subdomain>.workers.dev` dari keluarannya.

### 4. Isi rahasia

```bash
npx wrangler secret put GITHUB_TOKEN        # tempel PAT dari langkah 1
npx wrangler secret put CRON_SECRET         # karang sendiri, mis. `openssl rand -hex 24`
npx wrangler secret put TELEGRAM_BOT_TOKEN  # opsional — kabar kalau pemicu gagal
npx wrangler secret put TELEGRAM_CHAT_ID    # opsional
```

Rahasia berlaku langsung, tak perlu deploy ulang.

### 5. Uji manual

```bash
curl -i -X POST "https://emetiq-daily-sync-cron.<subdomain>.workers.dev" \
  -H "X-Cron-Secret: <CRON_SECRET>"
```

`{"ok": true, "status": 204}` berarti berhasil. Cek **Actions → Daily Sync** di
GitHub: run baru harus muncul dalam hitungan detik, berlabel `workflow_dispatch`.

Kalau `403`: cek header `X-Cron-Secret`. Kalau `status: 404` dari GitHub: PAT tak
punya akses repo, atau nama workflow salah. Kalau `401`: PAT salah/kedaluwarsa.

### 6. Pastikan cron terpasang

Cloudflare dashboard → Workers & Pages → `emetiq-daily-sync-cron` → Settings →
**Triggers → Cron Triggers**: harus ada `30 10 * * MON-FRI`. Perubahan cron butuh
**sampai 15 menit** untuk menyebar. Log tiap pemanggilan ada di tab *Logs* (Workers Logs
menyimpan riwayat; `wrangler tail` cuma live).

### 7. Setelah terbukti 2–3 hari: matikan cron GitHub

Kalau tidak, job jalan DUA KALI sehari — sekali dari Worker (tepat waktu), sekali
lagi dari antrean GitHub berjam-jam kemudian. Menit Actions memang gratis, tapi
egress Supabase tidak. Di `.github/workflows/daily-sync.yml`, komentari `schedule:`
(jangan hapus — pola yang sama dipakai `bigmoney-daily.yml`) dan biarkan
`workflow_dispatch` apa adanya.

## Yang perlu diingat

- **Hari di cron Cloudflare BUKAN konvensi POSIX.** Cloudflare memakai
  `1 = Minggu … 7 = Sabtu`; GitHub Actions memakai `0 = Minggu, 1 = Senin`.
  Artinya `* * * * 1-5` berarti **Senin–Jumat di `daily-sync.yml`** tapi
  **Minggu–Kamis di sini**. Tulis `MON-FRI`, jangan angka — dokumentasi
  Cloudflare sendiri menganjurkan singkatan justru karena jebakan ini.

- **PAT kedaluwarsa itu kegagalan senyap.** Karena itu `kabari()` mengirim Telegram
  saat GitHub menolak. Kalau Telegram tak diisi, andalkan penanda kesegaran data
  di dashboard.
- **Worker ini memperbaiki penjadwal, bukan ketersediaan runner.** Kalau kolam
  runner GitHub sendiri penuh, run hasil dispatch tetap bisa menunggu — hanya saja
  itu belum pernah terjadi ~4 jam seperti antrean cron.
- **Cron Cloudflare pun tidak presisi detik** (jitter beberapa detik) dan minimum
  granularitasnya 1 menit. Untuk sinkron harian ini lebih dari cukup.
- **Worker tak menyentuh basis data.** Ia menekan tombol; seluruh logika tetap di
  `backend/scripts/daily_sync.py`.
