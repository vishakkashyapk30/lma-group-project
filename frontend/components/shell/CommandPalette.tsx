"use client";
// Command palette (Ctrl/Cmd+K): jump to a case, a page or an action. Type to filter, arrows to move, Enter to run.
// Implements the combobox + listbox pattern, so screen readers announce the active option.
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { useRouter } from "next/navigation";
import { CornerDownLeft, FileText, Home, Plus, Search, SidebarClose, Zap, type LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import { useToast } from "@/components/ui/toast";
import { listCases } from "@/lib/api";
import { toggleReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "./nav";
import { useShell } from "./ShellProvider";

interface Entry {
  id: string;
  group: "Actions" | "Pages" | "Cases";
  label: string;
  hint?: string;
  icon: LucideIcon;
  keywords?: string;
  run: () => void;
}

const GROUPS: readonly Entry["group"][] = ["Actions", "Pages", "Cases"];

function matches(entry: Entry, tokens: string[]): number {
  if (tokens.length === 0) return 1;
  const label = entry.label.toLowerCase();
  const hay = `${label} ${entry.hint ?? ""} ${entry.keywords ?? ""}`.toLowerCase();
  if (!tokens.every((t) => hay.includes(t))) return 0;
  return label.startsWith(tokens[0]!) ? 3 : label.includes(tokens[0]!) ? 2 : 1;
}

export function CommandPalette(): ReactElement {
  const router = useRouter();
  const toast = useToast();
  const { paletteOpen, setPaletteOpen, setNewCaseOpen, toggleCollapsed } = useShell();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [cases, setCases] = useState<{ id: string; title: string }[]>([]);
  const listRef = useRef<HTMLUListElement>(null);

  useEffect(() => {
    if (!paletteOpen) return;
    setQuery("");
    setActive(0);
    let live = true;
    listCases()
      .then((list) => live && setCases(list.map((c) => ({ id: c.case_id, title: c.title }))))
      .catch(() => live && setCases([]));
    return () => { live = false; };
  }, [paletteOpen]);

  const entries = useMemo<Entry[]>(() => {
    const go = (href: string) => () => router.push(href);
    return [
      { id: "new-case", group: "Actions", label: "New case", hint: "Start a matter and upload the file", icon: Plus, keywords: "create add start", run: () => setNewCaseOpen(true) },
      {
        id: "motion", group: "Actions", label: "Reduce motion", hint: "Switch animations off or on", icon: Zap, keywords: "animation accessibility",
        run: () => toast(toggleReducedMotion() ? "Motion reduced" : "Motion restored"),
      },
      { id: "sidebar", group: "Actions", label: "Collapse or expand the sidebar", icon: SidebarClose, keywords: "navigation menu", run: toggleCollapsed },
      ...NAV_ITEMS.map<Entry>((n) => ({ id: `page-${n.href}`, group: "Pages", label: n.label, hint: n.hint, icon: n.icon, keywords: "go open", run: go(n.href) })),
      { id: "page-home", group: "Pages", label: "Product overview", hint: "The landing page", icon: Home, keywords: "go open home about", run: go("/") },
      ...cases.map<Entry>((c) => ({ id: `case-${c.id}`, group: "Cases", label: c.title, hint: c.id, icon: FileText, keywords: c.id, run: go(`/case/${c.id}`) })),
    ];
  }, [cases, router, setNewCaseOpen, toast, toggleCollapsed]);

  const results = useMemo(() => {
    const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const scored = entries.map((e) => ({ e, s: matches(e, tokens) })).filter((x) => x.s > 0);
    const out: Entry[] = [];
    for (const g of GROUPS) {
      const inGroup = scored.filter((x) => x.e.group === g).sort((a, b) => b.s - a.s).map((x) => x.e);
      out.push(...inGroup.slice(0, g === "Cases" ? (tokens.length ? 8 : 5) : 20));
    }
    return out;
  }, [entries, query]);

  useEffect(() => setActive(0), [query]);
  useEffect(() => {
    listRef.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView?.({ block: "nearest" });
  }, [active, results]);

  const run = (e: Entry | undefined) => {
    if (!e) return;
    setPaletteOpen(false);
    e.run();
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Home") { e.preventDefault(); setActive(0); }
    else if (e.key === "End") { e.preventDefault(); setActive(Math.max(results.length - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); run(results[active]); }
  };

  return (
    <DialogPrimitive.Root open={paletteOpen} onOpenChange={setPaletteOpen}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-modal bg-ink/40 data-[state=open]:animate-fade-in data-[state=closed]:animate-fade-out" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed left-1/2 top-[12vh] z-modal w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 overflow-hidden rounded-lg border border-line bg-cream shadow-lg data-[state=open]:animate-scale-in data-[state=closed]:animate-fade-out"
        >
          <DialogPrimitive.Title className="sr-only">Search cases, pages and actions</DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b border-line px-3">
            <Search aria-hidden className="size-4 shrink-0 text-ink-muted" />
            <input
              autoFocus
              role="combobox"
              aria-expanded="true"
              aria-controls="palette-list"
              aria-activedescendant={results[active] ? `palette-${results[active]!.id}` : undefined}
              aria-label="Search cases, pages and actions"
              placeholder="Search cases, pages and actions"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
              className="h-12 w-full bg-transparent text-base text-ink outline-none placeholder:text-ink-muted"
            />
          </div>
          <ul ref={listRef} id="palette-list" role="listbox" aria-label="Results" className="max-h-[min(24rem,60vh)] overflow-y-auto p-1.5">
            {results.length === 0 ? <li role="presentation" className="px-3 py-6 text-center text-sm text-ink-soft">Nothing matches &ldquo;{query}&rdquo;.</li> : null}
            {results.map((r, i) => {
              const Icon = r.icon;
              const showGroup = i === 0 || results[i - 1]!.group !== r.group;
              return (
                <li key={r.id} role="presentation">
                  {showGroup ? <p role="presentation" className="px-2.5 pb-1 pt-2 text-xs font-semibold text-ink-muted">{r.group}</p> : null}
                  <div
                    id={`palette-${r.id}`}
                    role="option"
                    aria-selected={i === active}
                    onMouseMove={() => setActive(i)}
                    onClick={() => run(r)}
                    className={cn("flex cursor-pointer items-center gap-3 rounded-md px-2.5 py-2 text-sm", i === active ? "bg-parchment-deep" : "")}
                  >
                    <Icon aria-hidden className="size-4 shrink-0 text-ink-muted" />
                    <span className="min-w-0 flex-1 truncate font-medium text-ink">{r.label}</span>
                    {r.hint ? <span className={cn("hidden truncate text-xs text-ink-muted sm:block sm:max-w-[45%]", r.group === "Cases" && "font-mono")}>{r.hint}</span> : null}
                    {i === active ? <CornerDownLeft aria-hidden className="size-3.5 shrink-0 text-ink-muted" /> : null}
                  </div>
                </li>
              );
            })}
          </ul>
          <p className="border-t border-line px-3 py-2 text-xs text-ink-muted">Arrow keys to move, Enter to open, Esc to close.</p>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
