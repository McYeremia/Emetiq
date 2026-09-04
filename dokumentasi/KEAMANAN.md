# Keamanan — apa yang menahan eksekusi trade

Ditulis 4 September 2026, setelah pemeriksaan menyeluruh atas satu pertanyaan:
**bisakah orang luar memerintahkan AI Porto melakukan trading?**

Jawabannya tidak. Halaman ini merekam *kenapa* tidak, apa yang sudah diuji, dan apa
yang tetap menjadi tanggung jawab pemilik. Dokumen ini ada supaya pemeriksaan yang
sama tak perlu diulang dari nol — dan supaya perubahan berikutnya tahu pagar mana
yang tidak boleh disenggol.

> Repositori ini publik, jadi halaman ini menjelaskan **bentuk** pengamanannya tanpa
> memuat nilai konfigurasi, nama variabel rahasia, atau langkah yang memudahkan
> orang mengganggu layanan.

---

## 1. Hanya ada dua jalur menuju eksekusi trade

Seluruh basis kode ditelusuri: fungsi yang benar-benar membuat transaksi hanya
dipanggil dari dua tempat, dan tak ada penulis tabel transaksi lain.

| Jalur | Siapa yang bisa melewatinya |
|---|---|
| Endpoint pembuatan trade, dengan tipe trade AI | tier `dev` saja — selain itu **403** |
| Pipeline AI Porto | hanya lewat endpoint chat AI Porto, yang **khusus `dev`** |

Konsekuensinya: menutup dua pintu itu berarti menutup semuanya. Kalau nanti ada
kode baru yang memanggil fungsi eksekusi, ia menjadi pintu ketiga — dan wajib
dipagari dengan sengaja, bukan diasumsikan aman.

**Router pantauan (tier `pro` ke atas) bukan pintu.** Ia tak punya satu pun metode
tulis dan tak mengimpor pipeline AI sama sekali. Permintaan tulis ke sana dijawab
"metode tidak diizinkan", dan ada tes yang menuntut demikian.

---

## 2. Identitas tak bisa dipalsukan

Token login diverifikasi sepenuhnya di sisi server: tanda tangan, penerima yang
dituju, dan masa berlaku. Algoritma yang tidak dikenali ditolak, termasuk token
"tanpa tanda tangan".

Diuji langsung terhadap layanan produksi:

| Yang dikirim | Jawaban server |
|---|---|
| Token tanpa tanda tangan | **401** |
| Token bertanda tangan kunci karangan | **401** |
| Tanpa token sama sekali | **401** |

---

## 3. Yang membuatnya kuat: tier tidak datang dari token

Ini bagian terpenting, dan kebetulan sudah dirancang benar sejak awal.

Token hanya menyatakan **siapa** pemakainya. **Tier** dibaca dari basis data. Jadi
seseorang dengan akun yang benar-benar sah pun tak bisa mengaku bertier `dev` —
tak ada isian di token yang dipercaya untuk itu. Dan mengubah tier siapa pun hanya
bisa lewat endpoint admin, yang juga khusus `dev`.

Artinya, untuk memerintahkan AI Porto seseorang harus benar-benar **memegang sesi
akun dev**. Tak ada jalan memutar lewat token.

---

## 4. Penjaga terhadap kesalahan konfigurasi

Ada flag pengembangan yang, bila aktif, membuat server memperlakukan setiap
pengunjung sebagai user dev tanpa memeriksa token sama sekali. Berguna saat
mengembangkan di laptop; membuka seluruh aplikasi kalau ikut menyala di server.

Yang membuat kesalahan seperti itu berbahaya adalah **diamnya**: tak ada galat, tak
ada log mencurigakan, aplikasinya jalan normal — hanya saja pintunya terbuka.

Karena itu sejak 4 Sep 2026 server **menolak menyala** bila flag itu aktif sementara
basis datanya bukan basis data lokal. Kesalahan konfigurasi berubah dari "diam-diam
terbuka" menjadi "gagal keras dan menjelaskan dirinya sendiri". Pesan galatnya
sengaja tak memuat alamat basis data, karena alamat itu mengandung kata sandi dan
pesan galat mudah tersalin ke tiket atau percakapan.

Penjaganya dipanggil **sebelum** aplikasi menyentuh basis data. Kalau suatu saat
dipindahkan ke posisi setelahnya, ia kehilangan sebagian gunanya.

---

## 5. Yang sudah diperiksa langsung di produksi

Semua tanpa token, dan semuanya hanya permintaan baca:

| Yang diminta | Jawaban |
|---|---|
| Portofolio AI (endpoint dev) | **401** |
| Riwayat transaksi | **401** |
| Daftar pengguna (admin) | **401** |
| Profil sendiri | **401** |

Selain membuktikan pagarnya bekerja, hasil ini sekaligus membuktikan **flag bypass
tidak menyala di produksi** — kalau menyala, jawabannya 200, bukan 401.

---

## 6. Yang tetap menjadi tanggung jawab pemilik

Tiga hal berikut tak bisa diselesaikan oleh kode.

**Sesi akun dev adalah kuncinya.** Siapa pun yang memegangnya bisa memerintahkan AI
Porto. Itu memang desainnya. Jaga akun itu seperti menjaga kunci — termasuk akun
pihak ketiga yang dipakai untuk masuk.

**Rahasia server harus tetap di tempatnya.** Kunci verifikasi token hidup di
penyimpanan rahasia milik penyedia hosting, tak pernah di repositori — dan repo ini
publik. Bocornya kunci itu berarti orang bisa membuat token atas nama siapa pun.

**Tak ada pembatasan laju permintaan.** Pemegang akun sah bisa menembak endpoint
baca berkali-kali. Itu soal beban, bukan soal trading — tapi belum pernah diukur,
dan belum ada penjaganya.

---

## 7. Kalau menambah fitur, periksa ini

Daftar pendek untuk perubahan berikutnya:

1. **Apakah kode baru memanggil fungsi eksekusi trade?** Kalau ya, ia pintu baru —
   pagari dengan sengaja dan tulis tesnya.
2. **Apakah endpoint baru menulis sesuatu?** Endpoint baca dan tulis dipisah dengan
   sengaja di seluruh aplikasi; jangan menggabungkannya demi kepraktisan.
3. **Apakah pagarnya diuji dari dua arah?** Bukan hanya "yang berhak bisa masuk",
   tapi juga "yang tak berhak tetap ditolak". Arah kedua yang biasanya rusak diam-diam.
4. **Apakah tier dibaca dari basis data, bukan dari isian yang dikirim klien?**
   Apa pun yang datang dari klien adalah permintaan, bukan fakta.
