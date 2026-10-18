"use client";
// Shared pieces of the case-file viewer: the highlight overlay, a lazy page frame and the local bundle preview (the PDF
// counsel just dropped in, kept as an object URL so react-pdf can show it before the backend has page images).
import { useEffect, useRef, useState, useSyncExternalStore, type ReactElement, type ReactNode } from "react";
import type { Box } from "@/lib/types";
import { cn } from "@/lib/utils";

/** A4 in PDF points, the fallback page size. */
export const A4 = { width: 595, height: 842 } as const;

/* ── Local bundle preview store ─────────────────────────────────────────────────────────────────────────────────── */

export interface BundlePreview {
  caseId: string;
  name: string;
  url: string;
}

let preview: BundlePreview | null = null;
const listeners = new Set<() => void>();

function emit(): void {
  listeners.forEach((l) => l());
}

/** Remember the first PDF among freshly uploaded files as this case's local preview (page numbers match file pages). */
export function rememberUpload(caseId: string, files: readonly File[]): void {
  const pdf = files.find((f) => f.type === "application/pdf" || /\.pdf$/i.test(f.name));
  if (!pdf) return;
  if (preview) URL.revokeObjectURL(preview.url);
  preview = { caseId, name: pdf.name, url: URL.createObjectURL(pdf) };
  emit();
}

export function clearUploadPreview(caseId: string): void {
  if (preview && preview.caseId === caseId) {
    URL.revokeObjectURL(preview.url);
    preview = null;
    emit();
  }
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The local preview for a case, or null. */
export function useBundlePreview(caseId: string): BundlePreview | null {
  const p = useSyncExternalStore(subscribe, () => preview, () => null);
  return p && p.caseId === caseId ? p : null;
}

/* ── Highlight ──────────────────────────────────────────────────────────────────────────────────────────────────── */

export function isBox(value: unknown): value is Box {
  return Array.isArray(value) && value.length === 4 && value.every((n) => typeof n === "number");
}

export interface HighlightBoxProps {
  box: Box;
  width: number;
  height: number;
  label: string;
}

/** A gold highlight over a source box, positioned in percent of the page so it scales with the page. */
export function HighlightBox({ box, width, height, label }: HighlightBoxProps): ReactElement {
  const [x0, y0, x1, y1] = box;
  const pad = 2;
  return (
    <div
      data-highlight=""
      data-testid="pdf-highlight"
      data-box={box.join(",")}
      role="note"
      aria-label={label}
      className="pointer-events-none absolute z-10 rounded-[2px] bg-gold/30 outline outline-2 outline-maroon motion-safe:animate-breathe"
      style={{
        left: `${(Math.max(0, x0 - pad) / width) * 100}%`,
        top: `${(Math.max(0, y0 - pad) / height) * 100}%`,
        width: `${((x1 - x0 + pad * 2) / width) * 100}%`,
        height: `${((y1 - y0 + pad * 2) / height) * 100}%`,
        mixBlendMode: "multiply",
      }}
    />
  );
}

/* ── Lazy page frame ────────────────────────────────────────────────────────────────────────────────────────────── */

export interface LazyPageProps {
  /** Always render (the page holding the selected source). */
  force?: boolean;
  /** Aspect ratio of the placeholder, height / width. */
  ratio: number;
  pageId: string;
  label: string;
  children: ReactNode;
  className?: string;
}

/** Mounts its children when it nears the viewport, so a long bundle does not render every page at once. */
export function LazyPage({ force, ratio, pageId, label, children, className }: LazyPageProps): ReactElement {
  const ref = useRef<HTMLDivElement>(null);
  const [seen, setSeen] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const root = el.closest<HTMLElement>("[data-viewer-scroll]");
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setSeen(true);
          io.disconnect();
        }
      },
      { root, rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [seen]);

  const show = force || seen;
  return (
    <div
      ref={ref}
      data-page-id={pageId}
      role="group"
      aria-label={label}
      className={cn("relative mx-auto w-full overflow-hidden rounded-[3px] bg-cream shadow-md ring-1 ring-line-strong/40", className)}
      style={show ? undefined : { aspectRatio: `1 / ${ratio}` }}
    >
      {show ? children : <span className="sr-only">{label} (not loaded yet)</span>}
    </div>
  );
}
