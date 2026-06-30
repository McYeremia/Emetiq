'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import EmetiqNav from '@/components/EmetiqNav';
import { api, AdvisorResponse, AdvisorQuota } from '@/lib/api';

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
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 16,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

type Msg = { role: 'user' | 'assistant'; content: string; resp?: AdvisorResponse };

const STORE_KEY = 'emetiq-advisor-chat';
const QUOTA_KEY = 'emetiq-advisor-quota';

const WELCOME: Msg = {
  role: 'assistant',
  content: 'Halo! Saya asisten saham IDX. Saya bisa bantu **cari saham** sesuai kriteria, **analisa satu saham**, atau memberi **saran portofolio**. Mau mulai dari mana?',
};

const QUICK = [
  { label: 'Cari saham', prompt: 'Cari saham dengan PE di bawah 15 dan dividen di atas 3%' },
  { label: 'Analisa saham', prompt: 'Gimana BBRI sekarang?' },
  { label: 'Saran portofolio', prompt: 'Tolong evaluasi portofolio saya' },
];

function decisionColor(d: string) {
  if (d === 'BELI') return UP;
  if (d === 'JUAL') return DOWN;
  return AMBER;
}
function actionColor(a: string) {
  if (a === 'ADD') return UP;
  if (a === 'TRIM') return DOWN;
  return MUTED;
}

export default function AdvisorPage() {
  useEffect(() => { document.title = 'AI Advisor — EMETIQ'; }, []);
  const [messages, setMessages] = useState<Msg[]>([WELCOME]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [quota, setQuota] = useState<AdvisorQuota | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Persist chat across navigation within the tab session (survives leaving to a
  // stock page and coming back; cleared only when the tab is closed or reset).
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(STORE_KEY);
      if (saved) {
        const p = JSON.parse(saved);
        if (Array.isArray(p) && p.length) setMessages(p);
      }
      const q = sessionStorage.getItem(QUOTA_KEY);
      if (q) setQuota(JSON.parse(q));
    } catch {}
  }, []);

  const persist = (msgs: Msg[]) => {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(msgs)); } catch {}
  };

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, loading]);

  const resetChat = () => {
    setMessages([WELCOME]);
    persist([WELCOME]);
  };

  const send = async (text: string) => {
    const message = text.trim();
    if (!message || loading) return;
    const next: Msg[] = [...messages, { role: 'user', content: message }];
    setMessages(next);
    persist(next);
    setInput('');
    setLoading(true);

    const history = next
      .filter(m => m !== WELCOME)
      .slice(-8)
      .map(m => ({ role: m.role, content: m.content }));

    try {
      const resp = await api.advisorChat({ message, history });
      const withReply: Msg[] = [...next, { role: 'assistant', content: resp.reply, resp }];
      setMessages(withReply);
      persist(withReply);
      if (resp.quota) {
        setQuota(resp.quota);
        try { sessionStorage.setItem(QUOTA_KEY, JSON.stringify(resp.quota)); } catch {}
      }
    } catch {
      const withErr: Msg[] = [...next, { role: 'assistant', content: 'Gagal menghubungi advisor. Periksa koneksi backend.' }];
      setMessages(withErr);
      persist(withErr);
    } finally {
      setLoading(false);
    }
  };

  const quotaLabel = quota
    ? quota.limit == null
      ? 'Tak terbatas'
      : `${quota.remaining ?? 0}/${quota.limit} hari ini`
    : null;

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav active="advisor" />

      <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 18px 28px', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)' }}>
        {/* Header */}
        <div className="flex items-end justify-between gap-4 mb-4">
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, letterSpacing: '-.02em' }}>AI Advisor</h1>
            <p style={{ marginTop: 3, fontSize: 13.5, color: MUTED }}>Screening, analisa saham, & saran portofolio dalam bahasa natural.</p>
          </div>
          <div className="flex items-center gap-2" style={{ flex: 'none' }}>
            {quotaLabel && (
              <span style={{ fontFamily: MONO, fontSize: 11, fontWeight: 600, color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 88%)`, border: `1px solid color-mix(in oklab, ${ACCENT}, white 76%)`, padding: '5px 10px', borderRadius: 999 }}>
                {quotaLabel}
              </span>
            )}
            {messages.length > 1 && (
              <button
                onClick={resetChat}
                title="Mulai percakapan baru"
                className="emx-chip"
                style={{ fontSize: 11.5, fontWeight: 600, color: MUTED, background: '#fff', border: `1px solid ${HAIR}`, padding: '5px 11px', borderRadius: 999, cursor: 'pointer' }}
              >
                Mulai baru
              </button>
            )}
          </div>
        </div>

        {/* Messages */}
        <div ref={scrollRef} className="emx-scroll" style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 14, paddingRight: 4 }}>
          {messages.map((m, i) => (
            <MessageBubble key={i} msg={m} />
          ))}
          {loading && (
            <div style={{ alignSelf: 'flex-start', ...CARD, padding: '12px 16px', display: 'flex', gap: 6, alignItems: 'center' }}>
              <Dot /> <Dot d={0.15} /> <Dot d={0.3} />
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="flex gap-2 flex-wrap mt-4 mb-2">
          {QUICK.map(q => (
            <button
              key={q.label}
              onClick={() => send(q.prompt)}
              disabled={loading}
              className="emx-chip"
              style={{ fontSize: 12.5, fontWeight: 600, color: MUTED, background: '#fff', border: `1px solid ${HAIR}`, padding: '7px 13px', borderRadius: 999, cursor: 'pointer' }}
            >
              {q.label}
            </button>
          ))}
        </div>

        {/* Input */}
        <div style={{ ...CARD, padding: 8, display: 'flex', alignItems: 'flex-end', gap: 8 }}>
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(input); } }}
            placeholder="Tanya apa saja — mis. cari saham PE<15 dividen>3%, atau analisa BBRI…"
            rows={1}
            className="emx-textarea"
            style={{ flex: 1, resize: 'none', border: 'none', outline: 'none', background: 'transparent', fontFamily: SANS, fontSize: 14, color: INK, padding: '9px 10px', maxHeight: 120 }}
          />
          <button
            onClick={() => send(input)}
            disabled={loading || !input.trim()}
            className="emx-send"
            style={{ flex: 'none', background: ACCENT, color: '#fff', fontWeight: 700, fontSize: 13.5, padding: '10px 18px', borderRadius: 11, border: 'none', cursor: 'pointer', opacity: loading || !input.trim() ? 0.5 : 1 }}
          >
            Kirim
          </button>
        </div>
        <p style={{ fontSize: 11, color: FAINT, marginTop: 8, textAlign: 'center', lineHeight: 1.5 }}>
          Saran AI berdasar data historis & probabilitas — <strong>bukan</strong> rekomendasi finansial. Keputusan & risiko ada di tanganmu.
        </p>
      </div>

      <style jsx global>{`
        .emx-scroll::-webkit-scrollbar { width: 6px; }
        .emx-scroll::-webkit-scrollbar-thumb { background: #E2E1DB; border-radius: 10px; }
        .emx-chip { transition: all .14s ease; }
        .emx-chip:hover { border-color: ${ACCENT}; color: ${ACCENT}; }
        .emx-send { transition: transform .15s ease, filter .15s ease; }
        .emx-send:hover { filter: brightness(1.03); }
        .emx-textarea::placeholder { color: #A9A9A1; }
        ::selection { background: color-mix(in oklab, ${ACCENT}, white 70%); }
        @keyframes emxblink { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }
      `}</style>
    </main>
  );
}

function Dot({ d = 0 }: { d?: number }) {
  return <span style={{ width: 7, height: 7, borderRadius: '50%', background: ACCENT, display: 'inline-block', animation: `emxblink 1.2s ${d}s infinite ease-in-out` }} />;
}

function MessageBubble({ msg }: { msg: Msg }) {
  if (msg.role === 'user') {
    return (
      <div style={{ alignSelf: 'flex-end', maxWidth: '85%', background: `color-mix(in oklab, ${ACCENT}, white 88%)`, border: `1px solid color-mix(in oklab, ${ACCENT}, white 78%)`, color: INK, padding: '10px 14px', borderRadius: 14, borderBottomRightRadius: 4, fontSize: 14, lineHeight: 1.5 }}>
        {msg.content}
      </div>
    );
  }
  const intent = msg.resp?.intent;
  const isErr = intent === 'error';
  return (
    <div style={{ alignSelf: 'flex-start', maxWidth: '92%', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ ...CARD, padding: '12px 16px', borderColor: isErr ? '#F2C9C9' : HAIR, background: isErr ? '#FBE9E9' : '#fff', fontSize: 14, lineHeight: 1.6, color: isErr ? DOWN : INK, whiteSpace: 'pre-wrap' }}>
        {renderText(msg.content)}
      </div>
      {msg.resp?.data && <StructuredData intent={intent} data={msg.resp.data} confidence={msg.resp.confidence} />}
    </div>
  );
}

// minimal **bold** support
function renderText(t: string): React.ReactNode {
  const parts = t.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**')
      ? <strong key={i}>{p.slice(2, -2)}</strong>
      : <span key={i}>{p}</span>
  );
}

function StructuredData({ intent, data, confidence }: { intent?: string; data: any; confidence: number | null }) {
  if (intent === 'screen' && Array.isArray(data?.candidates) && data.candidates.length > 0) {
    return (
      <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
        {data.candidates.slice(0, 8).map((c: any, i: number) => (
          <Link key={c.ticker} href={`/stocks/${c.ticker}`} className="emx-row" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '12px 16px', textDecoration: 'none', color: INK, borderBottom: i < Math.min(8, data.candidates.length) - 1 ? '1px solid #F2F1EC' : 'none' }}>
            <div style={{ minWidth: 0 }}>
              <div className="flex items-center gap-2">
                <span style={{ fontWeight: 700, fontSize: 14 }}>{c.ticker}</span>
                {typeof c.score === 'number' && <span style={{ fontFamily: MONO, fontSize: 10, fontWeight: 700, color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 88%)`, padding: '1px 7px', borderRadius: 999 }}>{Math.round(c.score)}</span>}
              </div>
              {c.reason && <p style={{ fontSize: 12, color: MUTED, marginTop: 3 }} className="line-clamp-2">{c.reason}</p>}
            </div>
            <span style={{ flex: 'none', fontFamily: MONO, fontSize: 11, color: ACCENT, fontWeight: 700 }}>Analisa ›</span>
          </Link>
        ))}
      </div>
    );
  }

  if (intent === 'analyze' && data?.ticker && data?.decision) {
    const col = decisionColor(data.decision);
    return (
      <div style={{ ...CARD, padding: 16 }}>
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2.5">
            <span style={{ fontWeight: 800, fontSize: 17 }}>{data.ticker}</span>
            <span style={{ fontSize: 12, fontWeight: 800, color: col, background: `color-mix(in oklab, ${col}, white 86%)`, border: `1px solid color-mix(in oklab, ${col}, white 74%)`, padding: '3px 10px', borderRadius: 999 }}>{data.decision}</span>
          </div>
          <Link href={`/stocks/${data.ticker}`} style={{ fontFamily: MONO, fontSize: 11, fontWeight: 700, color: ACCENT, textDecoration: 'none' }}>Buka chart ›</Link>
        </div>
        <div className="grid grid-cols-3 gap-2" style={{ marginBottom: data.confidence != null ? 12 : 0 }}>
          <Metric label="Entry" value={data.entry} />
          <Metric label="Take Profit" value={data.take_profit} color={UP} />
          <Metric label="Cut Loss" value={data.cut_loss} color={DOWN} />
        </div>
        {typeof data.confidence === 'number' && (
          <div>
            <div className="flex justify-between" style={{ marginBottom: 5 }}>
              <span style={{ fontSize: 10.5, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.08em', color: FAINT }}>Confidence</span>
              <span style={{ fontFamily: MONO, fontSize: 12, fontWeight: 700 }}>{Math.round(data.confidence * 100)}%</span>
            </div>
            <div style={{ width: '100%', background: '#F2F1EC', borderRadius: 999, height: 6 }}>
              <div style={{ height: 6, borderRadius: 999, width: `${Math.round(data.confidence * 100)}%`, background: col }} />
            </div>
          </div>
        )}
        {Array.isArray(data.warnings) && data.warnings.length > 0 && (
          <p style={{ fontSize: 11.5, color: AMBER, marginTop: 12 }}>⚠ {data.warnings.join(' · ')}</p>
        )}
      </div>
    );
  }

  if (intent === 'portfolio' && Array.isArray(data?.actions) && data.actions.length > 0) {
    return (
      <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
        {data.actions.map((a: any, i: number) => {
          const col = actionColor(a.action);
          return (
            <div key={a.ticker + i} style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, padding: '12px 16px', borderBottom: i < data.actions.length - 1 ? '1px solid #F2F1EC' : 'none' }}>
              <div style={{ minWidth: 0 }}>
                <div className="flex items-center gap-2">
                  <span style={{ fontWeight: 700, fontSize: 14 }}>{a.ticker}</span>
                  <span style={{ fontFamily: MONO, fontSize: 10, fontWeight: 700, color: col, background: `color-mix(in oklab, ${col}, white 86%)`, padding: '1px 8px', borderRadius: 999 }}>{a.action}</span>
                </div>
                {a.reason && <p style={{ fontSize: 12, color: MUTED, marginTop: 3 }}>{a.reason}</p>}
              </div>
              <Link href={`/stocks/${a.ticker}`} style={{ flex: 'none', fontFamily: MONO, fontSize: 11, color: ACCENT, fontWeight: 700, textDecoration: 'none' }}>›</Link>
            </div>
          );
        })}
      </div>
    );
  }

  return null;
}

function Metric({ label, value, color }: { label: string; value: number | null; color?: string }) {
  return (
    <div style={{ background: '#FBFBF9', border: `1px solid ${HAIR}`, borderRadius: 10, padding: '8px 10px' }}>
      <p style={{ fontSize: 9.5, color: FAINT, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: 3 }}>{label}</p>
      <p style={{ fontFamily: MONO, fontSize: 13, fontWeight: 700, color: value != null ? (color ?? INK) : FAINT }}>
        {value != null ? value.toLocaleString('id-ID') : '—'}
      </p>
    </div>
  );
}
