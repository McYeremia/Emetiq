'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useAuth } from './AuthProvider';

// Shared EMETIQ light-theme top nav for migrated app pages (Overview, Market, ...).
const ACCENT = '#F26A1B';
const INK = '#14140F';
const HAIR = '#ECEBE6';
const MUTED = '#55554E';

const tierBadge: React.CSSProperties = {
  fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.04em',
  color: ACCENT, background: `color-mix(in oklab, ${ACCENT}, white 86%)`,
  padding: '3px 9px', borderRadius: 999,
};
const ghostBtn: React.CSSProperties = {
  textDecoration: 'none', color: INK, background: '#fff', border: `1px solid ${HAIR}`,
  fontWeight: 600, fontSize: 13.5, padding: '8px 13px', borderRadius: 10, cursor: 'pointer',
};

const ITEMS = [
  { key: 'overview', label: 'Overview', href: '/overview' },
  { key: 'market', label: 'Market', href: '/dashboard' },
  { key: 'screener', label: 'Screener', href: '/screener' },
  { key: 'portfolio', label: 'Portofolio', href: '/portfolio' },
] as const;

export type NavKey = typeof ITEMS[number]['key'];

export default function EmetiqNav({ active }: { active?: NavKey | 'advisor' | 'ai-porto' }) {
  const [open, setOpen] = useState(false);
  const { user, tier, loading, signOut } = useAuth();
  const router = useRouter();

  const handleLogout = async () => {
    setOpen(false);
    await signOut();
    router.push('/');
  };

  const navItem = (isActive: boolean): React.CSSProperties => ({
    textDecoration: 'none',
    color: isActive ? ACCENT : '#55554E',
    fontWeight: isActive ? 700 : 500,
    background: isActive ? `color-mix(in oklab, ${ACCENT}, white 88%)` : 'transparent',
    padding: '8px 14px',
    borderRadius: 999,
    fontSize: 14.5,
    transition: 'color .15s ease, background .15s ease',
  });

  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        background: 'rgba(252,252,251,.92)',
        backdropFilter: 'saturate(140%) blur(12px)',
        borderBottom: `1px solid ${HAIR}`,
      }}
    >
      <nav style={{ maxWidth: 1200, margin: '0 auto', height: 64, padding: '0 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <Link href="/" style={{ textDecoration: 'none', color: 'inherit', fontWeight: 800, fontSize: 19, letterSpacing: '.06em' }}>
          EMETIQ
        </Link>

        {/* Desktop links */}
        <div className="hidden md:flex" style={{ alignItems: 'center', gap: 6 }}>
          {ITEMS.map(it => (
            <Link key={it.key} href={it.href} style={navItem(active === it.key)}>{it.label}</Link>
          ))}
          {tier === 'dev' && (
            <Link href="/ai-porto" style={navItem(active === 'ai-porto')}>AI Porto</Link>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Link
            href="/advisor"
            className="emx-btn hidden md:inline-flex"
            style={{ alignItems: 'center', textDecoration: 'none', color: '#fff', background: ACCENT, fontWeight: 700, fontSize: 14, padding: '9px 16px', borderRadius: 11, border: 'none', cursor: 'pointer', boxShadow: `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 64%)` }}
          >
            Trade with AI
          </Link>

          {/* Account (desktop) */}
          {!loading && (user ? (
            <div className="hidden md:flex" style={{ alignItems: 'center', gap: 8 }}>
              {tier && <Link href="/profile" style={{ ...tierBadge, textDecoration: 'none' }} title="Profil">{tier}</Link>}
              <Link href="/profile" style={{ ...ghostBtn, display: 'inline-flex', alignItems: 'center' }}>Profil</Link>
              <button type="button" onClick={handleLogout} style={ghostBtn}>Keluar</button>
            </div>
          ) : (
            <Link href="/login" className="hidden md:inline-flex" style={{ ...ghostBtn, alignItems: 'center' }}>Masuk</Link>
          ))}

          {/* Mobile hamburger */}
          <button
            type="button"
            aria-label="Menu"
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
            className="md:hidden flex flex-col items-center justify-center"
            style={{ width: 40, height: 40, borderRadius: 10, border: `1px solid ${HAIR}`, background: '#fff', cursor: 'pointer', gap: 4 }}
          >
            <span style={{ width: 17, height: 2, borderRadius: 2, background: INK, transition: 'transform .2s ease', transform: open ? 'translateY(6px) rotate(45deg)' : 'none' }} />
            <span style={{ width: 17, height: 2, borderRadius: 2, background: INK, opacity: open ? 0 : 1, transition: 'opacity .15s ease' }} />
            <span style={{ width: 17, height: 2, borderRadius: 2, background: INK, transition: 'transform .2s ease', transform: open ? 'translateY(-6px) rotate(-45deg)' : 'none' }} />
          </button>
        </div>
      </nav>

      {/* Mobile menu panel */}
      {open && (
        <div className="md:hidden flex flex-col" style={{ borderTop: `1px solid ${HAIR}`, background: '#fff', padding: '10px 16px 16px', gap: 4 }}>
          {ITEMS.map(it => {
            const isActive = active === it.key;
            return (
              <Link
                key={it.key}
                href={it.href}
                onClick={() => setOpen(false)}
                style={{ padding: '11px 13px', borderRadius: 11, textDecoration: 'none', fontSize: 15, fontWeight: isActive ? 700 : 600, color: isActive ? ACCENT : INK, background: isActive ? `color-mix(in oklab, ${ACCENT}, white 88%)` : 'transparent' }}
              >
                {it.label}
              </Link>
            );
          })}
          {tier === 'dev' && (
            <Link
              href="/ai-porto"
              onClick={() => setOpen(false)}
              style={{ padding: '11px 13px', borderRadius: 11, textDecoration: 'none', fontSize: 15, fontWeight: active === 'ai-porto' ? 700 : 600, color: active === 'ai-porto' ? ACCENT : INK, background: active === 'ai-porto' ? `color-mix(in oklab, ${ACCENT}, white 88%)` : 'transparent' }}
            >
              AI Porto
            </Link>
          )}
          <Link
            href="/advisor"
            onClick={() => setOpen(false)}
            style={{ marginTop: 6, textAlign: 'center', textDecoration: 'none', color: '#fff', background: ACCENT, fontWeight: 700, fontSize: 14.5, padding: '12px 16px', borderRadius: 12, border: 'none', cursor: 'pointer' }}
          >
            Trade with AI
          </Link>

          {/* Account (mobile) */}
          {!loading && (
            <div style={{ marginTop: 8, paddingTop: 12, borderTop: `1px solid ${HAIR}`, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {user ? (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 13, color: MUTED, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.email}</span>
                    {tier && <span style={tierBadge}>{tier}</span>}
                  </div>
                  <Link href="/profile" onClick={() => setOpen(false)} style={{ ...ghostBtn, textAlign: 'center' }}>Profil</Link>
                  <button type="button" onClick={handleLogout} style={{ ...ghostBtn, textAlign: 'center' }}>Keluar</button>
                </>
              ) : (
                <div style={{ display: 'flex', gap: 8 }}>
                  <Link href="/login" onClick={() => setOpen(false)} style={{ ...ghostBtn, flex: 1, textAlign: 'center' }}>Masuk</Link>
                  <Link href="/register" onClick={() => setOpen(false)} style={{ flex: 1, textAlign: 'center', textDecoration: 'none', color: '#fff', background: ACCENT, fontWeight: 700, fontSize: 13.5, padding: '8px 13px', borderRadius: 10 }}>Daftar</Link>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </header>
  );
}
