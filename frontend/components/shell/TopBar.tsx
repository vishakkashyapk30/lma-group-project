"use client";
// Top bar: where you are (breadcrumb), search (Ctrl/Cmd+K), the primary action, local mode, and the help menu.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { HardDrive, LifeBuoy, Menu, Phone, Plus, Search, Settings } from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { Breadcrumb, type Crumb } from "@/components/ui/breadcrumb";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Tooltip } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/toast";
import { getApiMode, getConnection, onApiModeChange, onConnectionChange, unreachableMessage, type ApiMode, type Connection } from "@/lib/api";
import { toggleReducedMotion } from "@/lib/useReducedMotion";
import { useCaseMeta } from "./meta";
import { useLang, useT } from "@/lib/i18n";
import { NAV_ITEMS } from "./nav";
import { useShell } from "./ShellProvider";

function useCrumbs(): { crumbs: Crumb[]; stage: string | null } {
  const path = usePathname() ?? "";
  const meta = useCaseMeta();
  const t = useT();
  if (path.startsWith("/case/")) {
    const id = decodeURIComponent(path.split("/")[2] ?? "");
    const own = meta && meta.caseId === id ? meta : null;
    return { crumbs: [{ label: t("Cases"), href: "/cases" }, { label: own?.title ?? id, share: `case-title-${id}` }], stage: own?.stageLabel ? t(own.stageLabel) : null };
  }
  if (path.startsWith("/about")) return { crumbs: [{ label: t("Help"), href: "/help" }, { label: t("About") }], stage: null };
  const item = NAV_ITEMS.find((n) => path === n.href);
  return { crumbs: [{ label: item ? t(item.label) : "Vakeel-Sahayak" }], stage: null };
}

/** Honest mode label: sample data, connected, or (in live mode) a server that does not answer. */
export function ModeChip(): ReactElement {
  const t = useT();
  const [mode, setMode] = useState<ApiMode>("demo");
  const [connection, setConnection] = useState<Connection>("unknown");
  useEffect(() => {
    setMode(getApiMode());
    setConnection(getConnection());
    const offMode = onApiModeChange(setMode);
    const offConnection = onConnectionChange(setConnection);
    return () => {
      offMode();
      offConnection();
    };
  }, []);
  const sample = mode === "demo";
  const down = !sample && connection === "down";
  const tip = sample
    ? t("No server connected. You are working with built-in sample cases, changes stay in this browser and no external model service is used.")
    : down
      ? `${unreachableMessage()} Nothing is shown in place of your cases while it is down.`
      : t("Connected to the local server. Its model and privacy settings are under Settings.");
  return (
    <Tooltip content={tip} side="bottom">
      <Link href="/settings" data-testid="mode-chip" data-mode={mode} data-connection={connection} className="hidden h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-xs text-ink-soft no-underline hover:text-ink md:inline-flex">
        <HardDrive aria-hidden className="size-3.5" />
        {sample ? "Local · Sample data" : down ? "Local · Not connected" : "Local · Connected"}
      </Link>
    </Tooltip>
  );
}

function HelpMenu(): ReactElement {
  const toast = useToast();
  const t = useT();
  const toggleMotion = () => toast(toggleReducedMotion() ? t("Motion reduced") : t("Motion restored"));
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={t("Settings and help")}><Settings aria-hidden /></Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuLabel>{t("Help")}</DropdownMenuLabel>
        <DropdownMenuItem asChild><Link href="/help" className="no-underline"><LifeBuoy aria-hidden />{t("Help and shortcuts")}</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link href="/about" className="no-underline">{t("How it works and its limits")}</Link></DropdownMenuItem>
        <DropdownMenuItem asChild><Link href="/" className="no-underline">{t("Product overview")}</Link></DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuLabel>{t("Settings")}</DropdownMenuLabel>
        <DropdownMenuItem asChild><Link href="/settings" className="no-underline">{t("Server, models and privacy")}</Link></DropdownMenuItem>
        <DropdownMenuItem onSelect={toggleMotion}>{t("Reduce motion")}</DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild><a href="tel:15100" className="no-underline"><Phone aria-hidden />{t("Free legal aid: NALSA 15100")}</a></DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function TopBar(): ReactElement {
  const { setPaletteOpen, setNewCaseOpen, setDrawerOpen } = useShell();
  const { crumbs, stage } = useCrumbs();
  const t = useT();
  const { lang, setLang } = useLang();
  const [mac, setMac] = useState(false);
  useEffect(() => setMac(/Mac|iPhone|iPad/.test(navigator.platform)), []);
  return (
    <header data-print-hide className="sticky top-0 z-nav flex h-[var(--nav-h)] shrink-0 items-center gap-3 border-b border-line bg-parchment px-3 sm:px-4">
      <Button variant="ghost" size="icon" className="lg:hidden" aria-label={t("Open menu")} onClick={() => setDrawerOpen(true)}><Menu aria-hidden /></Button>
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <Breadcrumb items={crumbs} />
        {stage ? <span data-testid="topbar-stage" className="hidden shrink-0 text-sm text-ink-soft sm:inline">{t("Stage")}: <span className="font-medium text-ink">{stage}</span></span> : null}
      </div>
      <button
        type="button"
        onClick={() => setPaletteOpen(true)}
        aria-label={t("Search cases, pages and actions")}
        aria-keyshortcuts="Control+K Meta+K"
        data-testid="search-trigger"
        className="hidden h-9 w-64 items-center gap-2 rounded-md border border-line-strong/60 bg-cream px-2.5 text-sm text-ink-muted transition-colors duration-fast hover:border-line-strong md:flex xl:w-80"
      >
        <Search aria-hidden className="size-4" />
        <span className="flex-1 text-left">{t("Search")}</span>
        <kbd className="rounded-sm border border-line bg-parchment px-1.5 py-0.5 font-sans text-xs text-ink-muted">{mac ? "⌘K" : "Ctrl K"}</kbd>
      </button>
      <Button variant="ghost" size="icon" className="md:hidden" aria-label={t("Search cases, pages and actions")} onClick={() => setPaletteOpen(true)}><Search aria-hidden /></Button>
      <ModeChip />
      <Button
        variant="ghost"
        size="sm"
        data-testid="lang-toggle"
        lang={lang === "hi" ? "en" : "hi"}
        aria-label={lang === "hi" ? "Switch the interface to English" : "इंटरफ़ेस को हिन्दी में बदलें"}
        onClick={() => setLang(lang === "hi" ? "en" : "hi")}
      >
        {lang === "hi" ? "English" : "हिन्दी"}
      </Button>
      <Button data-testid="new-case-button" onClick={() => setNewCaseOpen(true)}><Plus aria-hidden /><span className="hidden sm:inline">{t("New case")}</span><span className="sr-only sm:hidden">{t("New case")}</span></Button>
      <HelpMenu />
    </header>
  );
}
