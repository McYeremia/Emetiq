// Pemicu "Daily Sync" dari luar GitHub.
//
// Kenapa ini ada: cron GitHub Actions tidak tepat waktu. Run #52 dijadwalkan
// 17:00 WIB tapi baru mulai 20:56 — tertunda ~4 jam di ANTREAN PENJADWAL,
// padahal jobnya sendiri cuma 44 menit. Pindah ke menit 37 hanya mengurangi,
// tidak menghilangkan. Yang TIDAK ikut antre itu `workflow_dispatch`.
//
// Jadi: cron Cloudflare (jitter hitungan detik) -> GitHub API -> workflow_dispatch.
// Worker ini tidak menyentuh data sama sekali; ia cuma menekan tombol.

const REPO = "McYeremia/Emetiq";
const WORKFLOW = "daily-sync.yml";
const REF = "main";
const MODE_SAH = ["harian", "penuh"];

export default {
  // Dipanggil penjadwal Cloudflare sesuai [triggers].crons di wrangler.toml.
  async scheduled(controller, env, ctx) {
    const hasil = await picuWorkflow(env, "harian");
    console.log(JSON.stringify({ sumber: "cron", ...hasil }));
  },

  // Jalur uji manual. Dipagari CRON_SECRET supaya tak jadi tombol umum:
  // siapa pun yang tahu URL-nya bisa menyalakan job 44 menit berulang kali.
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("Not found", { status: 404 });
    }
    if (!env.CRON_SECRET || request.headers.get("X-Cron-Secret") !== env.CRON_SECRET) {
      return new Response("Forbidden", { status: 403 });
    }

    const mode = new URL(request.url).searchParams.get("mode") || "harian";
    if (!MODE_SAH.includes(mode)) {
      return new Response(`mode harus salah satu dari: ${MODE_SAH.join(", ")}`, { status: 400 });
    }

    const hasil = await picuWorkflow(env, mode);
    return new Response(JSON.stringify(hasil, null, 2), {
      status: hasil.ok ? 200 : 502,
      headers: { "Content-Type": "application/json" },
    });
  },
};

async function picuWorkflow(env, mode) {
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;

  let balasan;
  try {
    balasan = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        // GitHub menolak permintaan tanpa User-Agent dengan HTTP 403.
        "User-Agent": "emetiq-daily-sync-cron",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: REF, inputs: { mode } }),
    });
  } catch (e) {
    const hasil = { ok: false, mode, galat: String(e) };
    await kabari(env, `⚠️ EMETIQ: pemicu daily-sync gagal menghubungi GitHub — ${e}`);
    return hasil;
  }

  // Sukses = 204 No Content. GitHub tidak memulangkan id run-nya di sini.
  if (balasan.status === 204) {
    return { ok: true, mode, status: 204 };
  }

  const teks = (await balasan.text()).slice(0, 300);
  await kabari(
    env,
    `⚠️ EMETIQ: pemicu daily-sync DITOLAK GitHub — HTTP ${balasan.status}\n${teks}\n\n` +
      `Paling sering: PAT kedaluwarsa. Perbarui token lalu 'wrangler secret put GITHUB_TOKEN'.`,
  );
  return { ok: false, mode, status: balasan.status, body: teks };
}

// Lapisan kabar, bukan data: kegagalannya tidak boleh menjatuhkan pemicu.
async function kabari(env, teks) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_CHAT_ID) return;
  try {
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: teks }),
    });
  } catch (e) {
    console.log("gagal kirim kabar Telegram:", String(e));
  }
}
