import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { ToastProvider } from "@/components/Toast";
import AuthProvider from "@/components/AuthProvider";
import WatchlistProvider from "@/components/WatchlistProvider";

// Sampai 3 Sep 2026 aplikasi ini menjalankan TIGA sistem font sekaligus: Geist
// lewat next/font di sini, `Arial` di globals.css, dan tag stylesheet ke
// fonts.googleapis.com yang ditempel langsung di JSX 13 berkas halaman. Yang
// menang adalah yang paling lambat — dua koneksi lintas-origin (googleapis lalu
// gstatic) di jalur kritis render, plus FOUT di setiap navigasi.
//
// Sekarang satu sistem. next/font mengunduh berkas fontnya saat BUILD dan
// menyajikannya dari domain sendiri, jadi tak ada koneksi lintas-origin sama
// sekali. Geist dibuang karena tak pernah benar-benar terlihat: seluruh halaman
// memakai Plus Jakarta Sans + IBM Plex Mono.
const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  display: "swap",
});

// Plus Jakarta Sans font variabel (satu berkas untuk semua ketebalan), IBM Plex
// Mono tidak — ketebalannya harus disebut satu per satu, dan tiap tambahan
// berarti satu berkas lagi yang diunduh. Tiga ini yang dipakai halaman.
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "EMETIQ — Monitoring Saham",
  description: "Platform monitoring saham Indonesia — watchlist, portofolio, screener, dan AI Advisor.",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "EMETIQ",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  // Let the on-screen keyboard resize the layout (Chrome/Android) so chat pages
  // shrink instead of scrolling; iOS is handled via the visualViewport API.
  interactiveWidget: "resizes-content",
  viewportFit: "cover",
  themeColor: "#F26A1B",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id" className={`${jakarta.variable} ${plexMono.variable} h-full antialiased`}>
      {/* Latar EMETIQ. Sebelumnya hitam #050505 warisan IDXAnalyst, yang berkedip
          gelap tiap hard refresh sebelum halaman terang menutupinya. Sejak
          /broker-flow dihapus (3 Sep 2026) tak ada lagi halaman bertema gelap,
          jadi komponen Header — yang cuma dirender di rute itu dan `return null`
          di semua rute lain — ikut dibuang. */}
      <body className="min-h-full flex flex-col bg-[#FCFCFB]">
        <AuthProvider>
          <ToastProvider>
            <WatchlistProvider>
              <div className="flex-1">
                {children}
              </div>
            </WatchlistProvider>
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
