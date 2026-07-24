"""Pengiriman laporan Big Money ke Telegram.

Bot ini mendorong laporan keluar; ia bukan lawan bicara. Karena itu tak ada
proses bot yang berjalan terus-menerus dan tak ada dependensi baru — cukup Bot
API lewat httpx yang sudah terpasang, dipanggil dari pipeline harian.

Penautan akun memakai KODE SEKALI PAKAI yang dibuat saat user sudah login, bukan
dengan mengetik email di bot seperti spec lama. Email adalah identitas, bukan
bukti kepemilikan: kalau email jadi kuncinya, siapa pun yang tahu email orang
lain bisa membajak notifikasinya.
"""
import html
import logging
import os
import secrets
import time
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

import models
from services.bigmoney import istilah

logger = logging.getLogger("bigmoney.telegram")

_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

_DEFAULT_API_BASE = "https://api.telegram.org"
_TIMEOUT = 15
_MAX_PERCOBAAN = 3       # webhook Telegram menunggu balasan; jangan menggantung lama
_JEDA_ULANG = 0.5        # detik, dikali nomor percobaan
_CODE_TTL_MINUTES = 15
_CODE_BYTES = 6          # ~10 karakter base32 — cukup panjang untuk tak bisa ditebak
_TOP_IN_MESSAGE = 5
_BATAS_PESAN = 4096      # batas keras Bot API, dihitung dalam satuan UTF-16
_TANDA_POTONG = "\n\n(narasi dipotong agar muat dalam satu pesan)"

DISCLAIMER = "⚠️ Estimasi, bukan nasihat investasi."

# Tiga baris, sengaja pendek: legenda yang panjang akan dilewati mata setiap hari.
LEGENDA_SKOR = (
    "ℹ️ <b>Arti nilai 0–100</b>\n"
    "Membandingkan saham ini dengan saham lain <b>pada hari yang sama</b>, "
    "bukan nilai mutlak. Dihitung dari besarnya pembelian asing dibanding ramainya "
    "transaksi, konsistensi asing membeli, ukuran order rata-rata, posisi harga "
    "terhadap perkiraan harga masuk asing, dan volume yang naik saat harga masih adem.\n"
    "Ketik /skor untuk penjelasan lengkapnya."
)

PENJELASAN_SKOR = (
    "📐 <b>Dari mana nilai 0–100 itu?</b>\n\n"
    "Nilai ini <b>peringkat</b>, bukan nilai mutlak. Nilai 82 berarti saham itu "
    "mengungguli 82% saham lain <b>pada hari yang sama</b>. Di hari ketika asing "
    "menjual besar-besaran, nilai tinggi berarti 'paling sedikit dijual' — bukan "
    "'paling banyak dibeli'. Karena itu angkanya tak bisa dibandingkan antar hari.\n\n"
    "Lima hal yang diukur:\n\n"
    "1. <b>Besarnya uang asing dibanding ramainya transaksi.</b> Rp 10 miliar di saham "
    "sepi lebih berarti daripada Rp 10 miliar di saham yang sehari berputar triliunan.\n"
    "2. <b>Konsistensi.</b> Beli lima hari berturut-turut beda maknanya dengan beli "
    "sekali lalu diam.\n"
    "3. <b>Ukuran order rata-rata.</b> Nilai transaksi dibagi jumlah transaksi. Order "
    "besar meninggalkan jejak pemain besar — institusi, tak peduli asing atau lokal.\n"
    "4. <b>Posisi harga sekarang terhadap perkiraan harga masuk asing.</b> Masih dekat "
    "harga masuk berarti belum banyak yang tertinggal.\n"
    "5. <b>Volume naik saat harga masih adem.</b> Ciri pengumpulan diam-diam: barang "
    "berpindah banyak tanpa harga terlanjur lari.\n\n"
    "Bobot kelimanya <b>berubah mengikuti keadaan pasar</b>. Saat pasar bergejolak, "
    "konsistensi lebih dipercaya daripada lonjakan sesaat.\n\n"
    "Nilai tinggi saja tak cukup untuk disebut kuat: label 'kuat' menuntut minimal "
    "<b>tiga hari asing membeli berturut-turut</b>. Tanpa syarat itu, sesuatu akan "
    "selalu menempati peringkat teratas bahkan di hari terburuk sekalipun.\n\n"
    "Nilai uang asing adalah <b>estimasi</b> — IDX melaporkan jumlah lembar, bukan "
    "harga per sisi asing, jadi rupiahnya dihitung dari harga rata-rata pasar.\n\n"
    + DISCLAIMER
)


class TelegramError(RuntimeError):
    """Bot API menolak atau tak bisa dihubungi."""


def is_configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN"))


def _send_url(token: str) -> str:
    """URL sendMessage. Default langsung ke Bot API; TELEGRAM_API_BASE mengalihkannya.

    HF Spaces memblokir egress ke api.telegram.org, jadi backend di HF menyetel
    TELEGRAM_API_BASE ke Cloudflare Worker yang meneruskan permintaan. Laptop
    (pipeline harian) membiarkannya kosong dan menembak Telegram langsung.
    """
    base = os.getenv("TELEGRAM_API_BASE", _DEFAULT_API_BASE).rstrip("/")
    return f"{base}/bot{token}/sendMessage"


def _target(url: str) -> str:
    """Host tujuan saja, untuk pesan galat.

    Token ada di path, jadi jangan pernah menaruh URL utuh ke log — host cukup
    untuk membedakan 'menembak Telegram langsung' dari 'lewat Worker'.
    """
    return urlsplit(url).netloc or "(URL tanpa host)"


def send_message(chat_id: str, text: str) -> None:
    """Kirim satu pesan HTML. Melempar TelegramError bila gagal."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise TelegramError("TELEGRAM_BOT_TOKEN belum diset")

    # Proxy Worker menolak relay anonim: tanpa secret ini ia bukan open proxy.
    # Kosong saat menembak Telegram langsung — Bot API mengabaikan header asing.
    headers = {}
    proxy_secret = os.getenv("TELEGRAM_PROXY_SECRET")
    if proxy_secret:
        headers["X-Proxy-Secret"] = proxy_secret

    url = _send_url(token)
    # Host & status secret ikut ke pesan galat: tanpa itu, 'SSL EOF' dan '403'
    # tak bisa dibedakan antara Telegram langsung dan proxy Worker, dan diagnosis
    # di HF berubah jadi tebak-tebakan.
    jalur = f"{_target(url)}, secret={'ada' if proxy_secret else 'tidak ada'}"

    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}

    # Hanya galat transport yang diulang. Penolakan HTTP (403 secret salah, 400
    # chat_id salah) deterministik — mengulanginya cuma menunda kabar buruk.
    galat_terakhir = None
    for percobaan in range(1, _MAX_PERCOBAAN + 1):
        try:
            response = httpx.post(url, json=payload, headers=headers, timeout=_TIMEOUT)
        except Exception as exc:   # noqa: BLE001 — httpx melempar aneka galat jaringan
            galat_terakhir = exc
            logger.warning("Percobaan %s/%s ke %s gagal: %s",
                           percobaan, _MAX_PERCOBAAN, _target(url), exc)
            if percobaan < _MAX_PERCOBAAN:
                time.sleep(_JEDA_ULANG * percobaan)
            continue

        if response.status_code >= 400:
            raise TelegramError(
                f"Ditolak {jalur}: HTTP {response.status_code} {response.text[:200]}"
            )
        return

    raise TelegramError(
        f"Gagal menghubungi {jalur} setelah {_MAX_PERCOBAAN} percobaan: {galat_terakhir}"
    )


def _angka_id(value: float) -> str:
    """Format Indonesia: titik ribuan, koma desimal. Python memberi kebalikannya."""
    return f"{value:,.1f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _rupiah(value) -> str:
    """Rupiah dalam satuan yang terbaca. 'M' terlalu ambigu untuk pembaca awam —
    sebagian membacanya juta, sebagian miliar."""
    if value is None:
        return "tidak tersedia"

    miliar = value / 1_000_000_000
    if abs(miliar) >= 1_000:
        return f"Rp {_angka_id(miliar / 1_000)} triliun"
    return f"Rp {_angka_id(miliar)} miliar"


def _arah_dana(total) -> str:
    """Arah dana dinyatakan dengan kata, bukan tanda minus.

    'Uang asing masuk: Rp -285 miliar' menuntut pembaca menerjemahkan tanda minus
    sendiri. Hari outflow justru yang paling sering terjadi, jadi kalimatnya
    harus benar di kedua arah.
    """
    if total is None:
        return "Aliran dana asing hari ini: tidak tersedia"
    if total < 0:
        return f"Uang asing <b>keluar</b> dari pasar hari ini: {_rupiah(abs(total))}"
    return f"Uang asing <b>masuk</b> ke pasar hari ini: {_rupiah(total)}"


def _tanggal_pendek(iso: str | None) -> str | None:
    """'2026-07-14' → '14 Jul'. None bila tak bisa dibaca — tanggal cacat tak boleh menjatuhkan laporan."""
    if not iso:
        return None
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    return f"{d.day} {_BULAN[d.month - 1]}"


def _baris_akumulasi(pick: dict) -> str:
    """Baris kedua: angka hari ini dipisahkan tegas dari akumulasi berjalan.

    Tanpa pemisahan ini pembaca mengira angka harian adalah totalnya. Saham yang
    belum punya posisi aktif jatuh ke bentuk pendek — menampilkan 'total 0' akan
    berbohong tentang apa yang sudah masuk.
    """
    harian = pick.get("foreign_net_value")
    if harian is not None and harian < 0:
        # Di hari outflow, "top akumulasi" berarti paling sedikit dijual. Menutupi
        # itu dengan angka positif akan menyesatkan.
        bagian = [f"Hari ini asing justru keluar {_rupiah(abs(harian))}"]
    else:
        bagian = [f"Hari ini {_rupiah(harian)}"]

    total = pick.get("accumulated_value")
    if total:
        sejak = _tanggal_pendek(pick.get("opened_on"))
        hari = pick.get("inflow_days")
        potongan = f"total {_rupiah(total)}"
        if hari:
            potongan += f" dari {hari} hari beli"
        if sejak:
            potongan += f" sejak {sejak}"
        bagian.append(potongan)

        gain = pick.get("gain_since_entry_pct")
        if gain is not None:
            tanda = "+" if gain >= 0 else "−"
            bagian.append(f"harga {tanda}{_angka_id(abs(gain))}% sejak asing masuk")
    else:
        beruntun = pick.get("days_confirmed")
        if beruntun:
            bagian.append(f"{beruntun} hari beli beruntun")

    return " · ".join(bagian)


def _pick_line(pick: dict) -> str:
    ticker = html.escape(str(pick["ticker"]))
    fase = istilah.fase(pick.get("phase"))
    baris = [
        f"{pick['rank']}. <b>{ticker}</b> — nilai {pick['composite']:.0f} dari 100",
        f"   {html.escape(fase[:1].upper() + fase[1:])}",
        f"   {html.escape(_baris_akumulasi(pick))}",
    ]

    catatan = istilah.peringatan(pick.get("flags"))
    if catatan:
        baris.append(f"   {html.escape(catatan)}")

    return "\n".join(baris)


def _panjang(teks: str) -> int:
    """Panjang menurut hitungan Telegram: UTF-16, jadi tiap emoji dihitung dua.

    `len()` Python menghitung titik kode. Memakainya membuat pesan berisi emoji —
    dan laporan ini penuh emoji — lolos pemeriksaan di sini lalu ditolak Bot API.
    """
    return len(teks.encode("utf-16-le")) // 2


def _tanpa_entitas_terpenggal(teks: str) -> str:
    """Buang entitas HTML yang terpotong di ujung.

    '&amp;' yang terpangkas jadi '&am' membuat Telegram menolak seluruh pesan:
    satu karakter salah menghapus laporan sehari penuh.
    """
    amp = teks.rfind("&")
    return teks[:amp] if amp != -1 and ";" not in teks[amp:] else teks


def _potong_narasi(narasi: str, sisa: int) -> str:
    """Pangkas narasi (sudah ter-escape) ke `sisa` satuan, berhenti di akhir kalimat.

    Berhenti di tengah kalimat membuat laporan terbaca cacat, bukan terpotong —
    karena itu potongannya ditandai, bukan disamarkan.
    """
    batas = sisa - _panjang(_TANDA_POTONG)
    if batas <= 0:
        return ""

    potong = narasi
    while _panjang(potong) > batas:
        # Selisihnya dalam satuan UTF-16; sebagai jumlah karakter ia selalu >= 1,
        # jadi perulangan ini pasti mengecil dan berhenti.
        potong = potong[:len(potong) - (_panjang(potong) - batas)]

    titik = potong.rfind(". ")
    if titik > len(potong) // 2:   # jangan buang separuh narasi demi kerapian kalimat
        potong = potong[:titik + 1]

    return _tanpa_entitas_terpenggal(potong).rstrip() + _TANDA_POTONG


def _rakit_laporan(report: models.BigMoneyDailyReport, narasi: str) -> str:
    """Susun pesan dari laporan + narasi yang sudah ter-escape.

    Dipisah dari `format_report` supaya panjangnya bisa diukur lebih dulu, lalu
    narasinya dipangkas dan pesannya dirakit ulang.
    """
    context = report.context or {}
    regime = context.get("regime") or {}
    top = context.get("top_accumulation") or []

    lines = [
        f"📊 <b>Big Money — {report.date}</b>",
        "",
        f"<b>{html.escape(report.headline or '')}</b>",
    ]

    if narasi:
        lines += ["", narasi]

    kondisi = istilah.kondisi_pasar(regime.get("volatility_regime"),
                                    regime.get("trend_regime"))
    lines += [
        "",
        f"🔎 <b>Kondisi pasar:</b> {html.escape(kondisi)}",
        _arah_dana(regime.get("total_foreign_net_value")),
    ]

    if top:
        lines += ["", "🏆 <b>Paling banyak dibeli asing hari ini</b>", ""]
        # Baris kosong antar saham: tiga baris yang menempel jadi satu blok abu-abu.
        lines += ["\n".join([_pick_line(p), ""]) for p in top[:_TOP_IN_MESSAGE]]
        # Legenda menjelaskan nilai 0–100; tanpa satu pun saham, tak ada nilai yang dijelaskan.
        lines.append(LEGENDA_SKOR)

    lines += ["", DISCLAIMER]
    return "\n".join(lines)


def format_report(report: models.BigMoneyDailyReport) -> str:
    """Laporan harian → pesan HTML Telegram, dijamin muat dalam satu pesan.

    Teks dari LLM di-escape: judul yang kebetulan memuat `<` atau `&` akan
    membuat Telegram menolak seluruh pesan bila dikirim mentah.

    Narasi Gemini tak dibatasi panjangnya, dan pesan yang melewati 4096 satuan
    ditolak HTTP 400 — sementara `broadcast_report` tetap menandai laporan
    terkirim. Kegagalannya senyap, jadi panjangnya dipastikan di sini. Yang
    dipangkas hanya narasi: angka, peringatan risiko, dan disclaimer harus utuh.
    """
    narasi = html.escape(report.narrative or "")
    teks = _rakit_laporan(report, narasi)
    if _panjang(teks) <= _BATAS_PESAN:
        return teks

    # Satu karakter umpan mengukur kerangka sekaligus baris kosong pengapitnya;
    # mengurangi panjang narasi dari total akan melupakan pemisah itu.
    kerangka = _panjang(_rakit_laporan(report, "x")) - 1
    return _rakit_laporan(report, _potong_narasi(narasi, _BATAS_PESAN - kerangka))


def render_top(target: date, picks: list[dict]) -> str:
    """Daftar top akumulasi tanpa narasi — jawaban untuk perintah /top.

    Tanpa narasi, panjangnya terikat `_TOP_IN_MESSAGE` dan tak bisa meledak
    seperti `format_report`.
    """
    if not picks:
        return f"Belum ada peringkat untuk {target}."

    lines = [f"🏆 <b>Paling banyak dibeli asing — {target}</b>", ""]
    # Baris kosong antar saham: tiga baris yang menempel jadi satu blok abu-abu.
    lines += ["\n".join([_pick_line(p), ""]) for p in picks[:_TOP_IN_MESSAGE]]
    lines += [LEGENDA_SKOR, "", DISCLAIMER]
    return "\n".join(lines)


def _linked_dev_chats(db: Session) -> list[str]:
    """Chat yang berhak menerima: tertaut DAN tier dev (fitur masih dev-mode)."""
    rows = (
        db.query(models.Profile.telegram_chat_id)
          .filter(models.Profile.telegram_chat_id.isnot(None))
          .filter(models.Profile.tier == "dev")
          .all()
    )
    return [chat_id for (chat_id,) in rows]


def broadcast_report(target: date, db: Session, force: bool = False) -> int:
    """Kirim laporan `target` ke semua chat dev yang tertaut. Mengembalikan jumlah terkirim.

    Idempoten lewat `sent_at`: workflow yang di-rerun tak mengirim ulang laporan
    yang sama. `force=True` menembusnya.

    Tanpa TELEGRAM_BOT_TOKEN, fungsi ini diam dan mengembalikan 0 — Telegram adalah
    lapisan pemberitahuan, dan ketiadaannya tak boleh menjatuhkan pipeline data.
    """
    if not is_configured():
        logger.warning("Broadcast dilewati: TELEGRAM_BOT_TOKEN belum diset")
        return 0

    report = (
        db.query(models.BigMoneyDailyReport)
          .filter(models.BigMoneyDailyReport.date == target)
          .one_or_none()
    )
    if report is None:
        logger.info("%s belum punya laporan — tak ada yang dikirim", target)
        return 0
    if report.sent_at is not None and not force:
        logger.info("%s sudah pernah dikirim", target)
        return 0

    text = format_report(report)

    sent = 0
    for chat_id in _linked_dev_chats(db):
        try:
            send_message(chat_id, text)
        except TelegramError as exc:
            # Satu chat memblokir bot tak boleh menghentikan pengiriman ke yang lain.
            logger.error("Gagal kirim ke chat %s: %s", chat_id, exc)
        else:
            sent += 1

    report.sent_at = datetime.utcnow()
    db.commit()

    logger.info("%s laporan terkirim ke %d chat", target, sent)
    return sent


def issue_link_code(user_id: str, db: Session) -> str:
    """Buat kode tautan sekali pakai untuk user yang SEDANG LOGIN.

    Kodenya acak-kriptografis, bukan penghitung: ia satu-satunya bukti kepemilikan
    yang dipegang bot, dan kode yang bisa ditebak berarti akun yang bisa dibajak.
    """
    code = secrets.token_hex(_CODE_BYTES).upper()

    profile = db.query(models.Profile).filter(models.Profile.id == user_id).one()
    profile.telegram_link_code = code
    profile.telegram_code_expires_at = datetime.utcnow() + timedelta(minutes=_CODE_TTL_MINUTES)
    db.commit()

    return code


def link_chat(code: str, chat_id: str, db: Session) -> bool:
    """Tautkan `chat_id` ke profil pemilik `code`. False bila kode salah atau kedaluwarsa.

    Kode dibakar setelah dipakai: satu kode, satu chat.
    """
    profile = (
        db.query(models.Profile)
          .filter(models.Profile.telegram_link_code == (code or "").strip().upper())
          .one_or_none()
    )
    if profile is None:
        return False

    expired = (
        profile.telegram_code_expires_at is None
        or profile.telegram_code_expires_at < datetime.utcnow()
    )
    if expired:
        logger.info("Kode tautan kedaluwarsa untuk profil %s", profile.id)
        return False

    profile.telegram_chat_id = str(chat_id)
    profile.telegram_link_code = None
    profile.telegram_code_expires_at = None
    db.commit()

    return True
