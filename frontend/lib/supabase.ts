'use client';

import { createClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

// True hanya bila env Supabase terisi. UI memakai ini untuk menampilkan pesan
// "auth belum dikonfigurasi" alih-alih error keras.
export const supabaseConfigured = Boolean(url && anon);

// Fallback aman agar createClient tidak melempar saat env kosong (mis. saat build
// tanpa env). Panggilan auth akan gagal di jaringan, bukan saat import modul.
const safeUrl = url || 'http://localhost:54321';
const safeAnon = anon || 'public-anon-key-placeholder';

export const supabase = createClient(safeUrl, safeAnon, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
});

// Base URL publik untuk redirect verifikasi email & OAuth. Set
// NEXT_PUBLIC_SITE_URL ke domain produksi (mis. https://emetiq.vercel.app) agar
// link verifikasi email TIDAK mengarah ke localhost saat register dari lokal /
// preview. Bila tak diset, fallback ke origin runtime.
export function siteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL;
  const base = configured || (typeof window !== 'undefined' ? window.location.origin : '');
  return base.replace(/\/$/, '');
}
