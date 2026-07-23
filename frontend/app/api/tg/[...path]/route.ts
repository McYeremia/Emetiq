// Proxy egress Telegram untuk backend EMETIQ di Hugging Face Spaces.
//
// Kenapa di sini, bukan di Cloudflare Worker: egress HF memblokir tujuan
// berdasarkan domain. `api.telegram.org` ditolak, dan `*.workers.dev` ikut
// ditolak — terbukti 2026-07-23 dari log HF: httpx putus saat handshake TLS
// (SSL EOF) dan curl_cffi menggantung sampai timeout, dua gejala berbeda untuk
// satu sebab yang sama. Domain Vercel ini dijawab normal dari HF, jadi frontend
// yang sudah jalan sekaligus jadi jembatan: HF -> Vercel -> Telegram.
//
// Ia hanya meneruskan; tak menyentuh isi pesan. Bukan open relay: tanpa
// X-Proxy-Secret yang cocok ia menolak, dan hanya jalur Bot API bertoken
// (/bot<token>/<method>) yang diloloskan, bukan URL sembarang.

const TELEGRAM = "https://api.telegram.org";
const TOKEN_SEGMENT = /^bot[^/]+$/;
const METHOD_SEGMENT = /^[A-Za-z]+$/;

export async function POST(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const secret = process.env.TELEGRAM_PROXY_SECRET;
  if (!secret || request.headers.get("X-Proxy-Secret") !== secret) {
    return new Response("Forbidden", { status: 403 });
  }

  const { path } = await params;
  if (
    path.length !== 2 ||
    !TOKEN_SEGMENT.test(path[0]) ||
    !METHOD_SEGMENT.test(path[1])
  ) {
    return new Response("Forbidden", { status: 403 });
  }

  const upstream = await fetch(`${TELEGRAM}/${path[0]}/${path[1]}`, {
    method: "POST",
    headers: {
      "Content-Type": request.headers.get("Content-Type") || "application/json",
    },
    body: await request.arrayBuffer(),
  });

  // Teruskan status & body apa adanya supaya send_message di sisi Python bisa
  // membedakan sukses dari penolakan Telegram (HTTP 4xx).
  return new Response(upstream.body, {
    status: upstream.status,
    headers: { "Content-Type": "application/json" },
  });
}
