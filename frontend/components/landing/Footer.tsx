// Footer (plan §13.3): the Supreme Court's motto, the draft disclaimer, the free legal aid line for the public, nav links.
// Oxblood block; gold text only on oxblood (plan §13.2). Own typography only: no emblem, no court logo.
import Link from "next/link";
import type { ReactElement } from "react";
import { Phone } from "lucide-react";
import { cn } from "@/lib/utils";

export interface FooterProps {
  className?: string;
}

const LINKS = [
  { href: "/cases", label: "Cause list" },
  { href: "/desk", label: "Desk" },
  { href: "/library", label: "Library" },
  { href: "/about", label: "About" },
] as const;

export function Footer({ className }: FooterProps): ReactElement {
  return (
    <footer data-landing-footer data-testid="site-footer" className={cn("relative overflow-hidden bg-oxblood text-cream", className)}>
      <div aria-hidden className="bg-jaali-dark pointer-events-none absolute inset-0 opacity-40" />
      <div className="relative z-10 mx-auto grid max-w-[1280px] gap-10 px-6 py-14 sm:px-10 lg:grid-cols-12">
        <div className="flex flex-col gap-3 lg:col-span-5">
          <p lang="hi" className="font-devanagari text-4xl leading-devanagari text-gold-pale sm:text-5xl">यतो धर्मस्ततो जयः</p>
          <p className="font-display text-lg italic text-cream/90">Where there is dharma, there is victory.</p>
          <p className="font-mono text-2xs uppercase tracking-[0.18em] text-gold-pale">The motto of the Supreme Court of India</p>
        </div>

        <div className="flex flex-col gap-4 lg:col-span-4">
          <p className="font-display text-xl font-semibold">Vakeel-Sahayak.ai</p>
          <p className="text-base text-cream/95">AI-generated drafts for counsel. Not legal advice.</p>
          <p className="text-sm text-cream/80">Every claim is tied to a source page, and counsel approves before anything leaves the system.</p>
          <nav aria-label="Footer">
            <ul className="flex flex-wrap gap-x-5 gap-y-2">
              {LINKS.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="rounded-sm text-sm font-semibold text-cream underline-offset-4 hover:text-gold-pale hover:underline">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        </div>

        <div className="lg:col-span-3">
          <div className="flex flex-col gap-2 rounded-lg border border-gold-leaf/70 p-4">
            <p className="font-mono text-2xs uppercase tracking-[0.18em] text-gold-pale">For the public</p>
            <p className="text-sm text-cream/95">Cannot afford a lawyer? Free legal aid is your right (Art. 39A).</p>
            <a
              href="tel:15100"
              className="inline-flex items-center gap-2 rounded-sm font-display text-3xl font-semibold text-gold-pale underline-offset-4 hover:underline"
              aria-label="Call NALSA free legal aid helpline 15100"
            >
              <Phone aria-hidden className="size-5" /> NALSA 15100
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
