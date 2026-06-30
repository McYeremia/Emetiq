'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from './AuthProvider';

/** Bungkus halaman personal. User belum login -> redirect ke /login?next=<path>. */
export default function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [loading, user, router, pathname]);

  if (loading || !user) {
    return (
      <div
        style={{ minHeight: '100vh', background: '#FCFCFB', color: '#F26A1B', fontFamily: "'IBM Plex Mono', monospace" }}
        className="flex items-center justify-center text-xs tracking-[0.3em] uppercase animate-pulse"
      >
        Memeriksa sesi...
      </div>
    );
  }
  return <>{children}</>;
}
