# Keadaan aplikasi — 4 September 2026, diperbarui 25 September 2026

Potret EMETIQ hari ini, ditulis untuk orang yang akan mengubahnya. Bagian paling
berguna ada di bawah: **"Jangan diulang"** dan **"Jangan dibongkar"**.

> Angka kinerja di §2 adalah hasil audit 3–4 September. Yang berubah sesudahnya
> dicatat di §1 (pemicu pekerjaan harian) dan §7 (fitur & perbaikan setelah audit).

---

## 1. Susunan sistem

| Lapisan | Isi | Hidup di |
|---|---|---|
| Frontend | Next.js 16 (App Router, Turbopack), React 19 | Vercel |
| Backend | FastAPI | Hugging Face Space |
| Basis data | Postgres | Supabase |
| Autentikasi | Supabase Auth (email + Google), tier disimpan di tabel profil | — |
| Pekerjaan harian | GitHub Actions (`daily-sync`) menarik harga & fundamental, lalu memindai sinyal | runner GitHub |
| Pemicu pekerjaan harian | Cloudflare Worker menekan `workflow_dispatch` tiap hari kerja pukul 17:30 WIB — penjadwal GitHub sendiri pernah tertunda berjam-jam di antrean, jadi jadwal cron GitHub dimatikan (10 Sep 2026) | Cloudflare |
| Pipeline Big Money | Dijadwalkan dari mesin lokal — IDX menolak permintaan dari IP pusat data | laptop pemilik |

Halaman: landing, Overview, Market/Dashboard, Screener, Portofolio, detail saham,
AI Advisor, AI Porto (tier `dev`), **pantauan AI Porto (tier `pro` ke atas)**,
Big Money (tier `dev`), Admin (tier `dev`), Profil, Masuk, Daftar.

Tier yang dikenal, dari terendah: `free`, `basic`, `pro`, `premium`, `dev`.

---

## 2. Angka kinerja hari ini

Semua diukur dari hasil `next build` produksi dan header respons nyata.

| Ukuran | Sebelum optimalisasi | Sekarang |
|---|---:|---:|
| JavaScript awal halaman landing | 895,1 KB | **676,8 KB** (−24,4%) |
| Payload sekali membuka halaman detail saham | 339,5 KB | **≈16 KB** (−95%) |
| Payload satu siklus polling dashboard | 78,6 KB | **≈16 KB** |
| Kompresi respons API | tak ada | gzip, −77% s.d. −87% |
| Judul halaman ada di HTML awal | 2 dari 14 rute | **14 dari 14** |
| Halaman galat berbahasa Indonesia | tidak ada | 404, 500, dan 500 tingkat aplikasi |
| Tes backend | 408 | **511** (4 Sep) → **542** (10 Sep) |

Berkas statis (`/_next/static/*`) disajikan Vercel dengan
`cache-control: public, max-age=31536000, immutable`, jadi kunjungan berikutnya tak
mengunduh ulang JavaScript. Endpoint data pasar mengirim
`cache-control: public, max-age=300, stale-while-revalidate=3600`.

---

## 3. Jangan diulang — sudah diperiksa, hasilnya baik

Daftar ini yang paling menghemat waktu. Semua sudah diukur; menyelidikinya lagi
hanya membuang waktu kecuali ada bukti baru.

| Dugaan yang wajar | Kenyataan terukur |
|---|---|
| "Ada N+1 query di endpoint baca" | **Tidak.** Setiap jalur baca menembak 1–2 query |
| "Pustaka grafik membebani semua halaman" | **Tidak.** 172,7 KB terisolasi; `dynamic({ ssr: false })` bekerja |
| "Gambar perlu dioptimalkan" | **Tak ada gambar raster** di UI — semuanya SVG/CSS |
| "Tabel bikin geser horizontal di HP" | Sudah dibungkus `overflow-x-auto`; grid sudah `minmax(0,1fr)` |
| "Polling terlalu sering" | Sudah 5 menit, dan berhenti saat tab tak terlihat |
| "ISR belum jalan" | Jalan — dashboard dan overview revalidate tiap 5 menit |
| "Aset diunduh ulang tiap kunjungan" | **Tidak.** Header `immutable` sudah dipasang Vercel |
| "Perlu service worker supaya cepat" | Manfaat asetnya sudah didapat dari header di atas — lihat §5 |

---

## 4. Jangan dibongkar — keputusan yang menahan kerusakan

Setiap butir di sini pernah menjadi masalah nyata, atau menahannya. Mengubahnya
tanpa membaca alasannya kemungkinan besar mengembalikan bug yang sudah mati.

**Backend**

- **Kolam koneksi memakai `pool_pre_ping`.** Space membeku saat idle dan pooler
  Supabase memutus koneksi diam. Tanpa ini, sebagian permintaan menggantung lalu
  gagal — dan hanya sebagian, sehingga gejalanya "sebagian halaman hidup, sebagian
  mati". Tak muncul di lokal.
- **Gerbang NaN pada data harga.** Postgres menerima NaN sebagai angka pecahan yang
  sah, jadi batasan kolom tak menahannya. Sekali lolos, ratusan saham kehilangan
  harga tanpa satu pun galat.
- **Indikator dibaca dari 300 baris terakhir, bukan rentang tanggal.** Batas
  berbasis tanggal terlihat setara tapi mengosongkan indikator saham yang lama tak
  berdagang. Batas jumlah baris benar di ketiga keadaan: data segar, data basi, dan
  saham suspensi.
- **Tak ada jalur HTTP untuk pekerjaan seluruh pasar.** Sinkronisasi & pemindaian
  sinyal dijalankan lewat GitHub Actions, bukan permintaan web. Selain berat, jalur
  lamanya mengosongkan tabel sinyal lebih dulu — run yang terpotong meninggalkan
  tabel kosong yang dibaca fitur lain.
- **Hanya satu pemicu harian.** Alasan yang sama — tabel sinyal dikosongkan dulu
  sebelum dihitung ulang — membuat dua run yang tumpang tindih berbahaya. Karena itu
  jadwal cron GitHub dimatikan begitu pemicu Cloudflare terbukti jalan. Berkas
  workflow-nya **jangan dihapus atau diganti nama**: pemicu memanggilnya lewat nama
  berkas, dan kegagalan itu tak memunculkan job merah apa pun.
- **Screening AI Advisor juga sumber kandidat AI Porto.** Mengubah cara Advisor
  menyaring atau mengurutkan saham ikut mengubah saham yang dipertimbangkan AI Porto,
  walau tak satu berkas AI Porto pun disentuh.
- **Rute statis baru di bawah `/stocks` wajib didaftarkan ke daftar penjaga.**
  Semua rute statis di router itu GET, jadi `POST /stocks/<apa pun>` jatuh ke
  penangan "tambah saham bernama itu".
- **Endpoint baca pasar sengaja publik; endpoint tulis dan berat butuh login.**
  Header cache `public` hanya sah selama jawabannya sama untuk semua orang. Kalau
  suatu saat endpoint baca ikut dipagari, nilai header itu **wajib** berubah jadi
  `private`.
- **Laporan (Telegram, ringkasan LLM) adalah lapisan kabar, bukan data.**
  Kegagalannya tak boleh menjatuhkan pipeline: skor yang sudah tersimpan lebih
  berharga daripada narasinya.
- **Server menolak menyala bila mode bypass autentikasi aktif di atas basis data
  jauh.** Ada flag pengembangan yang meloloskan setiap permintaan sebagai user dev —
  berguna di laptop, bencana di server: siapa pun bisa mengubah tier orang lain dan
  memerintahkan AI Porto mengeksekusi trade. Yang membuatnya berbahaya adalah
  diamnya; aplikasi tetap jalan normal dengan pintu terbuka. Penjaga di `auth.py`
  mengubahnya jadi kegagalan keras saat boot. Jangan dilepas, dan jangan dipindah ke
  posisi setelah aplikasi menyentuh basis data.
- **Hari non-bursa bukan kegagalan.** Bursa membalas "tak ada baris" di akhir pekan
  dan libur; pipeline berhenti tenang dan job tetap hijau. Job merah tiap Sabtu
  hanya melatih orang mengabaikan alarm.

**Frontend**

- **Klien Supabase diunduh malas, dan hanya bila ada sesi tersimpan.** Menariknya
  kembali ke impor biasa mengembalikan 225 KB ke setiap halaman, termasuk landing
  dan halaman 404.
- **Halaman login memanggil pemberitahuan sesi sebelum berpindah halaman.**
  Perpindahan di sisi klien tidak me-mount ulang kerangka aplikasi, jadi tanpa
  langkah itu login yang berhasil pun tak terlihat.
- **Dashboard dan overview mengambil data di server, bukan di browser.** Versi
  lamanya mengirim cangkang kosong lalu menembak tiga permintaan setelah hidrasi —
  itu sumber "kedip-kedip"-nya.
- **Satu aturan CSS menahan zoom otomatis iOS**, bukan sebelas berkas yang diubah
  satu per satu. Menaikkan ukuran huruf di tiap berkas ikut mengubah tampilan
  desktop yang tak bermasalah.
- **Satu sistem font (dilayani sendiri).** Aplikasi ini pernah menjalankan tiga
  sekaligus; yang menang selalu yang paling lambat.
- **Grafik dimuat terpisah dan tanpa render server.** Itu yang menahan 172,7 KB
  keluar dari halaman yang tak butuh grafik.
- **Label tanggal data mengambil tanggal dari data yang sudah ada di halaman.**
  Jangan menambahkannya kembali ke payload ringkas — payload itu di-polling tiap
  lima menit oleh setiap tab yang terbuka.
- **AI Porto (tier `dev`) dan pantauannya (tier `pro` ke atas) adalah dua hal
  terpisah, dan sengaja begitu.** Halaman `dev` mengeksekusi trade sungguhan lewat
  LLM; halaman pantauan hanya membaca. Keduanya tak berbagi router, tak berbagi
  komponen tampilan, dan pantauannya tak mengimpor satu pun pipeline AI. Menyatukan
  keduanya "supaya tidak duplikat" berarti membuat permukaan yang mengeksekusi trade
  bisa tersentuh dari jalur yang dipakai penonton. Harga dari pemisahan ini nyata —
  mengubah tampilan di satu tempat tak mengubah yang lain — dan itu memang harga yang
  dipilih. Satu-satunya yang dipakai bersama adalah fungsi layanan yang murni
  membaca, dan ada tes yang menuntut keduanya memulangkan angka yang identik.

---

## 5. Sengaja tidak dikerjakan

Bukan lupa. Masing-masing punya alasan terukur.

**Service worker / mode offline penuh.** Alasan terbesarnya gugur setelah diukur:
berkas statis sudah disimpan browser setahun (`immutable`), jadi manfaat yang tersisa
hanya "aplikasi tetap terbuka saat benar-benar tanpa koneksi". Ia juga satu-satunya
perubahan yang **menempel di perangkat pengguna** dan butuh langkah khusus untuk
dicabut. Untuk aplikasi yang datanya berubah sekali sehari, tukar itu tidak sepadan.
Sebagai gantinya dipasang penanda: bilah pemberitahuan saat koneksi putus, dan label
tanggal data di dekat angkanya.

> Kalau suatu saat dipertimbangkan lagi, satu hal ini perlu diperiksa lebih dulu:
> sebagian browser mensyaratkan service worker sebelum menawarkan "Tambahkan ke layar
> utama". Itu belum pernah diuji di ponsel.

**Mengganti pustaka autentikasi dengan yang lebih ramping.** Pustaka yang dipakai
ikut membawa modul realtime yang tak terpakai. Memangkasnya berarti **mengganti**
penanganan sesi, bukan menundanya — dan titik paling rawannya persis di sana. Jadi
pekerjaan tersendiri, bukan tambahan.

**Ajakan naik tier di kartu "khusus tier X".** Kartu yang muncul untuk tier yang
belum berhak sengaja hanya **menjelaskan** fitur dan tier pengguna saat ini — tanpa
tombol apa pun. Alasannya sederhana: **aplikasi ini belum punya jalur naik tier sama
sekali.** Tak ada halaman paket, tak ada pembayaran, dan halaman profil hanya
menampilkan tier tanpa cara mengubahnya; tier diatur manual oleh pemilik lewat
dashboard basis data.

Menambahkan tombol sekarang berarti mengarahkan orang ke jalan buntu yang lain.
Keputusan pemilik repo (4 Sep 2026): biarkan apa adanya, **halaman paket menyusul** —
dan begitu halaman itu ada, ia menjadi tujuan yang benar untuk semua kartu bertier di
aplikasi, bukan cuma yang di pantauan AI Porto.

> Gap ini berlaku di seluruh aplikasi, bukan hanya satu halaman: Big Money dan kuota
> AI Advisor juga bertingkat tier tanpa jalan naik.

**Menampilkan jam pembaruan data.** Data harian hanya membawa tanggal, tidak jam.
Menuliskan jam berarti mengarang ketelitian yang tak dimiliki datanya.

---

## 6. Batas yang diketahui

Jujur soal yang belum terbukti, supaya tak ada yang menganggapnya beres:

- **Perilaku Safari iOS belum diuji di perangkat nyata.** Aturan CSS-nya terkirim
  dan ukurannya benar, tapi kesimpulannya berasal dari perilaku Safari yang
  terdokumentasi, bukan dari iPhone sungguhan.
- **Belum ada skor Lighthouse / Core Web Vitals.** Semua angka di dokumen ini adalah
  *byte* dan *jumlah permintaan*, bukan waktu render yang dirasakan pengguna.
- **Bilah offline diuji dengan event buatan.** `navigator.onLine` melaporkan koneksi
  tingkat sistem operasi, jadi pada kasus "terhubung tapi tak ada internet" ia tetap
  melaporkan online dan bilahnya tak muncul. Yang menolong pembaca di keadaan itu
  hanya label tanggal.
- **Endpoint yang butuh login belum diukur** — pengukurannya butuh sesi yang sah.
- **Waktu screener di produksi belum diukur.** Angka yang ada berasal dari basis data
  lokal dan CPU laptop.

---

## 7. Fitur & perbaikan setelah audit

**Pantauan AI Porto (4 Sep 2026), tier `pro` ke atas.** Tier di bawah `dev` kini bisa
melihat portofolio yang dikelola AI: nilai, posisi terbuka, dan histori jual/beli
lengkap dengan **alasan AI di tiap transaksi**. Alasan itu sudah tersimpan sejak lama
tapi tak pernah ditampilkan; justru itu isi yang membuat halaman ini layak dibuka.

Yang perlu diketahui orang berikutnya:

- Halaman ini **hanya melihat**. Perintah dan eksekusi tetap khusus `dev`.
- Ia hidup di router dan halaman yang **terpisah sepenuhnya** dari AI Porto — lihat
  alasannya di §4 dan di [`KEAMANAN.md`](KEAMANAN.md).
- Badge rezim risiko tak ikut ditampilkan: nilainya datang dari balasan pipeline AI,
  bukan dari data tersimpan. Menampilkannya berarti menjalankan AI-nya.
- Datanya dimuat **sekali**, tanpa polling. Porto AI hanya berubah saat pemiliknya
  menjalankan AI; polling berkala oleh tiap penonton berarti kueri berulang untuk
  angka yang sama.
- Tier di bawah `pro` **tak melihat menunya sama sekali**; membuka alamatnya
  langsung memberi kartu ajakan upgrade, bukan halaman kosong. Yang benar-benar
  menahan akses tetap backend, yang menolak dengan 403.
- Histori ditampilkan **lima terbaru** lebih dulu, sisanya di balik satu tombol.
  Endpoint histori memulangkan **terbaru di depan** — jangan membaliknya, dan
  "transaksi terakhir" ada di indeks 0, bukan di ujung. Versi pertama halaman ini
  salah di dua-duanya sekaligus karena satu asumsi urutan yang keliru.

**Perbaikan AI Advisor (10 Sep 2026).** Hasil pencarian saham kini diurutkan menurut
**seberapa cocok dengan kriteria yang diminta**, bukan menurut besar perusahaan;
indikator teknikal selalu dihitung untuk kandidat; angka portofolio memakai satu
sumber yang sama dengan eksekusi trade; dan layar chat mendapat panel filter serta
label tahap + penghitung detik selama menunggu. Tes backend 511 → **542**.

Yang perlu diketahui orang berikutnya:

- Karena AI Porto mengambil kandidat dari screening yang sama, **urutan kandidat
  AI Porto ikut berubah** walau kodenya tak disentuh — lihat §4.
- Label tahap di layar chat **urutannya benar tapi waktunya perkiraan**: backend
  belum mengirim kabar kemajuan. Penghitung detiknya angka sungguhan.
- Kuota harian per tier tidak diubah; itu keputusan harga, bukan teknis.

---

## 8. Cara mengukur tanpa menyentuh basis data produksi

Ada salinan basis data lokal (SQLite) berisi ratusan ribu baris harga untuk keperluan
ini. Datanya berhenti di suatu tanggal di masa lalu, jadi ia dipakai untuk mengukur
**bentuk dan volume**, bukan untuk membaca harga.

Dua hal yang paling sering menjebak:

1. **Jendela tanggal dihitung mundur dari hari ini.** Terhadap salinan lokal yang
   sudah tua, jendela itu kosong dan pengukurannya tak sah. Kesalahan ini sudah
   terjadi tiga kali; geser jendelanya, atau ukur terhadap ujung datanya sendiri.
2. **Menjalankan uvicorn atau skrip tanpa penimpaan akan menyambung ke produksi.**
   Suite tes sudah dipagari, tetapi perintah manual belum.

Perinciannya ada di `frontend/AUDIT-OPTIMALISASI.md` §2 (lokal, tidak ter-commit).
