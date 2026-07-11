'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_LINKS = [
  { label: 'OVERVIEW',   href: '/overview' },
  { label: 'MARKET',     href: '/dashboard' },
  { label: 'SCREENER',   href: '/screener' },
  { label: 'PORTOFOLIO', href: '/portfolio' },
];

// Halaman warisan IDXAnalyst yang belum dipindahkan ke tema EMETIQ dan masih
// memakai chrome gelap ini sebagai satu-satunya navigasinya.
//
// Dulu daftarnya kebalikan — "sembunyikan di rute-rute ini" — dan itu rapuh:
// setiap halaman baru otomatis mewarisi navbar mati kecuali seseorang ingat
// mendaftarkannya. Halaman /big-money kena persis itu: navbar gelap ini terus
// dirender di bawahnya, berkedip saat hard refresh, dan warnanya menembus
// EmetiqNav yang semi-transparan sehingga terlihat keabu-abuan.
//
// Sebagai daftar-izin, default-nya kini aman: halaman baru tidak mendapat apa-apa.
//
// Tinggal satu penghuni: /broker-flow (data broker lama). /backtest sudah jadi
// stub redirect ke Screener, jadi ia tak butuh navigasi sama sekali.
const LEGACY_ROUTES = ['/broker-flow'];

export default function Header() {
  const pathname = usePathname();

  if (!LEGACY_ROUTES.includes(pathname)) return null;

  return (
    <header className="fixed top-0 w-full z-50 bg-[#0A0A0A] border-b-2 border-white/10">
      <div className="max-w-[1400px] mx-auto px-6 h-[60px] flex justify-between items-center">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#3B82F6] flex items-center justify-center font-black text-[11px] text-white">EM</div>
          <span className="text-base font-black tracking-tighter uppercase">
            EMETIQ
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-8">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(link.href + '/');
            return (
              <Link
                key={link.label}
                href={link.href}
                className={`text-[10px] font-black tracking-[0.2em] uppercase transition-colors ${
                  active ? 'text-[#3B82F6]' : 'text-gray-500 hover:text-[#3B82F6]'
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
