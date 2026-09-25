# Dokumentasi EMETIQ

Folder ini menjawab satu pertanyaan: **apa yang sudah dikerjakan, sampai mana, dan
apa yang tak perlu diulang.** Ia dibuat supaya pekerjaan berikutnya — oleh siapa pun,
di komputer mana pun — tidak mulai dari nol dan tidak mengulang hal yang sudah
diperiksa.

| Berkas | Isinya | Baca kalau… |
|---|---|---|
| [`KEADAAN-APLIKASI.md`](KEADAAN-APLIKASI.md) | Keadaan aplikasi hari ini: susunan sistem, angka kinerja, dan **daftar hal yang tak boleh dibongkar** | …Anda akan menyentuh kode ini |
| [`RIWAYAT-OPTIMALISASI.md`](RIWAYAT-OPTIMALISASI.md) | Apa yang berubah 3–4 September 2026, beserta angka dan nomor commit-nya | …Anda ingin tahu kenapa sesuatu dibuat begitu |
| [`KEAMANAN.md`](KEAMANAN.md) | Apa yang menahan eksekusi trade, apa yang sudah diuji, dan apa yang tetap tanggung jawab pemilik | …Anda menyentuh autentikasi, tier, atau apa pun di dekat AI Porto |
| `STRATEGI-AI-PORTO.md` **(lokal saja)** | Bagaimana AI Porto memutuskan beli dan jual: rezim risiko, skor kandidat, dan pagar yang dipaksakan kode | …Anda ingin paham atau menyetel perilaku AI-nya |
| `AUDIT-ADVISOR.md` **(lokal saja)** | Audit AI Advisor 10 Sep 2026: temuan, perbaikan yang sudah dikerjakan, dan yang sengaja ditunda | …Anda menyentuh `services/advisor/` |

## Kenapa folder ini ter-commit, sementara catatan lain tidak

Repo ini punya empat dokumen internal yang **sengaja** di-`.gitignore` dan hanya hidup
di disk pemiliknya: `CLAUDE.md`, `frontend/AUDIT-OPTIMALISASI.md`,
`frontend/CATATAN-FRONTEND.md`, dan `frontend/CATATAN-BACKEND.md`. Keempatnya jauh
lebih rinci daripada folder ini.

`STRATEGI-AI-PORTO.md` dan `AUDIT-ADVISOR.md` di tabel atas juga begitu — **keduanya
tidak ikut ter-commit.** Yang pertama menjelaskan cara AI Porto memilih dan
mengeksekusi trade; yang kedua memuat daftar kelemahan layanan yang sedang hidup.
Keduanya bukan sesuatu yang perlu diumumkan di repositori publik. Kalau berkasnya tak
ada di komputer Anda, berarti ia memang tak pernah ikut; sumber kebenarannya tetap
kode di `backend/services/ai_porto/` dan `backend/services/advisor/`.

Masalahnya: dokumen yang tak ter-commit **tidak berpindah**. Sesi kerja di komputer
lain tak akan melihatnya sama sekali — dan itulah persis yang membuat pekerjaan
terulang. Folder ini ter-commit supaya kesimpulan pentingnya ikut ke mana pun repo
ini pergi.

> **Repositori ini publik.** Karena itu folder ini ditulis dengan asumsi siapa pun
> bisa membacanya: tak ada nilai konfigurasi, tak ada kunci, tak ada rincian yang
> memudahkan orang mengganggu layanan. Rincian operasional yang lebih terbuka tetap
> tinggal di empat dokumen lokal di atas.
