"use client";
// The sidebar as a drawer on narrow screens (Radix dialog: focus trapped, Escape closes).
import * as DialogPrimitive from "@radix-ui/react-dialog";
import Link from "next/link";
import { X } from "lucide-react";
import type { ReactElement } from "react";
import { Logo } from "@/components/common/Logo";
import { markRouteFocus } from "./routeFocus";
import { NavList } from "./Sidebar";
import { useShell } from "./ShellProvider";

export function MobileDrawer(): ReactElement {
  const { drawerOpen, setDrawerOpen } = useShell();
  return (
    <DialogPrimitive.Root open={drawerOpen} onOpenChange={setDrawerOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-drawer bg-ink/40 data-[state=open]:animate-fade-in data-[state=closed]:animate-fade-out lg:hidden" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 left-0 z-drawer flex w-[17rem] max-w-[85vw] flex-col border-r border-line bg-parchment-deep data-[state=open]:animate-slide-in-left data-[state=closed]:animate-slide-out-left lg:hidden"
        >
          <DialogPrimitive.Title className="sr-only">Menu</DialogPrimitive.Title>
          <div className="flex h-[var(--nav-h)] items-center justify-between border-b border-line px-4">
            <Link href="/" aria-label="Vakeel-Sahayak home" data-testid="brand-home" onClick={() => { markRouteFocus(); setDrawerOpen(false); }} className="rounded-sm no-underline"><Logo /></Link>
            <DialogPrimitive.Close className="grid size-8 place-items-center rounded-md text-ink-soft hover:bg-ink/[0.06]">
              <X aria-hidden className="size-4" />
              <span className="sr-only">Close menu</span>
            </DialogPrimitive.Close>
          </div>
          <nav aria-label="Primary" className="flex-1 overflow-y-auto p-3">
            <NavList onNavigate={() => setDrawerOpen(false)} />
          </nav>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
