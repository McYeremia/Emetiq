/**
 * Kerangka yang tampil seketika sementara data pasar di-stream dari server.
 *
 * Next membungkus halaman dalam Suspense begitu berkas ini ada, jadi cangkang
 * ini terkirim di byte pertama — sebelum backend menjawab, bahkan sebelum
 * bundel JS selesai diunduh. Bentuknya sengaja meniru tata letak overview
 * (grafik di atas, daftar saham di bawah) supaya isinya tidak terasa
 * melompat saat menggantikan kerangka ini.
 */
const BG = '#FCFCFB';
const HAIR = '#ECEBE6';
const SKEL = '#F1F0EC';

const CARD: React.CSSProperties = {
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 18,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

function Balok({ w, h, r = 6 }: { w: number | string; h: number; r?: number }) {
  return <div style={{ width: w, height: h, borderRadius: r, background: SKEL }} />;
}

export default function Loading() {
  return (
    <div style={{ minHeight: '100vh', background: BG }} aria-busy="true" aria-label="Memuat overview">
      <div className="animate-pulse" style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px' }}>
        {/* baris navigasi */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
          <Balok w={116} h={22} />
          <div style={{ display: 'flex', gap: 10 }}>
            <Balok w={72} h={22} />
            <Balok w={72} h={22} />
            <Balok w={36} h={22} r={999} />
          </div>
        </div>

        {/* kartu grafik IHSG */}
        <div style={{ ...CARD, padding: 20, marginBottom: 18 }}>
          <Balok w={128} h={14} />
          <div style={{ height: 12 }} />
          <Balok w={188} h={30} />
          <div style={{ height: 18 }} />
          <Balok w="100%" h={168} r={12} />
        </div>

        {/* daftar saham */}
        <div style={{ ...CARD, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 18 }}>
            <Balok w={148} h={14} />
            <Balok w={96} h={28} r={8} />
          </div>
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                gap: 12, padding: '12px 0',
                borderTop: i === 0 ? 'none' : `1px solid ${HAIR}`,
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                <Balok w={72} h={13} />
                <Balok w={136} h={10} />
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Balok w={68} h={13} />
                <Balok w={66} h={20} r={6} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
