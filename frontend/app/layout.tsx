// Root layout stub (plan §13.1). TODO: load fonts with next/font (Fraunces, Tiro Devanagari Hindi, Noto Sans Devanagari, DM Sans, IBM Plex Mono)
// and set --font-* variables from styles/tokens.css; wrap in Lenis provider (no-op under reduced motion).
import type { ReactNode } from "react";
import "./globals.css";

export const metadata = { title: "Vakeel-Sahayak.ai", description: "AI-generated drafts for counsel. Not legal advice." };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
