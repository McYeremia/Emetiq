'use client';

import { useEffect, useState } from 'react';
import EmetiqNav from '@/components/EmetiqNav';
import RequireAuth from '@/components/RequireAuth';
import { useAuth } from '@/components/AuthProvider';
import { api, AdminUser } from '@/lib/api';

// ── EMETIQ theme tokens ────────────────────────────────────────
const ACCENT = '#F26A1B';
const BG = '#FCFCFB';
const INK = '#14140F';
const MUTED = '#56564F';
const FAINT = '#9A9A92';
const HAIR = '#ECEBE6';
const UP = '#138A50';
const DOWN = '#D23B3B';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

const CARD: React.CSSProperties = {
  background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 16,
  boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)',
};

const TIERS = ['free', 'basic', 'pro', 'premium', 'dev'] as const;

export default function AdminPage() {
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
  return <AdminInner />;
}

function NotDev() {
  useEffect(() => { document.title = 'Admin — EMETIQ'; }, []);
  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS }}>
      <EmetiqNav />
      <div style={{ maxWidth: 520, margin: '0 auto', padding: '80px 20px', textAlign: 'center' }}>
        <div style={{ ...CARD, padding: 32 }}>
          <h1 style={{ fontSize: 22, fontWeight: 800 }}>Khusus tier developer</h1>
          <p style={{ marginTop: 10, fontSize: 14.5, color: MUTED, lineHeight: 1.6 }}>
            Halaman <strong>Admin</strong> hanya tersedia untuk akun bertier <code>dev</code>.
          </p>
        </div>
      </div>
    </main>
  );
}

function AdminInner() {
  useEffect(() => { document.title = 'Admin — EMETIQ'; }, []);
  const { user } = useAuth();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ ok: boolean; msg: string } | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true); setError(null);
      try {
        const data = await api.getUsers();
        if (alive) setUsers(data);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : 'Gagal memuat data.');
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => { alive = false; };
  }, []);

  const showToast = (ok: boolean, msg: string) => {
    setToast({ ok, msg });
    setTimeout(() => setToast(null), 3200);
  };

  const changeTier = async (u: AdminUser, tier: string) => {
    if (tier === u.tier) return;
    const prev = u.tier;
    setSavingId(u.id);
    setUsers(list => list.map(x => (x.id === u.id ? { ...x, tier } : x)));  // optimistic
    try {
      await api.updateUserTier(u.id, tier);
      showToast(true, `Tier ${u.email ?? u.id} → ${tier}`);
    } catch (e) {
      setUsers(list => list.map(x => (x.id === u.id ? { ...x, tier: prev } : x)));  // rollback
      showToast(false, e instanceof Error ? e.message : 'Gagal mengubah tier.');
    } finally {
      setSavingId(null);
    }
  };

  const fmtDate = (iso: string | null) => {
    if (!iso) return '—';
    try {
      return new Date(iso).toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch { return '—'; }
  };

  return (
    <main style={{ minHeight: '100vh', background: BG, color: INK, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      <EmetiqNav />

      <div style={{ maxWidth: 940, margin: '0 auto', padding: '28px 24px 80px' }}>
        <div className="mb-6">
          <h1 style={{ fontSize: 30, fontWeight: 800, letterSpacing: '-.02em' }}>Admin · Kelola Tier</h1>
          <p style={{ marginTop: 4, fontSize: 14.5, color: MUTED }}>
            Daftar user terdaftar. Ubah tier lewat dropdown. Tier akunmu sendiri tidak bisa diubah dari sini.
          </p>
        </div>

        {error && (
          <div style={{ ...CARD, padding: 20, marginBottom: 24, borderColor: '#F3C7C7', background: '#FBE9E9' }}>
            <p style={{ color: DOWN, fontWeight: 700, fontSize: 14 }}>Gagal memuat data ({error})</p>
          </div>
        )}

        <div style={{ ...CARD, padding: 0, overflow: 'hidden' }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', minWidth: 560, borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${HAIR}`, background: '#FBFBF9' }}>
                  <th style={TH}>Email</th>
                  <th style={TH}>Tier</th>
                  <th style={THR}>Daftar</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr><td colSpan={3} style={{ padding: '56px 18px', textAlign: 'center', color: FAINT, fontSize: 13, fontFamily: MONO }} className="animate-pulse">Memuat…</td></tr>
                ) : users.length === 0 ? (
                  <tr><td colSpan={3} style={{ padding: '56px 18px', textAlign: 'center', color: FAINT, fontSize: 13 }}>Belum ada user terdaftar.</td></tr>
                ) : (
                  users.map((u, i) => {
                    const isSelf = u.id === user?.id;
                    return (
                      <tr key={u.id} style={{ borderBottom: i < users.length - 1 ? '1px solid #F2F1EC' : 'none' }}>
                        <td style={TD}>
                          <span style={{ fontWeight: 600, fontSize: 14 }}>{u.email ?? '—'}</span>
                          {isSelf && <span style={{ marginLeft: 8, fontSize: 11, fontFamily: MONO, color: ACCENT, fontWeight: 700 }}>(kamu)</span>}
                          <div style={{ fontFamily: MONO, fontSize: 11, color: FAINT, marginTop: 3, wordBreak: 'break-all' }}>{u.id}</div>
                        </td>
                        <td style={TD}>
                          <select
                            value={u.tier}
                            disabled={isSelf || savingId === u.id}
                            onChange={e => changeTier(u, e.target.value)}
                            style={{
                              fontFamily: MONO, fontSize: 12.5, fontWeight: 700, textTransform: 'uppercase',
                              letterSpacing: '.03em', color: isSelf ? FAINT : INK,
                              background: isSelf ? '#F5F5F1' : '#fff', border: `1px solid ${HAIR}`,
                              borderRadius: 9, padding: '7px 10px', cursor: isSelf ? 'not-allowed' : 'pointer',
                            }}
                          >
                            {TIERS.map(t => <option key={t} value={t}>{t}</option>)}
                          </select>
                        </td>
                        <td style={{ ...TDR, color: MUTED, fontSize: 12.5 }}>{fmtDate(u.created_at)}</td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)', zIndex: 100,
          background: toast.ok ? '#0E2E1E' : '#3A1414', color: '#fff', fontSize: 13.5, fontWeight: 600,
          padding: '11px 18px', borderRadius: 12, boxShadow: '0 12px 32px -10px rgba(0,0,0,.4)',
          borderLeft: `3px solid ${toast.ok ? UP : DOWN}`, maxWidth: '90vw',
        }}>
          {toast.msg}
        </div>
      )}
    </main>
  );
}

const TH: React.CSSProperties = { padding: '13px 18px', textAlign: 'left', fontFamily: MONO, fontSize: 10.5, letterSpacing: '.06em', textTransform: 'uppercase', color: FAINT, fontWeight: 600, whiteSpace: 'nowrap' };
const THR: React.CSSProperties = { ...TH, textAlign: 'right' };
const TD: React.CSSProperties = { padding: '14px 18px', fontSize: 13, verticalAlign: 'middle' };
const TDR: React.CSSProperties = { ...TD, textAlign: 'right', fontFamily: MONO };
