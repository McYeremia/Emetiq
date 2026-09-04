/**
 * Tampilan bersama untuk tiga halaman jalur-gagal: `not-found`, `error`, dan
 * `global-error`. Sebelum 4 Sep 2026 ketiganya tak ada sama sekali, jadi yang
 * muncul adalah layar bawaan Next — berbahasa Inggris, tanpa jalan pulang, dan
 * tak menyerupai aplikasi ini sedikit pun.
 *
 * Sengaja TANPA `'use client'`: `not-found.tsx` tetap server component (jadi
 * 404-nya terkirim sebagai HTML, bukan setelah hidrasi), sementara `error.tsx`
 * yang memang wajib klien tetap boleh mengimpornya.
 *
 * Warnanya disalin dari `EmetiqNav`, bukan diimpor: halaman ini harus tetap utuh
 * justru ketika sesuatu di aplikasi rusak, jadi ia sengaja tak bergantung pada
 * modul lain mana pun.
 */
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#55554E';
const HAIR = '#ECEBE6';
const ACCENT = '#F26A1B';

/** Tombol/tautan aksi. 44px tinggi minimum — ambang sentuh Apple HIG, sama
 *  dengan `.emx-tap` yang dipakai tombol bintang sejak Tahap 2. */
export const tombolUtama: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  minHeight: 44, padding: '0 20px', borderRadius: 11, border: 'none',
  background: ACCENT, color: '#fff', fontWeight: 700, fontSize: 15,
  textDecoration: 'none', cursor: 'pointer',
  boxShadow: `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 64%)`,
};

export const tombolKedua: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
  minHeight: 44, padding: '0 18px', borderRadius: 11,
  border: `1px solid ${HAIR}`, background: '#fff', color: INK,
  fontWeight: 600, fontSize: 15, textDecoration: 'none', cursor: 'pointer',
};

export default function PesanGalat({
  kode,
  judul,
  penjelasan,
  jejak,
  children,
}: {
  /** Angka besar di atas judul — "404", "500". */
  kode: string;
  judul: string;
  penjelasan: string;
  /** `error.digest` dari Next. Pesan galat aslinya disensor di produksi, jadi
   *  kode inilah satu-satunya yang menghubungkan laporan pengguna dengan log. */
  jejak?: string;
  /** Tombol aksinya — berbeda antara 404 dan galat, jadi diserahkan pemanggil. */
  children: React.ReactNode;
}) {
  return (
    <main
      style={{
        minHeight: '100dvh', background: BG, color: INK,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: '32px 20px',
      }}
    >
      <div style={{ width: '100%', maxWidth: 460, textAlign: 'center' }}>
        <div style={{ fontWeight: 800, fontSize: 19, letterSpacing: '.06em', marginBottom: 28 }}>
          EMETIQ
        </div>

        <div
          style={{
            background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 18,
            boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
            padding: '32px 24px',
          }}
        >
          <div
            aria-hidden="true"
            style={{
              fontFamily: 'var(--font-plex-mono), ui-monospace, monospace',
              fontSize: 44, fontWeight: 600, lineHeight: 1,
              color: `color-mix(in oklab, ${ACCENT}, white 24%)`,
            }}
          >
            {kode}
          </div>

          <h1 style={{ fontSize: 21, fontWeight: 700, margin: '18px 0 8px' }}>{judul}</h1>

          <p style={{ fontSize: 15, lineHeight: 1.6, color: MUTED, margin: 0 }}>{penjelasan}</p>

          <div
            style={{
              display: 'flex', flexWrap: 'wrap', gap: 10,
              justifyContent: 'center', marginTop: 26,
            }}
          >
            {children}
          </div>

          {jejak && (
            <p
              style={{
                fontFamily: 'var(--font-plex-mono), ui-monospace, monospace',
                fontSize: 11.5, color: MUTED, marginTop: 22, marginBottom: 0,
                wordBreak: 'break-all',
              }}
            >
              Kode kejadian: {jejak}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
