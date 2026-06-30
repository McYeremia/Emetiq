import type { Metadata } from "next";
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
  title: "IDXAnalyst — Analisis Saham IDX80",
  description: "Platform analisis teknikal saham Indonesia — IDX80, candlestick chart, 16 indikator.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-[#050505]">
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
