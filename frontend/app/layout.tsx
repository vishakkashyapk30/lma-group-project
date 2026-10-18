// Root layout (plan §13.1-13.2): Manuscript fonts (self-hosted via @fontsource, styles/fonts.css), skip link, top nav.
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { TopNav } from "@/components/common/TopNav";
import "../styles/fonts.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Vakeel-Sahayak.ai", template: "%s · Vakeel-Sahayak.ai" },
  description: "AI-generated drafts for counsel, every claim tied to a source. Not legal advice.",
};

export const viewport: Viewport = { themeColor: "#F6EEDC" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-maroon focus:px-4 focus:py-2 focus:text-cream"
        >
          Skip to main content
        </a>
        <TopNav />
        <main id="main" tabIndex={-1} className="outline-none">
          {children}
        </main>
      </body>
    </html>
  );
}
