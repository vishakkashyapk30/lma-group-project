"use client";
// Shell state shared by the sidebar, top bar, palette and pages: command palette, new-case dialog, mobile drawer and
// the collapsed sidebar (remembered in localStorage). Also owns the Ctrl/Cmd+K shortcut.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactElement, type ReactNode } from "react";

interface ShellState {
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;
  newCaseOpen: boolean;
  setNewCaseOpen: (open: boolean) => void;
  drawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;
  collapsed: boolean;
  toggleCollapsed: () => void;
}

const noop = () => {};
const ShellContext = createContext<ShellState>({
  paletteOpen: false, setPaletteOpen: noop, newCaseOpen: false, setNewCaseOpen: noop,
  drawerOpen: false, setDrawerOpen: noop, collapsed: false, toggleCollapsed: noop,
});

export function useShell(): ShellState {
  return useContext(ShellContext);
}

const KEY = "vs:sidebar-collapsed";

export function ShellProvider({ children }: { children: ReactNode }): ReactElement {
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [newCaseOpen, setNewCaseOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(KEY) === "1");
    } catch {
      /* storage unavailable: start expanded */
    }
  }, []);

  const toggleCollapsed = useCallback(() => {
    setCollapsed((c) => {
      try {
        window.localStorage.setItem(KEY, c ? "0" : "1");
      } catch {
        /* ignore */
      }
      return !c;
    });
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const value = useMemo(
    () => ({ paletteOpen, setPaletteOpen, newCaseOpen, setNewCaseOpen, drawerOpen, setDrawerOpen, collapsed, toggleCollapsed }),
    [paletteOpen, newCaseOpen, drawerOpen, collapsed, toggleCollapsed],
  );
  return <ShellContext.Provider value={value}>{children}</ShellContext.Provider>;
}
