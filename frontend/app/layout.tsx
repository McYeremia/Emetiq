import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Header from "@/components/Header";
import { ToastProvider } from "@/components/Toast";
import AuthProvider from "@/components/AuthProvider";
import WatchlistProvider from "@/components/WatchlistProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
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
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      {/* Latar EMETIQ. Sebelumnya hitam #050505 warisan IDXAnalyst, yang berkedip
          gelap tiap hard refresh sebelum halaman terang menutupinya. Halaman
          warisan yang masih gelap (/broker-flow) membawa latarnya sendiri. */}
      <body className="min-h-full flex flex-col bg-[#FCFCFB]">
        <AuthProvider>
          <ToastProvider>
            <WatchlistProvider>
              <Header />
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
