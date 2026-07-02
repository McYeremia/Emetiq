import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "EMETIQ — Monitoring Saham",
    short_name: "EMETIQ",
    description: "Intelligence built on truth. Watchlist, portofolio, screener, dan AI Advisor untuk saham IDX.",
    start_url: "/overview",
    display: "standalone",
    background_color: "#FCFCFB",
    theme_color: "#F26A1B",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-192-maskable.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
