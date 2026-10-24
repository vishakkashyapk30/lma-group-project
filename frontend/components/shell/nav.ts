// The app's destinations. One list drives the sidebar, the mobile drawer and the command palette.
import { BookOpen, FolderOpen, HelpCircle, Inbox, type LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Extra path prefixes that count as "inside" this destination. */
  also?: readonly string[];
  hint: string;
}

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/cases", label: "Cases", icon: FolderOpen, also: ["/case"], hint: "All matters, urgent first" },
  { href: "/desk", label: "Batch desk", icon: Inbox, hint: "Rank a folder of case files" },
  { href: "/library", label: "Precedent library", icon: BookOpen, hint: "Search judgments and compare IPC with BNS" },
  { href: "/help", label: "Help", icon: HelpCircle, also: ["/about"], hint: "Shortcuts, method and limits" },
];

export function isActive(item: NavItem, path: string): boolean {
  const hit = (p: string) => path === p || path.startsWith(`${p}/`);
  return hit(item.href) || (item.also ?? []).some(hit);
}
