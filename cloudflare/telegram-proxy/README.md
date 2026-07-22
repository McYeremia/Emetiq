# Proxy egress Telegram (Cloudflare Worker)

HF Spaces memblokir egress ke `api.telegram.org`, jadi balasan bot interaktif
(`/start`, `/report`, `/top`) yang jalan di backend HF macet dengan SSL timeout.
Worker ini jadi jembatan: HF → Cloudflare → Telegram.

`broadcast_report` (laporan harian) tak butuh ini — ia jalan dari laptop lewat
Task Scheduler dan menembak Telegram langsung.

## Deploy

```bash
cd cloudflare/telegram-proxy
npm install -g wrangler        # sekali saja
wrangler login
wrangler secret put PROXY_SECRET   # tempel string acak panjang; simpan
wrangler deploy
```

Catat URL hasilnya, mis. `https://emetiq-telegram-proxy.<akun>.workers.dev`.

## Sambungkan backend HF

Di Settings → Variables and secrets pada HF Space, tambah:

| Nama | Nilai |
|------|-------|
| `TELEGRAM_API_BASE` | URL Worker (tanpa `/` di akhir) |
| `TELEGRAM_PROXY_SECRET` | `PROXY_SECRET` yang sama |

`TELEGRAM_BOT_TOKEN` sudah ada dari sebelumnya. Lalu **Factory rebuild**.

**JANGAN** set `TELEGRAM_API_BASE` di laptop — pipeline harian harus tetap
menembak Telegram langsung.

## Uji

Kirim `/report` ke bot dari Telegram. Balasan yang muncul = jalur egress tembus.
Kalau perlu cek dari sisi HF:

```bash
curl -X POST "$TELEGRAM_API_BASE/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
  -H "X-Proxy-Secret: $TELEGRAM_PROXY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":"<chat_id_kamu>","text":"tes proxy"}'
```
