// Token akses Supabase saat ini, disimpan di modul agar `lib/api.ts` (bukan React)
// bisa menyisipkan header Authorization secara sinkron. Diperbarui oleh AuthProvider
// setiap kali sesi berubah.
let _accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}
