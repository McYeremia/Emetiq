'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';

// ── Design tokens (from Landing.dc.html) ──────────────────────
const ACCENT = '#F26A1B';
const RADIUS = '11px';
const SANS = "'Plus Jakarta Sans', system-ui, sans-serif";
const MONO = "'IBM Plex Mono', monospace";

// ── Screener presets (ported from DCLogic.renderVals) ─────────
interface Preset {
  name: string;
  desc: string;
  match: number;
  tag: string;
}

const PRESETS: Preset[] = [
  { name: 'Golden Cross', desc: 'MA50 memotong MA200 ke atas — sinyal tren naik jangka menengah.', match: 8, tag: 'Teknikal' },
  { name: 'Foreign Inflow', desc: 'Net buy asing terbesar dalam 5 hari terakhir.', match: 14, tag: 'Flow' },
  { name: 'Undervalue PBV<1', desc: 'Harga di bawah nilai buku dengan ROE sehat.', match: 21, tag: 'Fundamental' },
  { name: 'Bandarmology', desc: 'Akumulasi bandar terdeteksi dari pola broker summary.', match: 6, tag: 'Flow' },
  { name: 'High Dividend', desc: 'Yield dividen di atas 6% dengan payout stabil.', match: 11, tag: 'Income' },
  { name: '52W High Breakout', desc: 'Tembus harga tertinggi 52 minggu dengan konfirmasi volume.', match: 9, tag: 'Teknikal' },
];

const WATCHLIST = [
  { ticker: 'BBCA', name: 'Bank Central Asia', price: '9.875', chg: '+1,28%', up: true },
  { ticker: 'GOTO', name: 'GoTo Gojek Tokopedia', price: '68', chg: '+3,03%', up: true },
  { ticker: 'TLKM', name: 'Telkom Indonesia', price: '2.890', chg: '-0,34%', up: false },
  { ticker: 'BMRI', name: 'Bank Mandiri', price: '6.025', chg: '+0,84%', up: true },
];

const BREAKOUT = [
  { ticker: 'PGAS', price: '1.640', chg: '+6,1%', vol: '3,8×' },
  { ticker: 'ADRO', price: '2.910', chg: '+4,7%', vol: '2,9×' },
  { ticker: 'INCO', price: '4.180', chg: '+3,2%', vol: '2,1×' },
];

const MUTED = '#56564F';
const HAIR = '#ECEBE6';

export default function LandingPage() {
  const [featureOpen, setFeatureOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState('home');

  useEffect(() => {
    document.title = 'EMETIQ — Monitoring Saham';
  }, []);

  // Smooth-scroll nav clicks, offsetting the 68px sticky header
  const handleNavClick = (e: React.MouseEvent, targetId: string, key: string) => {
    e.preventDefault();
    setActiveMenu(key);
    setFeatureOpen(false);
    const el = document.getElementById(targetId);
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY - 68;
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });
  };

  const menuItemStyle = (key: string): React.CSSProperties => ({
    textDecoration: 'none',
    color: activeMenu === key ? ACCENT : 'inherit',
    fontWeight: activeMenu === key ? 700 : 500,
    background: activeMenu === key ? `color-mix(in oklab, ${ACCENT}, white 88%)` : 'transparent',
    padding: '8px 14px',
    borderRadius: 999,
    transition: 'color .15s ease, background .15s ease',
    cursor: 'pointer',
  });

  const dropdownStyle: React.CSSProperties = {
    position: 'absolute',
    top: '100%',
    left: 0,
    paddingTop: '10px',
    zIndex: 60,
    opacity: featureOpen ? 1 : 0,
    visibility: featureOpen ? 'visible' : 'hidden',
    transform: featureOpen ? 'translateY(0)' : 'translateY(6px)',
    pointerEvents: featureOpen ? 'auto' : 'none',
    transition: 'opacity .16s ease, transform .16s ease',
  };

  const lockedPresets = PRESETS.slice(0, 3);
  const fadedPresets = PRESETS.slice(3);

  return (
    <div
      id="top"
      style={{
        minHeight: '100vh',
        background: '#FCFCFB',
        color: '#14140F',
        fontFamily: SANS,
        WebkitFontSmoothing: 'antialiased',
      }}
    >
      {/* Fonts — React 19 hoists these into <head> */}
      <link rel="preconnect" href="https://fonts.googleapis.com" />
      <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      <link
        href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap"
        rel="stylesheet"
      />

      {/* ── NAV ─────────────────────────────────────────────── */}
      <header
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          background: 'rgba(252,252,251,.82)',
          backdropFilter: 'saturate(140%) blur(12px)',
          borderBottom: `1px solid ${HAIR}`,
        }}
      >
        <nav
          style={{
            maxWidth: 1200,
            margin: '0 auto',
            height: 68,
            padding: '0 28px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 20,
          }}
        >
          <Link
            href="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              textDecoration: 'none',
              color: 'inherit',
              fontWeight: 800,
              fontSize: 20,
              letterSpacing: '.06em',
            }}
          >
            EMETIQ
          </Link>

          <div
            className="lp-navmenu"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 14.5,
              fontWeight: 500,
              color: '#55554E',
            }}
          >
            <a href="#top" style={menuItemStyle('home')} onClick={(e) => handleNavClick(e, 'top', 'home')}>
              Home
            </a>

            <div
              style={{ position: 'relative', display: 'flex', alignItems: 'center', height: 68 }}
              onMouseEnter={() => setFeatureOpen(true)}
              onMouseLeave={() => setFeatureOpen(false)}
            >
              <a
                href="#fitur"
                onClick={(e) => handleNavClick(e, 'fitur', 'feature')}
                style={{ ...menuItemStyle('feature'), display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
              >
                Feature
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRight: '1.6px solid #9A9A92',
                    borderBottom: '1.6px solid #9A9A92',
                    transform: 'rotate(45deg)',
                    marginTop: -2,
                  }}
                />
              </a>
              <div style={dropdownStyle}>
                <div
                  style={{
                    background: '#fff',
                    border: `1px solid ${HAIR}`,
                    borderRadius: 14,
                    boxShadow: '0 20px 44px -22px rgba(20,20,15,.32)',
                    padding: 7,
                    display: 'flex',
                    flexDirection: 'column',
                    minWidth: 222,
                  }}
                >
                  {/* Watchlist */}
                  <Link href="/dashboard" className="lp-menuitem">
                    <span
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: 9,
                        background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center',
                        gap: 3,
                        padding: '0 8px',
                        flex: 'none',
                      }}
                    >
                      <span style={{ height: 2.5, borderRadius: 2, background: ACCENT, width: '100%' }} />
                      <span style={{ height: 2.5, borderRadius: 2, background: ACCENT, width: '70%', opacity: 0.55 }} />
                      <span style={{ height: 2.5, borderRadius: 2, background: ACCENT, width: '85%', opacity: 0.4 }} />
                    </span>
                    <span style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>Watchlist</span>
                      <span style={{ fontSize: 11.5, color: '#9A9A92', fontWeight: 500 }}>Daftar saham pantauanmu</span>
                    </span>
                  </Link>

                  {/* Porto */}
                  <Link href="/portfolio" className="lp-menuitem">
                    <span
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: 9,
                        background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flex: 'none',
                      }}
                    >
                      <span
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: '50%',
                          background: `conic-gradient(${ACCENT} 0 62%, color-mix(in oklab, ${ACCENT}, white 60%) 62% 100%)`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: `color-mix(in oklab, ${ACCENT}, white 88%)` }} />
                      </span>
                    </span>
                    <span style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>Porto</span>
                      <span style={{ fontSize: 11.5, color: '#9A9A92', fontWeight: 500 }}>Posisi &amp; P&amp;L kamu</span>
                    </span>
                  </Link>

                  {/* Screener */}
                  <Link href="/screener" className="lp-menuitem">
                    <span
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: 9,
                        background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        position: 'relative',
                        flex: 'none',
                      }}
                    >
                      <span style={{ width: 13, height: 13, borderRadius: '50%', border: `2.5px solid ${ACCENT}` }} />
                      <span
                        style={{
                          position: 'absolute',
                          width: 6,
                          height: 2.5,
                          borderRadius: 2,
                          background: ACCENT,
                          transform: 'rotate(45deg)',
                          right: 7,
                          bottom: 7,
                        }}
                      />
                    </span>
                    <span style={{ display: 'flex', flexDirection: 'column' }}>
                      <span style={{ fontWeight: 700, fontSize: 14, lineHeight: 1.2 }}>Screener</span>
                      <span style={{ fontSize: 11.5, color: '#9A9A92', fontWeight: 500 }}>Saring saham per sinyal</span>
                    </span>
                  </Link>
                </div>
              </div>
            </div>

            <a href="#cara" style={menuItemStyle('works')} onClick={(e) => handleNavClick(e, 'cara', 'works')}>
              How It Works
            </a>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <Link
              href="/overview"
              className="lp-navbtn"
              style={{
                textDecoration: 'none',
                color: '#fff',
                background: ACCENT,
                fontWeight: 700,
                fontSize: 14.5,
                padding: '10px 18px',
                borderRadius: RADIUS,
                boxShadow: `0 2px 10px color-mix(in oklab, ${ACCENT}, transparent 64%)`,
                transition: 'transform .18s ease',
              }}
            >
              Launch the App
            </Link>
          </div>
        </nav>
      </header>

      {/* ── HERO ────────────────────────────────────────────── */}
      <section
        style={{
          position: 'relative',
          maxWidth: 1200,
          margin: '0 auto',
          padding: '74px 28px 84px',
          display: 'grid',
          gridTemplateColumns: '1.04fr .96fr',
          gap: 60,
          alignItems: 'center',
        }}
        className="lp-hero"
      >
        {/* Graph-paper grid backdrop — fades in toward the mock panel */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            zIndex: 0,
            pointerEvents: 'none',
            backgroundImage: `linear-gradient(${HAIR} 1px, transparent 1px), linear-gradient(90deg, ${HAIR} 1px, transparent 1px)`,
            backgroundSize: '38px 38px',
            opacity: 0.55,
            maskImage: 'radial-gradient(115% 115% at 82% 12%, #000 0%, transparent 60%)',
            WebkitMaskImage: 'radial-gradient(115% 115% at 82% 12%, #000 0%, transparent 60%)',
          }}
        />
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
              color: `color-mix(in oklab, ${ACCENT}, black 22%)`,
              fontFamily: MONO,
              fontSize: 12,
              fontWeight: 600,
              letterSpacing: '.04em',
              textTransform: 'uppercase',
              padding: '7px 12px',
              borderRadius: 999,
            }}
          >
            <span style={{ width: 7, height: 7, borderRadius: '50%', background: ACCENT }} />
            Data EOD • Refresh 16:00 WIB
          </div>
          <h1 style={{ margin: '22px 0 0', fontSize: 'clamp(40px,5vw,60px)', lineHeight: 1.04, fontWeight: 800, letterSpacing: '-.03em' }}>
            Pantau Saham,
            <br />
            <span style={{ color: ACCENT }}>Raih Peluang.</span>
          </h1>
          <p style={{ margin: '22px 0 0', fontSize: 18, lineHeight: 1.55, color: MUTED, maxWidth: 468 }}>
            Satu dashboard untuk watchlist, portofolio, dan screener. Lihat harga penutupan dan P&amp;L kamu dalam satu layar
            yang bersih, diperbarui tiap sore.
          </p>
          <div style={{ display: 'flex', gap: 12, marginTop: 30, flexWrap: 'wrap' }}>
            <Link
              href="/dashboard"
              style={{
                textDecoration: 'none',
                color: '#fff',
                background: ACCENT,
                fontWeight: 700,
                fontSize: 16,
                padding: '15px 26px',
                borderRadius: RADIUS,
                boxShadow: `0 6px 20px color-mix(in oklab, ${ACCENT}, transparent 60%)`,
              }}
            >
              Masuk Market
            </Link>
            <Link
              href="/portfolio"
              style={{
                textDecoration: 'none',
                color: '#14140F',
                background: '#fff',
                border: '1px solid #E2E1DB',
                fontWeight: 700,
                fontSize: 16,
                padding: '15px 26px',
                borderRadius: RADIUS,
              }}
            >
              Open Portofolio
            </Link>
          </div>
          <p style={{ margin: '22px 0 0', fontFamily: MONO, fontSize: 12.5, color: '#8C8C84', letterSpacing: '.01em' }}>
            Data end-of-day • Refresh otomatis tiap hari 16:00 WIB
          </p>
        </div>

        {/* MOCK PANEL */}
        <div style={{ position: 'relative', zIndex: 1 }}>
          <div
            style={{
              position: 'absolute',
              inset: '-26px -10px -10px',
              background: `radial-gradient(60% 55% at 70% 25%, color-mix(in oklab, ${ACCENT}, transparent 84%), transparent 70%)`,
              filter: 'blur(6px)',
            }}
          />
          <div
            style={{
              position: 'relative',
              background: '#fff',
              border: `1px solid ${HAIR}`,
              borderRadius: 18,
              boxShadow: '0 24px 60px -24px rgba(20,20,15,.28), 0 4px 14px -6px rgba(20,20,15,.1)',
              padding: '18px 18px 8px',
              animation: 'lpFloatY 7s ease-in-out infinite',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 700, fontSize: 14 }}>
                Watchlist
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    fontFamily: MONO,
                    fontSize: 10.5,
                    fontWeight: 500,
                    color: '#8C8C84',
                    background: '#F2F1EC',
                    padding: '3px 8px',
                    borderRadius: 999,
                  }}
                >
                  EOD 16:00
                </span>
              </div>
              <span style={{ fontFamily: MONO, fontSize: 11, color: '#9A9A92' }}>29 Jun</span>
            </div>

            <div style={{ background: '#FBFBF9', border: '1px solid #F0EFEA', borderRadius: 13, padding: '14px 15px', marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
                <div>
                  <div style={{ fontSize: 12, color: '#83837B', fontWeight: 600 }}>IHSG</div>
                  <div style={{ fontFamily: MONO, fontSize: 25, fontWeight: 600, letterSpacing: '-.01em', marginTop: 2 }}>7.298,21</div>
                </div>
                <div style={{ textAlign: 'right', fontFamily: MONO }}>
                  <div style={{ color: '#138A50', fontSize: 14, fontWeight: 600 }}>+46,18</div>
                  <div style={{ color: '#138A50', fontSize: 12 }}>+0,64%</div>
                </div>
              </div>
              <svg viewBox="0 0 520 96" preserveAspectRatio="none" style={{ width: '100%', height: 70, marginTop: 8, display: 'block', overflow: 'visible' }}>
                <defs>
                  <linearGradient id="lpSpk" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={ACCENT} stopOpacity=".26" />
                    <stop offset="100%" stopColor={ACCENT} stopOpacity="0" />
                  </linearGradient>
                </defs>
                <polygon
                  points="0,72 40,64 80,68 120,50 160,56 200,40 240,47 280,30 320,37 360,22 400,29 440,16 480,21 520,8 520,96 0,96"
                  fill="url(#lpSpk)"
                />
                <polyline
                  points="0,72 40,64 80,68 120,50 160,56 200,40 240,47 280,30 320,37 360,22 400,29 440,16 480,21 520,8"
                  fill="none"
                  stroke={ACCENT}
                  strokeWidth="2.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ strokeDasharray: 760, animation: 'lpDrawLine 1.8s ease forwards' }}
                />
              </svg>
            </div>

            <div>
              {WATCHLIST.map((row, i) => (
                <div
                  key={row.ticker}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '11px 2px',
                    borderBottom: i < WATCHLIST.length - 1 ? '1px solid #F2F1EC' : 'none',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 700, fontSize: 14 }}>{row.ticker}</span>
                    <span style={{ fontSize: 11.5, color: '#9A9A92' }}>{row.name}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontFamily: MONO, fontSize: 14 }}>{row.price}</span>
                    <span
                      style={{
                        fontFamily: MONO,
                        fontSize: 12,
                        color: row.up ? '#138A50' : '#D23B3B',
                        background: row.up ? '#E7F6EE' : '#FBE9E9',
                        padding: '3px 8px',
                        borderRadius: 7,
                      }}
                    >
                      {row.chg}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── FITUR ───────────────────────────────────────────── */}
      <section id="fitur" style={{ maxWidth: 1200, margin: '0 auto', padding: '36px 28px 20px' }}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: ACCENT }}>
            Fitur
          </div>
          <h2 style={{ margin: '12px 0 0', fontSize: 'clamp(28px,3.4vw,38px)', fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1.1 }}>
            Semua yang kamu butuh untuk pantau market
          </h2>
          <p style={{ margin: '14px 0 0', fontSize: 16.5, lineHeight: 1.55, color: MUTED }}>
            Dirancang ringkas — fokus ke angka, bukan ke clutter.
          </p>
        </div>

        <div className="lp-grid-4" style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 18, marginTop: 34 }}>
          {/* watchlist */}
          <div className="lp-card" style={featureCardStyle}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 13,
                background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                gap: 4,
                padding: '0 12px',
              }}
            >
              <span style={{ height: 3, borderRadius: 2, background: ACCENT, width: '100%' }} />
              <span style={{ height: 3, borderRadius: 2, background: ACCENT, width: '72%', opacity: 0.6 }} />
              <span style={{ height: 3, borderRadius: 2, background: ACCENT, width: '86%', opacity: 0.4 }} />
            </div>
            <h3 style={{ margin: '18px 0 0', fontSize: 17, fontWeight: 700 }}>Watchlist Harian</h3>
            <p style={{ margin: '8px 0 0', fontSize: 14, lineHeight: 1.5, color: '#67675F' }}>
              Susun daftar saham favorit dan lihat harga penutupannya, diperbarui tiap sore.
            </p>
          </div>
          {/* portfolio */}
          <div className="lp-card" style={featureCardStyle}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 13,
                background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span
                style={{
                  width: 24,
                  height: 24,
                  borderRadius: '50%',
                  background: `conic-gradient(${ACCENT} 0 62%, color-mix(in oklab, ${ACCENT}, white 60%) 62% 100%)`,
                  position: 'relative',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <span style={{ width: 11, height: 11, borderRadius: '50%', background: `color-mix(in oklab, ${ACCENT}, white 88%)` }} />
              </span>
            </div>
            <h3 style={{ margin: '18px 0 0', fontSize: 17, fontWeight: 700 }}>Analisa Portofolio</h3>
            <p style={{ margin: '8px 0 0', fontSize: 14, lineHeight: 1.5, color: '#67675F' }}>
              Alokasi aset, bobot tiap saham, dan komposisi yang gampang dibaca.
            </p>
          </div>
          {/* pnl */}
          <div className="lp-card" style={featureCardStyle}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 13,
                background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <span style={{ width: 0, height: 0, borderLeft: '9px solid transparent', borderRight: '9px solid transparent', borderBottom: `15px solid ${ACCENT}` }} />
            </div>
            <h3 style={{ margin: '18px 0 0', fontSize: 17, fontWeight: 700 }}>Profit &amp; Loss</h3>
            <p style={{ margin: '8px 0 0', fontSize: 14, lineHeight: 1.5, color: '#67675F' }}>
              P&amp;L harian &amp; total dengan persentase return per posisi, otomatis.
            </p>
          </div>
          {/* screener */}
          <div className="lp-card" style={featureCardStyle}>
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 13,
                background: `color-mix(in oklab, ${ACCENT}, white 88%)`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
              }}
            >
              <span style={{ width: 16, height: 16, borderRadius: '50%', border: `3px solid ${ACCENT}` }} />
              <span
                style={{
                  position: 'absolute',
                  width: 8,
                  height: 3,
                  borderRadius: 2,
                  background: ACCENT,
                  transform: 'rotate(45deg)',
                  right: 11,
                  bottom: 11,
                }}
              />
            </div>
            <h3 style={{ margin: '18px 0 0', fontSize: 17, fontWeight: 700 }}>Smart Screener</h3>
            <p style={{ margin: '8px 0 0', fontSize: 14, lineHeight: 1.5, color: '#67675F' }}>
              Saring ratusan saham pakai preset sinyal teknikal &amp; fundamental.
            </p>
          </div>
        </div>
      </section>

      {/* ── SCREENER HIGHLIGHT ───────────────────────────────── */}
      <section id="screener" style={{ maxWidth: 1200, margin: '0 auto', padding: '64px 28px 24px' }}>
        <div className="lp-screener-split" style={{ display: 'grid', gridTemplateColumns: '.9fr 1.1fr', gap: 48, alignItems: 'center' }}>
          <div>
            <div style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: ACCENT }}>
              Screener
            </div>
            <h2 style={{ margin: '12px 0 0', fontSize: 'clamp(28px,3.4vw,38px)', fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1.1 }}>
              Temukan saham bergerak sebelum yang lain
            </h2>
            <p style={{ margin: '14px 0 0', fontSize: 16.5, lineHeight: 1.55, color: MUTED }}>
              Preset <b>Volume Breakout</b> sudah aktif untuk semua orang. Preset lanjutan terbuka saat kamu connect portofolio.
            </p>
            <Link
              href="/screener"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                marginTop: 22,
                textDecoration: 'none',
                color: '#fff',
                background: ACCENT,
                fontWeight: 700,
                fontSize: 15,
                padding: '13px 22px',
                borderRadius: RADIUS,
                boxShadow: `0 6px 20px color-mix(in oklab, ${ACCENT}, transparent 62%)`,
              }}
            >
              Buka semua preset →
            </Link>
          </div>

          <div style={{ background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 18, boxShadow: '0 18px 44px -28px rgba(20,20,15,.24)', padding: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 9, fontWeight: 700, fontSize: 14.5 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: ACCENT }} />
                Volume Breakout
              </div>
              <span style={{ fontFamily: MONO, fontSize: 11, color: '#138A50', background: '#E7F6EE', padding: '3px 9px', borderRadius: 999 }}>
                12 match
              </span>
            </div>
            <div style={{ border: '1px solid #F0EFEA', borderRadius: 12, overflow: 'hidden' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.4fr 1fr .9fr 1fr',
                  background: '#FBFBF9',
                  fontFamily: MONO,
                  fontSize: 10.5,
                  color: '#9A9A92',
                  textTransform: 'uppercase',
                  letterSpacing: '.04em',
                  padding: '9px 14px',
                }}
              >
                <span>Saham</span>
                <span style={{ textAlign: 'right' }}>Harga</span>
                <span style={{ textAlign: 'right' }}>Chg</span>
                <span style={{ textAlign: 'right' }}>Vol ×avg</span>
              </div>
              {BREAKOUT.map((row) => (
                <div
                  key={row.ticker}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1.4fr 1fr .9fr 1fr',
                    alignItems: 'center',
                    padding: '11px 14px',
                    borderTop: '1px solid #F2F1EC',
                    fontSize: 13.5,
                  }}
                >
                  <span style={{ fontWeight: 700 }}>{row.ticker}</span>
                  <span style={{ fontFamily: MONO, textAlign: 'right' }}>{row.price}</span>
                  <span style={{ fontFamily: MONO, textAlign: 'right', color: '#138A50' }}>{row.chg}</span>
                  <span style={{ fontFamily: MONO, textAlign: 'right', color: ACCENT }}>{row.vol}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* locked presets grid */}
        <div style={{ marginTop: 40 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
            <h3 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Preset screener lainnya</h3>
            <span style={{ fontFamily: MONO, fontSize: 12.5, color: '#9A9A92' }}>6 preset terkunci</span>
          </div>
          <div className="lp-grid-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18, marginTop: 18 }}>
            {lockedPresets.map((p) => (
              <div key={p.name} className="lp-card" style={{ position: 'relative', background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 16, padding: 22, overflow: 'hidden', minHeight: 150 }}>
                <div style={{ filter: 'blur(5px)', userSelect: 'none', pointerEvents: 'none', opacity: 0.85 }}>
                  <div style={{ fontWeight: 700, fontSize: 16 }}>{p.name}</div>
                  <p style={{ margin: '8px 0 0', fontSize: 13.5, lineHeight: 1.5, color: '#67675F' }}>{p.desc}</p>
                  <div style={{ display: 'flex', gap: 6, marginTop: 16 }}>
                    <span style={{ fontFamily: MONO, fontSize: 12, background: '#F4F3EE', padding: '4px 9px', borderRadius: 7 }}>{p.match} match</span>
                    <span style={{ fontFamily: MONO, fontSize: 12, background: '#F4F3EE', padding: '4px 9px', borderRadius: 7 }}>{p.tag}</span>
                  </div>
                </div>
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 10,
                    background: 'linear-gradient(180deg, rgba(255,255,255,.45), rgba(255,255,255,.72))',
                  }}
                >
                  <span style={{ position: 'relative', width: 30, height: 34 }}>
                    <span style={{ position: 'absolute', bottom: 0, left: 0, width: 30, height: 22, borderRadius: 6, background: ACCENT }} />
                    <span style={{ position: 'absolute', top: 0, left: 7, width: 16, height: 18, border: `3px solid ${ACCENT}`, borderBottom: 'none', borderRadius: '9px 9px 0 0' }} />
                    <span style={{ position: 'absolute', bottom: 7, left: 13, width: 4, height: 8, borderRadius: 2, background: '#fff' }} />
                  </span>
                  <span
                    style={{
                      fontFamily: MONO,
                      fontSize: 12,
                      fontWeight: 600,
                      color: `color-mix(in oklab, ${ACCENT}, black 18%)`,
                      background: `color-mix(in oklab, ${ACCENT}, white 84%)`,
                      padding: '5px 12px',
                      borderRadius: 999,
                    }}
                  >
                    Terkunci
                  </span>
                </div>
              </div>
            ))}
            {fadedPresets.map((p) => (
              <div
                key={p.name}
                style={{
                  position: 'relative',
                  background: '#fff',
                  border: `1px solid ${HAIR}`,
                  borderRadius: 16,
                  padding: 22,
                  overflow: 'hidden',
                  minHeight: 150,
                  opacity: 0.5,
                  maskImage: 'linear-gradient(to bottom, #000 0%, #000 30%, transparent 88%)',
                  WebkitMaskImage: 'linear-gradient(to bottom, #000 0%, #000 30%, transparent 88%)',
                }}
              >
                <div style={{ filter: 'blur(6px)', userSelect: 'none', pointerEvents: 'none', opacity: 0.8 }}>
                  <div style={{ fontWeight: 700, fontSize: 16 }}>{p.name}</div>
                  <p style={{ margin: '8px 0 0', fontSize: 13.5, lineHeight: 1.5, color: '#67675F' }}>{p.desc}</p>
                  <div style={{ display: 'flex', gap: 6, marginTop: 16 }}>
                    <span style={{ fontFamily: MONO, fontSize: 12, background: '#F4F3EE', padding: '4px 9px', borderRadius: 7 }}>{p.match} match</span>
                    <span style={{ fontFamily: MONO, fontSize: 12, background: '#F4F3EE', padding: '4px 9px', borderRadius: 7 }}>{p.tag}</span>
                  </div>
                </div>
                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <span style={{ position: 'relative', width: 26, height: 30, animation: 'lpBob 3s ease-in-out infinite' }}>
                    <span style={{ position: 'absolute', bottom: 0, left: 0, width: 26, height: 19, borderRadius: 5, background: ACCENT }} />
                    <span style={{ position: 'absolute', top: 0, left: 6, width: 14, height: 16, border: `3px solid ${ACCENT}`, borderBottom: 'none', borderRadius: '8px 8px 0 0' }} />
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CARA KERJA ──────────────────────────────────────── */}
      <section id="cara" style={{ maxWidth: 1200, margin: '0 auto', padding: '72px 28px 24px' }}>
        <div style={{ textAlign: 'center', maxWidth: 560, margin: '0 auto' }}>
          <div style={{ fontFamily: MONO, fontSize: 12, fontWeight: 600, letterSpacing: '.06em', textTransform: 'uppercase', color: ACCENT }}>
            Cara Kerja
          </div>
          <h2 style={{ margin: '12px 0 0', fontSize: 'clamp(28px,3.4vw,38px)', fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1.1 }}>
            Mulai dalam 3 langkah
          </h2>
        </div>
        <div className="lp-grid-3" style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 18, marginTop: 38 }}>
          {[
            { n: '01', title: 'Buat watchlist', desc: 'Tambahkan saham yang ingin kamu pantau dari 900+ emiten IDX.' },
            { n: '02', title: 'Pantau tiap sore', desc: 'Data ditarik saat market tutup (16:00 WIB) — harga, P&L, dan sinyal screener langsung diperbarui.' },
            { n: '03', title: 'Raih peluang', desc: 'Open portofolio dan ambil keputusan dengan data di depan mata.' },
          ].map((step) => (
            <div key={step.n} className="lp-card" style={{ background: '#fff', border: `1px solid ${HAIR}`, borderRadius: 16, padding: 28 }}>
              <div
                style={{
                  fontFamily: MONO,
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#fff',
                  background: ACCENT,
                  width: 34,
                  height: 34,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 10,
                }}
              >
                {step.n}
              </div>
              <h3 style={{ margin: '18px 0 0', fontSize: 17.5, fontWeight: 700 }}>{step.title}</h3>
              <p style={{ margin: '8px 0 0', fontSize: 14.5, lineHeight: 1.55, color: '#67675F' }}>{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────── */}
      <section style={{ maxWidth: 1200, margin: '0 auto', padding: '72px 28px' }}>
        <div style={{ position: 'relative', overflow: 'hidden', background: '#16160F', color: '#fff', borderRadius: 24, padding: '64px 40px', textAlign: 'center' }}>
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: `radial-gradient(50% 80% at 50% 0%, color-mix(in oklab, ${ACCENT}, transparent 70%), transparent 70%)`,
              animation: 'lpGlowPulse 5s ease-in-out infinite',
            }}
          />
          <div style={{ position: 'relative' }}>
            <h2 style={{ margin: 0, fontSize: 'clamp(30px,3.8vw,44px)', fontWeight: 800, letterSpacing: '-.02em', lineHeight: 1.08 }}>
              Siap raih peluang berikutnya?
            </h2>
            <p style={{ margin: '16px auto 0', fontSize: 17, lineHeight: 1.55, color: '#B9B9AE', maxWidth: 480 }}>
              Mulai pantau saham kamu hari ini. Gratis untuk monitoring, tanpa kartu kredit.
            </p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 30, flexWrap: 'wrap' }}>
              <Link
                href="/dashboard"
                style={{
                  textDecoration: 'none',
                  color: '#fff',
                  background: ACCENT,
                  fontWeight: 700,
                  fontSize: 16,
                  padding: '15px 28px',
                  borderRadius: RADIUS,
                  boxShadow: `0 6px 22px color-mix(in oklab, ${ACCENT}, transparent 55%)`,
                }}
              >
                Masuk Market
              </Link>
              <Link
                href="/portfolio"
                style={{
                  textDecoration: 'none',
                  color: '#fff',
                  background: 'rgba(255,255,255,.08)',
                  border: '1px solid rgba(255,255,255,.16)',
                  fontWeight: 700,
                  fontSize: 16,
                  padding: '15px 28px',
                  borderRadius: RADIUS,
                }}
              >
                Open Portofolio
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────── */}
      <footer style={{ borderTop: `1px solid ${HAIR}`, background: '#FCFCFB' }}>
        <div className="lp-footer-grid" style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 28px', display: 'grid', gridTemplateColumns: '1.6fr 1fr 1fr 1fr', gap: 32 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', fontWeight: 800, fontSize: 20, letterSpacing: '.06em' }}>
              EMETIQ
            </div>
            <p style={{ margin: '14px 0 0', fontSize: 14, lineHeight: 1.55, color: '#7C7C74', maxWidth: 280 }}>
              Dashboard monitoring saham pribadi. Pantau watchlist, portofolio, dan screener dalam satu tempat.
            </p>
            <p style={{ margin: '16px 0 0', fontFamily: MONO, fontSize: 11.5, color: '#A6A69E' }}>
              Bukan rekomendasi beli/jual. Risiko di tangan kamu.
            </p>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#14140F', marginBottom: 14 }}>Produk</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14, color: '#7C7C74' }}>
              <a href="#fitur" style={{ textDecoration: 'none', color: 'inherit' }}>Fitur</a>
              <a href="#screener" style={{ textDecoration: 'none', color: 'inherit' }}>Screener</a>
              <Link href="/portfolio" style={{ textDecoration: 'none', color: 'inherit' }}>Portofolio</Link>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#14140F', marginBottom: 14 }}>Sumber</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14, color: '#7C7C74' }}>
              <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Dokumentasi</a>
              <a href="#cara" style={{ textDecoration: 'none', color: 'inherit' }}>Cara Kerja</a>
              <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Status Data</a>
            </div>
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#14140F', marginBottom: 14 }}>Lainnya</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14, color: '#7C7C74' }}>
              <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Privasi</a>
              <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Ketentuan</a>
              <a href="#" style={{ textDecoration: 'none', color: 'inherit' }}>Kontak</a>
            </div>
          </div>
        </div>
        <div style={{ borderTop: `1px solid ${HAIR}` }}>
          <div
            style={{
              maxWidth: 1200,
              margin: '0 auto',
              padding: '18px 28px',
              display: 'flex',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: 8,
              fontFamily: MONO,
              fontSize: 12,
              color: '#A6A69E',
            }}
          >
            <span>© 2026 EMETIQ</span>
            <span>Data IDX • update 16:00 WIB</span>
          </div>
        </div>
      </footer>

      <style jsx global>{`
        @keyframes lpFloatY {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-10px); }
        }
        @keyframes lpDrawLine {
          from { stroke-dashoffset: 760; }
          to { stroke-dashoffset: 0; }
        }
        @keyframes lpGlowPulse {
          0%, 100% { opacity: .5; }
          50% { opacity: 1; }
        }
        @keyframes lpBob {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-5px); }
        }
        .lp-card {
          transition: transform .2s ease, box-shadow .2s ease;
        }
        .lp-card:hover {
          transform: translateY(-4px);
          box-shadow: 0 18px 38px -22px rgba(20, 20, 15, .28);
        }
        .lp-navbtn:hover {
          transform: translateY(-1px);
        }
        .lp-menuitem {
          display: flex;
          align-items: center;
          gap: 11px;
          padding: 9px 10px;
          border-radius: 10px;
          text-decoration: none;
          color: #14140f;
          transition: background .15s ease;
        }
        .lp-menuitem:hover {
          background: color-mix(in oklab, #f26a1b, white 90%);
        }
        ::selection {
          background: color-mix(in oklab, #f26a1b, white 70%);
        }
        @media (max-width: 900px) {
          .lp-hero { grid-template-columns: 1fr !important; }
          .lp-screener-split { grid-template-columns: 1fr !important; }
          .lp-grid-4 { grid-template-columns: repeat(2, 1fr) !important; }
          .lp-grid-3 { grid-template-columns: 1fr !important; }
          .lp-footer-grid { grid-template-columns: 1fr 1fr !important; }
        }
        @media (max-width: 640px) {
          .lp-navmenu { display: none !important; }
        }
        @media (max-width: 560px) {
          .lp-grid-4 { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}

// ── Shared style objects ──────────────────────────────────────
const featureCardStyle: React.CSSProperties = {
  background: '#fff',
  border: `1px solid ${HAIR}`,
  borderRadius: 16,
  padding: 24,
};
