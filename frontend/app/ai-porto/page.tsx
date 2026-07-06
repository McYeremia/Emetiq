'use client';

import { useEffect, useRef, useState } from 'react';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import { useAuth } from '@/components/AuthProvider';
import { api, AiPortoResponse, AiPortoSnapshot, TradeHistory } from '@/lib/api';

// ── EMETIQ theme tokens ────────────────────────────────────────
const ACCENT = '#F26A1B';
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#56564F';
const FAINT = '#9A9A92';
const HAIR = '#ECEBE6';
const UP = '#138A50';
const DOWN = '#D23B3B';
const AMBER = '#B7791F';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

const CARD: React.CSSProperties = {
  background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 16,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

const rp = (n: number | null | undefined) =>
  n == null ? '—' : 'Rp ' + Math.round(n).toLocaleString('id-ID');

const REGIME: Record<string, { label: string; color: string }> = {
  AGGRESSIVE: { label: 'Agresif', color: UP },
  NORMAL: { label: 'Normal', color: AMBER },
  DEFENSIVE: { label: 'Defensif', color: DOWN },
};

type Msg = { role: 'user' | 'assistant'; content: string; resp?: AiPortoResponse };

const WELCOME: Msg = {
  role: 'assistant',
  content: 'Ini porto yang saya kelola. Beri saya perintah — mis. **"cari peluang & kelola porto, maksimalkan profit"** — dan saya akan langsung mengeksekusi trade.',
};

export default function AiPortoPage() {
  return (
    <RequireAuth>
      <DevGate />
    </RequireAuth>
  );
}

function DevGate() {
  const { tier, loading } = useAuth();
  if (loading) return null;
  if (tier !== 'dev') return <NotDev />;
  return <AiPortoInner />;
}

function NotDev() {
  useEffect(() => { document.title = 'AI Porto — EMETIQ'; }, []);
  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS }}>
      <EmetiqNav />
      <div style={{ maxWidth: 520, margin: '0 auto', padding: '80px 20px', textAlign: 'center' }}>
        <div style={{ ...CARD, padding: 32 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Khusus tier developer</h1>
          <p style={{ marginTop: 10, fontSize: 14.5, color: MUTED, lineHeight: 1.6 }}>
            Fitur <strong>AI Porto</strong> hanya tersedia untuk akun bertier <code>dev</code>.
          </p>
        </div>
      </div>
    </main>
  );
}

function AiPortoInner() {
  useEffect(() => { document.title = 'AI Porto — EMETIQ'; }, []);
  const [messages, setMessages] = useState<Msg[]>([WELCOME]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [snapshot, setSnapshot] = useState<AiPortoSnapshot | null>(null);
  const [regime, setRegime] = useState<string | null>(null);
  const [history, setHistory] = useState<TradeHistory[]>([]);
  const [histOpen, setHistOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshHistory = () => { api.getTradeHistory('AI').then(setHistory).catch(() => {}); };

  useEffect(() => {
    api.getAiPorto().then(setSnapshot).catch(() => {});
    refreshHistory();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || loading) return;
    const next: Msg[] = [...messages, { role: 'user', content: message }];
    setMessages(next);
    setInput('');
    setLoading(true);
    try {
      const resp = await api.aiPortoChat({ message });
      setMessages([...next, { role: 'assistant', content: resp.reply, resp }]);
      if (resp.snapshot) setSnapshot(resp.snapshot);
      if (resp.regime) setRegime(resp.regime);
      // AI mungkin baru mengeksekusi trade — segarkan histori jual/beli.
      if ((resp.executed?.length ?? 0) > 0 || (resp.auto_exits?.length ?? 0) > 0) refreshHistory();
    } catch {
      setMessages([...next, { role: 'assistant', content: 'Gagal menghubungi AI Porto. Periksa koneksi backend.' }]);
    } finally {
      setLoading(false);
    }
  };

  const pnl = snapshot ? snapshot.total_value - 15_000_000 : 0;
  const pnlPct = snapshot ? (pnl / 15_000_000) * 100 : 0;

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />
      <EmetiqNav active="ai-porto" />

      <div style={{ maxWidth: 1080, margin: '0 auto', padding: '24px 18px 28px', display: 'grid', gridTemplateColumns: 'minmax(0,1fr) 340px', gap: 20, alignItems: 'start' }} className="aip-grid">
        {/* Chat column */}
        <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 116px)' }}>
          <div className="mb-4">
            <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>AI Porto</h1>
            <p style={{ marginTop: 3, fontSize: 13.5, color: MUTED }}>Portofolio otonom — AI memilih saham & mengeksekusi trade atas perintahmu.</p>
          </div>

          <div ref={scrollRef} className="aip-scroll" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14, paddingRight: 4 }}>
            {messages.map((m, i) => <Bubble key={i} msg={m} />)}
            {loading && (
              <div style={{ alignSelf: 'flex-start', ...CARD, padding: '12px 16px', display: 'flex', gap: 6 }}>
                <Dot /> <Dot d={0.15} /> <Dot d={0.3} />
              </div>
            )}
          </div>

          <div style={{ ...CARD, padding: 8, display: 'flex', alignItems: 'flex-end', gap: 8, marginTop: 14 }}>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
              placeholder="Perintahkan AI mengelola porto…"
              rows={1}
              className="aip-textarea"
              style={{ flex: 1, resize: 'none', border: 'none', outline: 'none', background: 'transparent', fontFamily: SANS, fontSize: 14, color: INK, padding: '9px 10px', maxHeight: 120 }}
            />
            <button
              onClick={() => send(input)}
              disabled={loading || !input.trim()}
              style={{ flex: 'none', background: ACCENT, color: '#fff', fontWeight: 700, fontSize: 13.5, padding: '10px 18px', borderRadius: 11, border: 'none', cursor: 'pointer', opacity: loading || !input.trim() ? 0.5 : 1 }}
            >
              Kirim
            </button>
          </div>
          <p style={{ fontSize: 11, color: FAINT, marginTop: 8, textAlign: 'center' }}>
            AI langsung mengeksekusi trade (uang dummy). Tak ada konfirmasi.
          </p>
        </div>

        {/* Portfolio panel */}
        <aside style={{ ...CARD, padding: 18, position: 'sticky', top: 84 }} className="aip-panel">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <h2 style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, letterSpacing: '.14em', textTransform: 'uppercase', color: FAINT }}>Porto AI</h2>
            {regime && REGIME[regime] && (
              <span title="Rezim risiko adaptif" style={{ fontSize: 10.5, fontWeight: 800, textTransform: 'uppercase', letterSpacing: '.05em', color: REGIME[regime].color, background: `color-mix(in oklab, ${REGIME[regime].color}, white 86%)`, border: `1px solid color-mix(in oklab, ${REGIME[regime].color}, white 72%)`, padding: '3px 9px', borderRadius: 999 }}>
                {REGIME[regime].label}
              </span>
            )}
          </div>
          <div style={{ marginTop: 10 }}>
            <div style={{ fontFamily: MONO, fontSize: 24, fontWeight: 700 }}>{rp(snapshot?.total_value)}</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: pnl >= 0 ? UP : DOWN, marginTop: 2 }}>
              {pnl >= 0 ? '▲' : '▼'} {rp(Math.abs(pnl))} ({pnlPct.toFixed(2)}%)
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 14 }}>
            <Stat label="Kas" value={rp(snapshot?.cash)} />
            <Stat label="Diinvestasikan" value={rp(snapshot?.invested)} />
            <Stat label="Unrealized" value={rp(snapshot?.unrealized)} color={(snapshot?.unrealized ?? 0) >= 0 ? UP : DOWN} />
            <Stat label="Realized" value={rp(snapshot?.realized)} color={(snapshot?.realized ?? 0) >= 0 ? UP : DOWN} />
          </div>

          <h3 style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT, marginTop: 18, marginBottom: 8 }}>
            Holdings ({snapshot?.position_count ?? 0})
          </h3>
          {snapshot && snapshot.holdings.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {snapshot.holdings.map(h => (
                <div key={h.ticker} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13.5 }}>{h.ticker}</div>
                    <div style={{ fontSize: 11, color: MUTED }}>{h.lots} lot @ {rp(h.avg_price)}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontFamily: MONO, fontSize: 12.5 }}>{rp(h.current_price)}</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: h.unrealized_pnl >= 0 ? UP : DOWN }}>
                      {h.unrealized_pct == null ? '—' : `${h.unrealized_pct >= 0 ? '+' : ''}${h.unrealized_pct.toFixed(2)}%`}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 12.5, color: FAINT }}>Belum ada posisi. Perintahkan AI untuk mulai.</p>
          )}

          <button
            onClick={() => setHistOpen(o => !o)}
            aria-expanded={histOpen}
            style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, background: 'transparent', border: 'none', cursor: 'pointer', padding: 0, marginTop: 18, marginBottom: histOpen ? 8 : 0 }}
          >
            <h3 style={{ fontFamily: MONO, fontSize: 10.5, fontWeight: 700, letterSpacing: '.12em', textTransform: 'uppercase', color: FAINT }}>
              Histori Jual/Beli{history.length > 0 ? ` (${history.length})` : ''}
            </h3>
            <span style={{ fontSize: 11, color: FAINT, transform: histOpen ? 'rotate(90deg)' : 'none', transition: 'transform .15s ease' }}>▸</span>
          </button>
          {histOpen && (
            history.length > 0 ? (
              <div className="aip-scroll" style={{ display: 'flex', flexDirection: 'column', maxHeight: 320, overflowY: 'auto', margin: '0 -4px', paddingRight: 4 }}>
                {history.map(t => <HistoryRow key={t.id} t={t} />)}
              </div>
            ) : (
              <p style={{ fontSize: 12.5, color: FAINT }}>Belum ada transaksi.</p>
            )
          )}
        </aside>
      </div>

      <style jsx global>{`
        .aip-scroll::-webkit-scrollbar { width: 6px; }
        .aip-scroll::-webkit-scrollbar-thumb { background: #E2E1DB; border-radius: 10px; }
        .aip-textarea::placeholder { color: #A9A9A1; }
        @keyframes aipblink { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }
        @media (max-width: 860px) {
          .aip-grid { grid-template-columns: minmax(0,1fr) !important; }
          .aip-panel { position: static !important; order: -1; }
        }
      `}</style>
    </main>
  );
}

function HistoryRow({ t }: { t: TradeHistory }) {
  const col = t.action === 'BUY' ? UP : DOWN;
  const dateLabel = (() => {
    const d = new Date(t.date);
    return isNaN(d.getTime()) ? t.date : d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
  })();
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8, padding: '9px 4px', borderTop: `1px solid #F2F1EC` }}>
      <div style={{ minWidth: 0 }}>
        <div className="flex items-center gap-2">
          <span style={{ fontFamily: MONO, fontSize: 9.5, fontWeight: 700, color: col, background: `color-mix(in oklab, ${col}, white 86%)`, padding: '1px 6px', borderRadius: 999 }}>{t.action === 'BUY' ? 'BELI' : 'JUAL'}</span>
          <span style={{ fontWeight: 700, fontSize: 13 }}>{t.ticker}</span>
          <span style={{ fontSize: 11, color: MUTED }}>{t.quantity} lot</span>
        </div>
        <div style={{ fontSize: 11, color: FAINT, marginTop: 2 }}>{dateLabel} · @ {rp(t.price)}</div>
      </div>
      <div style={{ textAlign: 'right', flex: 'none' }}>
        <div style={{ fontFamily: MONO, fontSize: 11.5, color: INK }}>{rp(t.total_value)}</div>
        {t.pnl != null && (
          <div style={{ fontSize: 11, fontWeight: 700, color: t.pnl >= 0 ? UP : DOWN, marginTop: 2 }}>
            {t.pnl >= 0 ? '+' : ''}{rp(t.pnl)}{t.pnl_pct != null ? ` (${t.pnl_pct >= 0 ? '+' : ''}${t.pnl_pct.toFixed(1)}%)` : ''}
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: '#FBFBF9', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '8px 10px' }}>
      <p style={{ fontSize: 9.5, color: FAINT, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 3 }}>{label}</p>
      <p style={{ fontFamily: MONO, fontSize: 12.5, fontWeight: 700, color: color ?? INK }}>{value}</p>
    </div>
  );
}

function Dot({ d = 0 }: { d?: number }) {
  return <span style={{ width: 7, height: 7, borderRadius: '50%', background: ACCENT, display: 'inline-block', animation: `aipblink 1.2s ${d}s infinite ease-in-out` }} />;
}

function Bubble({ msg }: { msg: Msg }) {
  if (msg.role === 'user') {
    return (
      <div style={{ alignSelf: 'flex-end', maxWidth: '85%', background: `color-mix(in oklab, ${ACCENT}, white 88%)`, border: `1px solid color-mix(in oklab, ${ACCENT}, white 78%)`, color: INK, padding: '10px 14px', borderRadius: 14, borderBottomRightRadius: 4, fontSize: 14, lineHeight: 1.5 }}>
        {msg.content}
      </div>
    );
  }
  const resp = msg.resp;
  return (
    <div style={{ alignSelf: 'flex-start', maxWidth: '92%', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ ...CARD, padding: '12px 16px', fontSize: 14, lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
        {renderText(msg.content)}
      </div>
      {resp && ((resp.auto_exits?.length ?? 0) > 0 || resp.executed.length > 0 || resp.skipped.length > 0) && (
        <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
          {(resp.auto_exits ?? []).map((o, i) => (
            <Row key={'a' + i} o={o} ok tag="auto" />
          ))}
          {resp.executed.map((o, i) => (
            <Row key={'e' + i} o={o} ok />
          ))}
          {resp.skipped.map((o, i) => (
            <Row key={'s' + i} o={o} />
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ o, ok, tag }: { o: { ticker: string; action: string; lots: number; price?: number; reason: string }; ok?: boolean; tag?: 'auto' }) {
  const col = o.action === 'BUY' ? UP : DOWN;
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, padding: '10px 14px', borderTop: `1px solid #F2F1EC`, opacity: ok ? 1 : 0.6 }}>
      <div style={{ minWidth: 0 }}>
        <div className="flex items-center gap-2">
          <span style={{ fontWeight: 700, fontSize: 13.5 }}>{o.ticker}</span>
          <span style={{ fontFamily: MONO, fontSize: 10, fontWeight: 700, color: col, background: `color-mix(in oklab, ${col}, white 86%)`, padding: '1px 7px', borderRadius: 999 }}>{o.action} {o.lots}</span>
          {tag === 'auto' && <span style={{ fontSize: 10, fontWeight: 800, color: AMBER, textTransform: 'uppercase', letterSpacing: '.04em' }}>auto</span>}
          {!ok && <span style={{ fontSize: 10.5, color: DOWN, fontWeight: 700 }}>dilewati</span>}
        </div>
        {o.reason && <p style={{ fontSize: 11.5, color: MUTED, marginTop: 3 }}>{o.reason}</p>}
      </div>
      {ok && o.price != null && <span style={{ flex: 'none', fontFamily: MONO, fontSize: 11.5, color: INK }}>{rp(o.price)}</span>}
    </div>
  );
}

function renderText(t: string): React.ReactNode {
  const parts = t.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>
  );
}
