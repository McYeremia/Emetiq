# Proxy egress Telegram (Cloudflare Worker) — TIDAK DIPAKAI

**Diganti oleh `frontend/app/api/tg/[...path]/route.ts` sejak 2026-07-23.**
Berkas di folder ini disimpan sebagai catatan, bukan bagian dari jalur produksi.

## Kenapa gagal

Egress HF Spaces memblokir tujuan berdasarkan **domain**, bukan berdasarkan
sidik jari TLS. `*.workers.dev` ikut terblokir bersama `api.telegram.org`, jadi
Worker ini tak pernah bisa dihubungi dari HF. Buktinya di log HF:

- `httpx` → `[SSL: UNEXPECTED_EOF_WHILE_READING]`, koneksi diputus saat
  handshake TLS, sebelum ada satu byte HTTP pun.
- `curl_cffi` impersonate Chrome → `curl: (28) Connection timed out`. Sidik jari
  Chrome tak menolong; kalau penyaringnya menilai TLS, jalur ini akan tembus.
- Domain lain dari HF (`emetiq.vercel.app`) dijawab normal — HTTP 404 dari
  Vercel. Jadi egress HF sendiri sehat; yang ditolak adalah tujuannya.

Worker-nya sendiri benar dan pernah terbukti bekerja saat dipanggil dari laptop
(menembus sampai Telegram dan membawa pulang balasan JSON asli). Yang salah
bukan kodenya, melainkan pilihan domainnya.

## Kalau suatu saat mau dipakai lagi

Perlu **custom domain** di Cloudflare (Worker → Settings → Domains & Routes).
Selama alamatnya masih `*.workers.dev`, HF akan terus memutusnya.
