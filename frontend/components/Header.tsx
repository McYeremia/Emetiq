'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_LINKS = [
  { label: 'OVERVIEW',   href: '/overview' },
  { label: 'MARKET',     href: '/dashboard' },
  { label: 'SCREENER',   href: '/screener' },
  { label: 'PORTOFOLIO', href: '/portfolio' },
];

export default function Header() {
  const pathname = usePathname();

  // Pages migrated to the EMETIQ theme ship their own navigation, so the
  // legacy dark app chrome is hidden there. Phased migration starts with '/'
  // and '/dashboard'; add routes here as each page is reskinned.
  if (pathname === '/' || pathname === '/dashboard' || pathname === '/overview' || pathname === '/screener' || pathname === '/portfolio' || pathname.startsWith('/stocks/')) return null;

  return (
    <header className="fixed top-0 w-full z-50 bg-[#0A0A0A] border-b-2 border-white/10">
      <div className="max-w-[1400px] mx-auto px-6 h-[60px] flex justify-between items-center">
        <Link href="/" className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#3B82F6] flex items-center justify-center font-black text-[11px] text-white">IX</div>
          <span className="text-base font-black tracking-tighter uppercase">
            IDX<span className="text-[#3B82F6]">Analyst</span>
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
