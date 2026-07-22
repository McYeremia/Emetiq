// Proxy egress Telegram untuk backend EMETIQ di Hugging Face Spaces.
//
// Kenapa ini ada: HF Spaces MEMBLOKIR egress ke api.telegram.org, jadi balasan
// bot interaktif (/start, /report, /top) yang jalan di HF macet dengan SSL
// timeout. Cloudflare boleh menembak Telegram, HF boleh menembak Cloudflare —
// Worker ini jembatannya. Ia hanya meneruskan; tak menyentuh isi pesan.
//
// Bukan open relay: tanpa X-Proxy-Secret yang cocok ia menolak. Dan hanya jalur
// Bot API bertoken (/bot<token>/<method>) yang diloloskan, bukan URL sembarang.

const TELEGRAM = "https://api.telegram.org";
const BOT_PATH = /^\/bot[^/]+\/[A-Za-z]+$/;

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Not found", { status: 404 });
    }
    if (!env.PROXY_SECRET || request.headers.get("X-Proxy-Secret") !== env.PROXY_SECRET) {
      return new Response("Forbidden", { status: 403 });
    }

    const url = new URL(request.url);
    if (!BOT_PATH.test(url.pathname)) {
      return new Response("Forbidden", { status: 403 });
    }

    const upstream = await fetch(TELEGRAM + url.pathname + url.search, {
      method: "POST",
      headers: { "Content-Type": request.headers.get("Content-Type") || "application/json" },
      body: await request.arrayBuffer(),
    });

    // Teruskan status & body apa adanya supaya send_message di sisi Python bisa
    // membedakan sukses dari penolakan Telegram (HTTP 4xx).
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  },
};
