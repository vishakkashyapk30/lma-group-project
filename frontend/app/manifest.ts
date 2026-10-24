import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Vakeel-Sahayak",
    short_name: "Vakeel-Sahayak",
    description: "Prepare a bail application from the case file. Every fact traced to its source.",
    start_url: "/cases",
    display: "standalone",
    background_color: "#F7F5F0",
    theme_color: "#7A1626",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
