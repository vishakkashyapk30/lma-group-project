"use client";
// App shell: sidebar + top bar + content. The landing page (/) is outside it and renders full width.
import { usePathname } from "next/navigation";
import type { ReactElement, ReactNode } from "react";
import { NewCaseDialog } from "@/components/cases/NewCaseDialog";
import { PageTransition } from "@/components/motion/PageTransition";
import { ToastProvider } from "@/components/ui/toast";
import { CommandPalette } from "./CommandPalette";
import { MobileDrawer } from "./MobileDrawer";
import { useRouteFocus } from "./routeFocus";
import { ShellProvider } from "./ShellProvider";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

export function AppShell({ children }: { children: ReactNode }): ReactElement {
  const path = usePathname() ?? "/";
  const isLanding = path === "/";
  useRouteFocus();
  return (
    <ToastProvider>
      {isLanding ? (
        <main id="main" tabIndex={-1} className="outline-none"><PageTransition routeKey={path}>{children}</PageTransition></main>
      ) : (
        <ShellProvider>
          <div className="flex min-h-dvh">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <TopBar />
              <main id="main" tabIndex={-1} className="min-w-0 flex-1 outline-none"><PageTransition routeKey={path}>{children}</PageTransition></main>
            </div>
          </div>
          <MobileDrawer />
          <CommandPalette />
          <NewCaseDialog />
        </ShellProvider>
      )}
    </ToastProvider>
  );
}
