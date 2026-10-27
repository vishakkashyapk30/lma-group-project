"use client";
// Left sidebar: Cases, Batch desk, Precedent library, Help. Collapses to icons (tooltips carry the labels).
// On narrow screens the same list renders inside a drawer (see MobileDrawer).
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import type { ReactElement } from "react";
import { Logo } from "@/components/common/Logo";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { NAV_ITEMS, isActive } from "./nav";
import { markRouteFocus } from "./routeFocus";
import { useShell } from "./ShellProvider";

export function NavList({ collapsed = false, onNavigate }: { collapsed?: boolean; onNavigate?: () => void }): ReactElement {
  const path = usePathname() ?? "/";
  return (
    <ul className="flex flex-col gap-0.5">
      {NAV_ITEMS.map((item) => {
        const active = isActive(item, path);
        const Icon = item.icon;
        const link = (
          <Link
            href={item.href}
            onClick={() => {
              markRouteFocus();
              onNavigate?.();
            }}
            aria-current={active ? "page" : undefined}
            aria-label={collapsed ? item.label : undefined}
            className={cn(
              "relative flex h-9 items-center gap-3 rounded-md px-2.5 text-sm no-underline transition-colors duration-fast",
              collapsed && "justify-center px-0",
              active ? "bg-maroon/[0.09] font-semibold text-maroon" : "text-ink-soft hover:bg-ink/[0.06] hover:text-ink",
            )}
          >
            {active ? <span aria-hidden className="absolute -left-2 top-1.5 h-6 w-0.5 rounded-full bg-maroon" /> : null}
            <Icon aria-hidden className="size-[18px] shrink-0" />
            {collapsed ? null : <span className="truncate">{item.label}</span>}
          </Link>
        );
        return <li key={item.href}>{collapsed ? <Tooltip content={item.label} side="right" delay={150}>{link}</Tooltip> : link}</li>;
      })}
    </ul>
  );
}

export function Sidebar(): ReactElement {
  const { collapsed: preferred, toggleCollapsed } = useShell();
  // Inside a case the workspace needs the width, so the sidebar stays a narrow icon rail there.
  const inCase = (usePathname() ?? "").startsWith("/case/");
  const collapsed = preferred || inCase;
  return (
    <aside
      data-testid="sidebar"
      data-collapsed={collapsed}
      data-print-hide
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-parchment-deep transition-[width] duration-base ease-standard lg:flex",
        collapsed ? "w-[var(--sidebar-w-collapsed)]" : "w-[var(--sidebar-w)]",
      )}
    >
      <div className={cn("flex h-[var(--nav-h)] shrink-0 items-center border-b border-line", collapsed ? "justify-center" : "px-4")}>
        <Link href="/" aria-label="Vakeel-Sahayak home" data-testid="brand-home" onClick={markRouteFocus} className="rounded-sm no-underline">
          <Logo markOnly={collapsed} />
        </Link>
      </div>
      <nav aria-label="Primary" className={cn("flex-1 overflow-y-auto py-3", collapsed ? "px-2" : "px-3")}>
        <NavList collapsed={collapsed} />
      </nav>
      <div className={cn("border-t border-line p-2", collapsed && "flex justify-center", inCase && "hidden")}>
        <button
          type="button"
          onClick={toggleCollapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          className={cn(
            "flex h-8 items-center gap-2 rounded-md text-sm text-ink-muted transition-colors duration-fast hover:bg-ink/[0.06] hover:text-ink",
            collapsed ? "w-9 justify-center" : "w-full px-2.5",
          )}
        >
          {collapsed ? <PanelLeftOpen aria-hidden className="size-[18px]" /> : <><PanelLeftClose aria-hidden className="size-[18px]" /><span>Collapse</span></>}
        </button>
      </div>
    </aside>
  );
}
