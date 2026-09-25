# Riwayat optimalisasi — 3–4 September 2026

Catatan apa yang berubah, kenapa, dan seberapa besar dampaknya. Semua angka diukur,
bukan diperkirakan. Nomor commit disertakan supaya tiap klaim bisa ditelusuri.

Titik berangkatnya sebuah audit yang dikerjakan **sebelum** satu baris kode diubah,
dengan tujuh temuan berdampak. Ketujuhnya kini tertutup.

---

## Tahap 1 — hal termurah dengan dampak terbesar

`94db54ae` · `f0dcf94f` · `e6470520`

| Perubahan | Dampak terukur |
|---|---|
| Kompresi gzip pada respons API | **−77% s.d. −87%** byte di setiap endpoint. Sebuah respons 25.210 byte turun jadi 3.638 |
| Header `Cache-Control` pada 5 endpoint data pasar | Perpindahan halaman dan muat ulang tak lagi mengunduh ulang |
| `lang="id"` pada dokumen HTML | Pembaca layar berhenti melafalkan teks Indonesia dengan fonem Inggris |
| Satu aturan CSS untuk menahan zoom otomatis iOS | Menekan kolom pencarian di iPhone tak lagi membuat halaman melompat |

Dua catatan yang layak diingat:

- Kompresi **ditambahkan sebelum** CORS. Middleware yang ditambahkan terakhir menjadi
  lapisan terluar, dan CORS harus berada di sana. Ada tes yang menjaganya.
- Rencana awal anti-zoom adalah menyunting sebelas berkas. Yang dipakai akhirnya satu
  aturan `@media (pointer: coarse)` — bug itu milik perangkat sentuh, bukan layar
  sempit. iPad lanskap itu lebar tapi tetap kena; jendela desktop yang dikecilkan itu
  sempit tapi tidak.

---

## Tahap 2 — berhenti mengirim byte yang tak dipakai

`e4c73d75`

Sekali membuka halaman detail saham dulu menarik **339,5 KB**: seluruh riwayat harga
saham itu (1.218 baris, padahal layar menampilkan 58) ditambah daftar lengkap 737
saham dengan sepuluh kolom, padahal daftar sampingnya hanya menampilkan empat.

| Perubahan | Hasil |
|---|---|
| Daftar samping memakai payload ringkas | 174,2 KB → **14,5 KB** |
| Riwayat harga mengikuti rentang waktu yang dipilih | 165,0 KB → **1,5 KB** |
| Indikator dihitung dari 300 baris terakhir | Ratusan baris tak lagi ditarik dari basis data per permintaan |
| Pengambilan data yang hasilnya tak pernah ditampilkan — dibuang | −6,1 KB per siklus polling per tab |
| Tombol bintang diberi area sentuh 44×44 px dan label aksesibilitas | Dulu 12–18 px, di bawah semua standar |

**Total halaman detail saham: 339,5 KB → ≈16 KB (−95%).**

> **Kesalahan yang layak dicatat.** Percobaan pertama membatasi indikator dengan
> rentang tanggal, dan itu menghapus rata-rata 200 hari untuk sebagian saham tanpa
> galat apa pun — nilainya diam-diam jadi kosong. Tes pertamanya pun tak bisa gagal,
> karena datanya dibuat berurutan sempurna. Perbaikannya: batasi **jumlah baris**,
> dan buat tes yang menuntut saham yang lama tak berdagang tetap punya indikator.

---

## Tahap 3 — pagar, pembersihan, dan satu pemangkasan besar

`57a159b1` · `946df121` · `deabb0b4` · `ebcbe9f0`

**Pemagaran.** Endpoint yang menulis data atau memakan CPU berat kini menuntut login;
endpoint baca data pasar sengaja tetap terbuka karena halaman publik menariknya tanpa
sesi. Ada tes yang menjaga **kedua arah** — arah kedua yang paling mudah rusak tanpa
disadari.

**Pembersihan.** Sebuah fitur pengambilan data yang tak pernah tertaut dari mana pun,
tanpa tes, dengan 88 baris data, dan yang secara teknis tak mungkin berhasil dari
lingkungan produksi — dihapus seluruhnya, bukan dipagari. Tabelnya dipertahankan
beserta penjelasan alasannya di kode.

**Pekerjaan seluruh pasar keluar dari HTTP.** Sinkronisasi dan pemindaian sinyal
dulu bisa dipicu lewat permintaan web. Selain menyandera pekerja yang sedang melayani
pengunjung, jalur pemindaiannya mengosongkan tabel sinyal lebih dulu — run yang
terpotong meninggalkan tabel kosong. Semuanya pindah ke GitHub Actions, dan satu
router menyusut **461 → 353 baris**.

**Font: tiga sistem jadi satu.** Aplikasi ini menjalankan tiga sistem font sekaligus,
salah satunya lewat tiga belas tag stylesheet ke penyedia luar. Sekarang satu sistem,
dilayani dari domain sendiri: nol koneksi lintas-origin di jalur render.

**Pustaka autentikasi jadi impor malas.** Ini yang terbesar. Pustakanya 225 KB dan
ikut terunduh di **setiap** halaman — termasuk landing dan halaman 404 yang tak punya
satu pun elemen login.

| Rute | Sebelum | Sesudah |
|---|---:|---:|
| Landing | 900,1 KB | **675,4 KB** |
| Halaman masuk | 861,5 KB | 636,9 KB |
| Halaman 404 | 850,9 KB | 626,2 KB |

> **Impor malas saja tidak cukup**, dan ini pelajaran yang mudah terlewat: pemeriksa
> sesi hidup di kerangka aplikasi dan berjalan di setiap halaman, jadi pustakanya
> tetap akan ditarik — cuma beberapa detik lebih lambat. Angka build membaik,
> kuota pengunjung tidak. Yang benar-benar menghapusnya adalah memeriksa dulu apakah
> browser ini menyimpan sesi, tanpa memuat pustakanya. Kalau ragu, ia memuat —
> salah memuat cuma boros, salah tidak memuat berarti orang terlihat logout.

---

## Tahap 4 — jalur gagal, judul halaman, dan penanda kesegaran data

`898a4718` · `a6d02c42` · `8f3ea6b0`

**Halaman galat.** Sebelumnya tak ada satu pun, jadi galat menampilkan layar bawaan
kerangka kerja: berbahasa Inggris, tanpa jalan pulang. Kini ada tiga — 404, 500, dan
500 tingkat aplikasi untuk kasus kerangka aplikasinya sendiri yang gagal.

> Halaman galat tak bisa dibuktikan dengan permintaan HTTP biasa: ia komponen sisi
> klien, jadi yang terkirim hanyalah cangkang kosong sampai halaman dihidupkan di
> browser. Verifikasinya wajib di browser sungguhan.

**Judul halaman.** Dua belas halaman menyetel judulnya setelah halaman hidup di
browser. Bagi pengunjung tak terasa; bagi mesin pencari dan pratinjau tautan, semua
halaman berjudul sama. Kini **14 dari 14** rute membawa judulnya sendiri sejak byte
pertama, dan halaman di balik login ditandai agar tak diindeks.

Biayanya diukur, tidak diasumsikan: pemecahan itu **nol byte** di sisi klien;
yang menambah hanya halaman galat, +5,0 KB merata di semua rute. Angka pertamanya
+16,3 KB, lalu turun setelah tautan di halaman galat diganti tautan biasa — dari
sebuah halaman galat, navigasi sisi klien memang pilihan yang salah, karena
kerangkanya bagian dari yang barusan gagal. Perubahan yang lebih benar ternyata
sekaligus yang lebih murah.

**Satu bug ikut tertutup.** Saham dengan riwayat harga sangat pendek — praktisnya
saham yang baru melantai — membuat endpoint indikator gagal keras. Gejalanya bahkan
lebih luas dari dugaan: halaman detailnya menarik harga dan indikator dalam satu
tarikan, jadi grafiknya pun ikut kosong dan pesan galatnya menuduh koneksi.

**Penanda kesegaran data.** Aplikasi ini tak pernah menampilkan tanggal data di mana
pun. Kalau sinkronisasi harian gagal tiga hari berturut-turut, layar tetap menyajikan
harga lama dengan percaya diri. Sekarang ada label tanggal di dekat angkanya —
berubah jadi peringatan bila lewat tujuh hari — dan bilah pemberitahuan saat koneksi
putus. Keduanya **tak menambah satu byte pun** ke jaringan: tanggalnya diambil dari
data yang sudah ada di halaman.

---

## Yang diputuskan untuk dilewati

**Service worker.** Dua keputusan desainnya sudah diambil ketika pengukuran
membatalkan alasan terbesarnya — berkas statis ternyata sudah disimpan browser
setahun. Rinciannya di [`KEADAAN-APLIKASI.md` §5](KEADAAN-APLIKASI.md#5-sengaja-tidak-dikerjakan).

---

## Ringkasan angka

| | Sebelum | Sesudah |
|---|---:|---:|
| JavaScript awal landing | 895,1 KB | **676,8 KB** (−24,4%) |
| Halaman detail saham, sekali buka | 339,5 KB | **≈16 KB** (−95%) |
| Polling dashboard, per siklus | 78,6 KB | **≈16 KB** (−79%) |
| Rute dengan judul sendiri di HTML | 2 dari 14 | **14 dari 14** |
| Tes backend | 408 | **476** ¹ |

¹ Angka di akhir Tahap 4. Pada hari yang sama tes bertambah jadi **511** (pantauan
AI Porto + penjaga mode bypass), lalu **542** pada 10 Sep 2026 (perbaikan AI Advisor).
Angka terkini ada di [`KEADAAN-APLIKASI.md` §2](KEADAAN-APLIKASI.md#2-angka-kinerja-hari-ini).

---

## Cara kerja yang terbukti berguna

Tiga kebiasaan yang beberapa kali menyelamatkan pekerjaan ini, layak dipakai lagi:

1. **Ukur sebelum mengerjakan, dan ukur lagi sesudahnya — dengan alat yang sama.**
   Satu kali angka "sebelum" dan "sesudah" nyaris dibandingkan dari dua skrip
   berbeda. Itu cara paling mudah menuliskan kesimpulan yang salah dengan penuh
   percaya diri.
2. **Pastikan tes barunya bisa gagal.** Dua tes di pekerjaan ini lulus sambil tak
   menjaga apa pun, karena datanya dibuat terlalu rapi. Ubah kodenya jadi salah dan
   pastikan tesnya merah, baru percaya.
3. **Catat rencana yang berubah beserta alasannya.** Beberapa rencana berubah di
   tengah jalan — anti-zoom dari sebelas berkas jadi satu aturan, batas indikator
   dari tanggal jadi jumlah baris, service worker dari "dikerjakan" jadi "dilewati".
   Tanpa catatan alasannya, orang berikutnya hanya melihat dokumen menyuruh A
   sementara kodenya berisi B.
