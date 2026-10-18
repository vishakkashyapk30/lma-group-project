"use client";
// Top navigation: Vakeel-Sahayak · Cause list · Desk · Library (plan §13.1).
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactElement } from "react";
import { cn } from "@/lib/utils";
import { getApiMode, onApiModeChange, type ApiMode } from "@/lib/api";
import { useEffect, useState } from "react";
import { Logo } from "./Logo";

const LINKS = [
  { href: "/cases", label: "Cause list" },
  { href: "/desk", label: "Desk" },
  { href: "/library", label: "Library" },
  { href: "/about", label: "About" },
] as const;

export function TopNav(): ReactElement {
  const path = usePathname() ?? "/";
  const [mode, setMode] = useState<ApiMode>("demo");
  useEffect(() => {
    setMode(getApiMode());
    return onApiModeChange(setMode);
  }, []);
  return (
    <header className="sticky top-0 z-40 border-b border-gold-leaf/40 bg-parchment/95 backdrop-blur">
      <nav aria-label="Primary" className="mx-auto flex h-14 max-w-[1800px] items-center justify-between gap-4 px-4">
        <Link href="/" aria-label="Vakeel-Sahayak home" className="rounded-sm"><Logo /></Link>
        <ul className="flex items-center gap-1">
          {LINKS.map((l) => {
            const active = path === l.href || path.startsWith(`${l.href}/`) || (l.href === "/cases" && path.startsWith("/case/"));
            return (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-semibold no-underline transition-colors duration-fast",
                    active ? "bg-maroon text-cream" : "text-ink hover:bg-ink/[0.06]",
                  )}
                >
                  {l.label}
                </Link>
              </li>
            );
          })}
          <li className="ml-2 hidden sm:block">
            <span className="rounded-pill border border-line-strong/50 px-2 py-0.5 font-mono text-[11px] text-ink-muted" title={mode === "demo" ? "Running from built-in demo data" : "Connected to the API"}>
              {mode === "demo" ? "demo data" : "live"}
            </span>
          </li>
        </ul>
      </nav>
    </header>
  );
}

export default TopNav;
