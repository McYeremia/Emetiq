'use client';

import Link from 'next/link';
import { useState } from 'react';

// Shared EMETIQ light-theme top nav for migrated app pages (Overview, Market, ...).
const ACCENT = '#F26A1B';
const INK = '#14140F';
const HAIR = '#ECEBE6';

const ITEMS = [
  { key: 'overview', label: 'Overview', href: '/overview' },
  { key: 'market', label: 'Market', href: '/dashboard' },
  { key: 'screener', label: 'Screener', href: '/screener' },
  { key: 'portfolio', label: 'Portofolio', href: '/portfolio' },
] as const;

export type NavKey = typeof ITEMS[number]['key'];

export default function EmetiqNav({ active }: { active: NavKey }) {
  const [open, setOpen] = useState(false);

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
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Routing to the AI trading page is wired up later */}
          <button
            type="button"
            className="emx-btn hidden md:inline-flex"
            style={{ color: '#fff', background: ACCENT, fontWeight: 700, fontSize: 14, padding: '9px 16px', borderRadius: 11, border: 'none', cursor: 'pointer', boxShadow: `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 64%)` }}
          >
            Trade with AI
          </button>

          {/* Mobile hamburger */}
          <button
            type="button"
            aria-label="Menu"
            aria-expanded={open}
            onClick={() => setOpen(o => !o)}
            className="md:hidden"
            style={{ width: 40, height: 40, borderRadius: 10, border: `1px solid ${HAIR}`, background: '#fff', cursor: 'pointer', display: 'inline-flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4 }}
          >
            <span style={{ width: 17, height: 2, borderRadius: 2, background: INK, transition: 'transform .2s ease', transform: open ? 'translateY(6px) rotate(45deg)' : 'none' }} />
            <span style={{ width: 17, height: 2, borderRadius: 2, background: INK, opacity: open ? 0 : 1, transition: 'opacity .15s ease' }} />
            <span style={{ width: 17, height: 2, borderRadius: 2, background: INK, transition: 'transform .2s ease', transform: open ? 'translateY(-6px) rotate(-45deg)' : 'none' }} />
          </button>
        </div>
      </nav>

      {/* Mobile menu panel */}
      {open && (
        <div className="md:hidden" style={{ borderTop: `1px solid ${HAIR}`, background: '#fff', padding: '10px 16px 16px', display: 'flex', flexDirection: 'column', gap: 4 }}>
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
          <button
            type="button"
            onClick={() => setOpen(false)}
            style={{ marginTop: 6, color: '#fff', background: ACCENT, fontWeight: 700, fontSize: 14.5, padding: '12px 16px', borderRadius: 12, border: 'none', cursor: 'pointer' }}
          >
            Trade with AI
          </button>
        </div>
      )}
    </header>
  );
}
