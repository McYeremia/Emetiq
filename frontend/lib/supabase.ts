'use client';

import type { SupabaseClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// True hanya bila env Supabase terisi. UI memakai ini untuk menampilkan pesan
// "auth belum dikonfigurasi" alih-alih error keras. Sengaja tetap sinkron: ia cuma
// membaca env, tak butuh pustaka apa pun.
export const supabaseConfigured = Boolean(url && anon);

// Fallback aman agar createClient tidak melempar saat env kosong (mis. saat build
// tanpa env). Panggilan auth akan gagal di jaringan, bukan saat modul dimuat.
const safeUrl = url || 'http://localhost:54321';
const safeAnon = anon || 'public-anon-key-placeholder';

// Promise-nya yang di-memoize, bukan kliennya. Dua pemanggil yang berbarengan
// (mis. AuthProvider dan halaman login) sama-sama menunggu promise yang sama, jadi
// hanya ADA SATU klien — dua klien berarti dua langganan onAuthStateChange dan dua
// penulis ke storage yang sama.
let klien: Promise<SupabaseClient> | null = null;

/**
 * Klien Supabase, diunduh saat pertama kali dibutuhkan.
 *
 * Sebelum 4 Sep 2026 modul ini mengekspor `const supabase = createClient(...)` di
 * tingkat modul. Akibatnya pustaka 225,9 KB (GoTrue + Realtime, padahal yang dipakai
 * cuma auth) masuk ke chunk bersama SETIAP rute — `AuthProvider` ada di root layout,
 * jadi landing page, halaman login, bahkan halaman 404 ikut mengunduhnya sebelum
 * hidrasi.
 *
 * Bentuk fungsi + `import()` membuatnya jadi chunk terpisah yang hanya diambil saat
 * benar-benar ada yang memanggil. Yang menentukan "benar-benar" ada di
 * `adaSesiTersimpan()` di bawah.
 */
export function getSupabase(): Promise<SupabaseClient> {
  if (!klien) {
    klien = import('@supabase/supabase-js').then(({ createClient }) =>
      createClient(safeUrl, safeAnon, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
          detectSessionInUrl: true,
        },
      }),
    );
  }
  return klien;
}

/**
 * Apakah browser ini menyimpan sesi Supabase — dijawab TANPA memuat pustakanya.
 *
 * Inilah yang membuat pengunjung anonim tak pernah mengunduh 225,9 KB itu sama
 * sekali. supabase-js menyimpan sesinya di `localStorage` dengan kunci
 * `sb-<ref>-auth-token`, dan `<ref>` diambil dari hostname URL Supabase — dibaca
 * langsung dari kode pustakanya (`dist/index.mjs`):
 *
 *     const defaultStorageKey = `sb-${baseUrl.hostname.split(".")[0]}-auth-token`;
 *
 * Selama OAuth berjalan ada pula `sb-<ref>-auth-token-code-verifier`, dan itu juga
 * harus dihitung sebagai "ada sesi" — kalau tidak, pertukaran kode PKCE-nya gagal.
 * Karena itu pencocokannya berdasarkan pola, bukan satu kunci persis.
 *
 * ARAH KEGAGALANNYA SENGAJA: fungsi ini menjawab `true` bila ragu. Salah menjawab
 * `true` cuma berarti mengunduh yang tak perlu; salah menjawab `false` berarti
 * pengguna yang sudah login terlihat logout dan dilempar ke /login — termasuk dari
 * halaman yang bergantung pada tier seperti AI Porto. Jadi: localStorage tak bisa
 * dibaca (mode privat, pengaturan browser) → `true`. Format kuncinya berubah di
 * versi supabase-js mendatang → kunci `sb-` lain masih terlihat → `true`.
 */
export function adaSesiTersimpan(): boolean {
  if (typeof window === 'undefined') return false;
  if (!supabaseConfigured) return false;
  try {
    const simpanan = window.localStorage;
    for (let i = 0; i < simpanan.length; i++) {
      const kunci = simpanan.key(i);
      if (kunci && kunci.startsWith('sb-') && kunci.includes('auth-token')) return true;
    }
    return false;
  } catch {
    return true;
  }
}

// Base URL publik untuk redirect verifikasi email & OAuth. Set
// NEXT_PUBLIC_SITE_URL ke domain produksi (mis. https://emetiq.vercel.app) agar
// link verifikasi email TIDAK mengarah ke localhost saat register dari lokal /
// preview. Bila tak diset, fallback ke origin runtime.
export function siteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL;
  const base = configured || (typeof window !== 'undefined' ? window.location.origin : '');
  return base.replace(/\/$/, '');
}
