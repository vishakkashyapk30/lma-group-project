// Root layout: fonts (self-hosted via @fontsource, styles/fonts.css), skip link, and the app shell.
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/AppShell";
import "../styles/fonts.css";
import "./globals.css";

const DESCRIPTION = "Prepare a bail application from the case file. Every fact traced to its source. AI-generated drafts for counsel, not legal advice.";

export const metadata: Metadata = {
  title: { default: "Vakeel-Sahayak", template: "%s | Vakeel-Sahayak" },
  description: DESCRIPTION,
  applicationName: "Vakeel-Sahayak",
  openGraph: { type: "website", siteName: "Vakeel-Sahayak", title: "Vakeel-Sahayak", description: DESCRIPTION, locale: "en_IN" },
  twitter: { card: "summary", title: "Vakeel-Sahayak", description: DESCRIPTION },
};

export const viewport: Viewport = { themeColor: "#7A1626" };

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[90] focus:rounded-md focus:bg-maroon focus:px-4 focus:py-2 focus:text-cream"
        >
          Skip to main content
        </a>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
