"use client";
// The case-file page viewer body (loaded by PdfViewer through next/dynamic, ssr: false). Three page sources:
//  - a PDF counsel dropped in this session (react-pdf, PdfCanvas), pages numbered like the file;
//  - a page image from the backend (GET /files/{doc}/pages/{n});
//  - demo mode: the IngestionReport's pages as paper-like facsimiles with real Hindi text.
// Every source supports the same highlight: pick a dossier field or a citation chip and the page scrolls to the box.
import dynamic from "next/dynamic";
import { ChevronLeft, ChevronRight, Languages, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Button } from "@/components/ui/button";
import { getPage, type PageSource } from "@/lib/api";
import { DOC_TYPE_LABELS, langLabel } from "@/lib/labels";
import type { DocumentEntry, MockPage, MockPageLine, SelectedSource } from "@/lib/types";
import { prefersReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { errorMessage } from "@/lib/errors";
import { A4, HighlightBox, LazyPage, isBox } from "./pdfShared";

const PdfCanvas = dynamic(() => import("./PdfCanvas"), {
  ssr: false,
  loading: () => <p className="p-4 text-sm text-ink-soft">Loading the PDF viewer…</p>,
});

export interface PdfPagesProps {
  caseId: string;
  doc: DocumentEntry | null;
  selection: SelectedSource | null;
  /** Increments on every selection so choosing the same source scrolls again. */
  nonce: number;
  /** Local object URL of the PDF counsel dropped in (react-pdf). */
  pdfUrl?: string | null;
  onClear?: () => void;
  className?: string;
}

const DEVANAGARI = /[ऀ-ॿ]/;

/* ── Mock page (demo mode) ──────────────────────────────────────────────────────────────────────────────────────── */

function lineStyle(line: MockPageLine, page: MockPage): CSSProperties {
  const [x0, y0, x1, y1] = line.box;
  const h = y1 - y0;
  const pts = line.style === "heading" ? Math.min(h * 0.62, 19) : Math.min(Math.max(h * 0.5, 8), 15);
  return {
    left: `${(x0 / page.width) * 100}%`,
    top: `${(y0 / page.height) * 100}%`,
    width: `${((x1 - x0) / page.width) * 100}%`,
    height: `${(h / page.height) * 100}%`,
    fontSize: `${(pts / page.width) * 100}cqw`,
    lineHeight: 1.2,
  };
}

function MockPaper({ page, showEn, selection }: { page: MockPage; showEn: boolean; selection: SelectedSource | null }): ReactElement {
  const selected = selection && selection.doc_id === page.doc_id && selection.page === page.page && isBox(selection.box) ? selection : null;
  return (
    <div className="relative w-full" style={{ aspectRatio: `${page.width} / ${page.height}`, containerType: "inline-size" }}>
      <div
        className="absolute inset-0 origin-center"
        style={page.skew ? { transform: `rotate(${page.skew}deg) scale(0.985)` } : undefined}
      >
        <div
          className="absolute inset-0 text-ink"
          style={page.unreadable ? { filter: "blur(2.4px)" } : undefined}
          aria-hidden={page.unreadable ? true : undefined}
        >
          {page.lines.map((line, i) => {
            const hindi = DEVANAGARI.test(line.text);
            const text = showEn && line.text_en ? line.text_en : line.text;
            const asHindi = hindi && !(showEn && line.text_en);
            return (
              <div
                key={i}
                lang={asHindi ? "hi" : "en"}
                style={lineStyle(line, page)}
                className={cn(
                  "absolute overflow-hidden whitespace-nowrap",
                  asHindi ? "font-devanagari-body" : "font-sans",
                  line.style === "heading" && "text-center font-display font-semibold uppercase tracking-wide text-oxblood",
                  line.style === "table" && "font-mono",
                  line.style === "signature" && "text-right font-display italic text-ink-soft",
                  line.style === "stamp" &&
                    "flex items-center justify-center -rotate-6 rounded-[3px] border-2 border-maroon/70 text-center font-mono font-semibold uppercase text-maroon/80",
                  line.handwritten && "font-display italic text-indigo",
                  showEn && line.text_en && "italic",
                )}
              >
                {text}
              </div>
            );
          })}
        </div>
        {page.unreadable ? (
          <div className="absolute inset-x-6 top-[38%] z-[5] flex flex-col items-center gap-2 rounded-md border border-sindoor/50 bg-cream/95 p-3 text-center shadow-sm">
            <StatusBadge status="UNREADABLE" kind="page" />
            <p className="text-xs text-ink-soft">Every route failed on this page. Munshi has asked counsel for a clearer copy.</p>
          </div>
        ) : null}
        {selected && isBox(selected.box) ? (
          <HighlightBox
            box={selected.box}
            width={page.width}
            height={page.height}
            label={`Source${selected.origin ? ` for ${selected.origin}` : ""}: ${selected.quote ?? "highlighted region"}`}
          />
        ) : null}
      </div>
      <span aria-hidden className="absolute bottom-1.5 right-3 font-mono text-[length:2cqw] text-ink-muted">
        {page.doc_id} · {page.page}
      </span>
    </div>
  );
}

/* ── One page: image or mock ────────────────────────────────────────────────────────────────────────────────────── */

function PageView({
  caseId, docId, pageNo, showEn, selection, label,
}: {
  caseId: string; docId: string; pageNo: number; showEn: boolean; selection: SelectedSource | null; label: string;
}): ReactElement {
  const [source, setSource] = useState<PageSource | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setSource(null);
    setFailure(null);
    getPage(caseId, docId, pageNo)
      .then((s) => !cancelled && setSource(s))
      .catch((e: unknown) => !cancelled && setFailure(errorMessage(e)));
    return () => {
      cancelled = true;
    };
  }, [caseId, docId, pageNo]);

  if (failure) {
    return (
      <div className="grid min-h-48 place-items-center p-6 text-center text-sm text-ink-soft">
        <p>
          Page {pageNo} of {docId} is not available to preview here.
          <span className="mt-1 block text-xs text-ink-muted">{failure}</span>
        </p>
      </div>
    );
  }
  if (!source) return <div className="grid min-h-48 animate-breathe place-items-center text-sm text-ink-soft">Loading page {pageNo}…</div>;
  if (source.kind === "mock") return <MockPaper page={source.page} showEn={showEn} selection={selection} />;

  const w = imgSize?.w ?? A4.width;
  const h = imgSize?.h ?? A4.height;
  const selected = selection && selection.doc_id === docId && selection.page === pageNo && isBox(selection.box) ? selection : null;
  return (
    <div className="relative">
      {/* eslint-disable-next-line @next/next/no-img-element -- page images come from the case API, not the build */}
      <img
        src={source.url}
        alt={`${label}, scanned page`}
        className="block h-auto w-full"
        onLoad={(e) => {
          const img = e.currentTarget;
          // Boxes are in PDF points: scale the image's aspect ratio onto an A4-wide page.
          if (img.naturalWidth) setImgSize({ w: A4.width, h: Math.round((A4.width * img.naturalHeight) / img.naturalWidth) });
        }}
      />
      {selected && isBox(selected.box) ? (
        <HighlightBox box={selected.box} width={w} height={h} label={`Source: ${selected.quote ?? "highlighted region"}`} />
      ) : null}
    </div>
  );
}

/* ── The viewer body ────────────────────────────────────────────────────────────────────────────────────────────── */

export default function PdfPages({ caseId, doc, selection, nonce, pdfUrl, onClear, className }: PdfPagesProps): ReactElement {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [showEn, setShowEn] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const [pageIdx, setPageIdx] = useState(0);

  const pages = useMemo(() => {
    if (!doc) return null;
    const [first, last] = [doc.pages[0] ?? 1, doc.pages[doc.pages.length - 1] ?? doc.pages[0] ?? 1];
    return Array.from({ length: Math.max(1, last - first + 1) }, (_, i) => first + i);
  }, [doc]);

  const docLabel = doc ? `${DOC_TYPE_LABELS[doc.type]} (${doc.doc_id})` : "Uploaded bundle";
  const docId = doc?.doc_id ?? "file";
  const hasHindi = doc ? doc.lang === "hi" || doc.lang === "mixed" : false;
  const activeSelection = selection && (!doc || selection.doc_id === doc.doc_id) ? selection : null;

  useEffect(() => setPageIdx(0), [doc?.doc_id]);

  // Scroll to the selected source box (or its page) whenever a source is chosen.
  useEffect(() => {
    if (!activeSelection || nonce === 0) return;
    const root = scrollRef.current;
    if (!root) return;
    const wantsBox = isBox(activeSelection.box);
    let frame = 0;
    let tries = 0;
    let settled: ReturnType<typeof setTimeout> | null = null;
    const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";

    const scrollTo = (el: Element, center: boolean) => {
      const r = root.getBoundingClientRect();
      const e = el.getBoundingClientRect();
      const offset = center ? root.clientHeight / 2 - e.height / 2 : 12;
      root.scrollTo({ top: Math.max(0, root.scrollTop + (e.top - r.top) - offset), behavior });
    };

    const run = () => {
      const highlight = root.querySelector("[data-highlight]");
      if (highlight) {
        scrollTo(highlight, true);
        settled = setTimeout(() => {
          const again = root.querySelector("[data-highlight]");
          if (again) scrollTo(again, true);
        }, 350);
        return;
      }
      const pageEl = root.querySelector(`[data-page-id="${activeSelection.doc_id}-${activeSelection.page}"]`);
      if (pageEl && !wantsBox) {
        scrollTo(pageEl, false);
        return;
      }
      if (tries++ < 60) frame = requestAnimationFrame(run);
      else if (pageEl) scrollTo(pageEl, false);
    };
    run();
    return () => {
      cancelAnimationFrame(frame);
      if (settled) clearTimeout(settled);
    };
    // Only a new selection should scroll.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce]);

  const goToPage = useCallback(
    (idx: number) => {
      if (!pages) return;
      const next = Math.min(pages.length - 1, Math.max(0, idx));
      setPageIdx(next);
      const root = scrollRef.current;
      const el = root?.querySelector(`[data-page-id="${docId}-${pages[next]}"]`);
      if (root && el) {
        const r = root.getBoundingClientRect();
        root.scrollTo({ top: root.scrollTop + (el.getBoundingClientRect().top - r.top) - 12, behavior: prefersReducedMotion() ? "auto" : "smooth" });
      }
    },
    [pages, docId],
  );

  return (
    <div className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div className="flex flex-wrap items-center gap-2 border-b border-line bg-parchment/70 px-3 py-1.5">
        <p className="min-w-0 flex-1 truncate font-display text-sm font-semibold text-maroon" title={docLabel}>
          {docLabel}
          {doc ? <span className="ml-2 font-sans text-xs font-normal text-ink-soft">{langLabel(doc.lang)}</span> : null}
        </p>
        {pages && pages.length > 1 ? (
          <div className="flex items-center gap-1" role="group" aria-label="Page navigation">
            <Button variant="ghost" size="icon-sm" onClick={() => goToPage(pageIdx - 1)} disabled={pageIdx === 0} aria-label="Previous page">
              <ChevronLeft aria-hidden />
            </Button>
            <span className="min-w-[4.5rem] text-center font-mono text-xs text-ink-soft" aria-live="polite">
              p.{pages[pageIdx]} of {pages[pages.length - 1]}
            </span>
            <Button variant="ghost" size="icon-sm" onClick={() => goToPage(pageIdx + 1)} disabled={pageIdx >= pages.length - 1} aria-label="Next page">
              <ChevronRight aria-hidden />
            </Button>
          </div>
        ) : null}
        {hasHindi ? (
          <Button
            variant={showEn ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={showEn}
            onClick={() => setShowEn((v) => !v)}
            title="Show the English translation of Hindi lines (demo pages)"
          >
            <Languages aria-hidden /> English
          </Button>
        ) : null}
      </div>

      {activeSelection ? (
        <div className="flex items-start gap-2 border-b border-gold/40 bg-gold/10 px-3 py-2 text-sm" role="status">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold uppercase tracking-caps text-maroon">
              Source{activeSelection.origin ? `: ${activeSelection.origin}` : ""} · {activeSelection.doc_id} · p.{activeSelection.page}
            </p>
            {activeSelection.quote ? (
              <p
                lang={DEVANAGARI.test(activeSelection.quote) ? "hi" : undefined}
                className={cn("mt-0.5 line-clamp-3 text-ink", DEVANAGARI.test(activeSelection.quote) && "font-devanagari-body leading-devanagari")}
              >
                “{activeSelection.quote}”
              </p>
            ) : null}
            {activeSelection.quote_en ? <p className="mt-0.5 line-clamp-2 text-xs italic text-ink-soft">{activeSelection.quote_en}</p> : null}
          </div>
          {onClear ? (
            <Button variant="ghost" size="icon-sm" onClick={onClear} aria-label="Clear the highlighted source">
              <X aria-hidden />
            </Button>
          ) : null}
        </div>
      ) : null}

      <div
        ref={scrollRef}
        data-viewer-scroll=""
        data-lenis-prevent=""
        role="region"
        aria-label={`Pages of ${docLabel}`}
        tabIndex={0}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain bg-parchment-deep/60 p-3"
      >
        {pdfUrl && !pdfError ? (
          <PdfCanvas url={pdfUrl} pages={pages} selection={activeSelection} docLabel={docLabel} onError={setPdfError} />
        ) : !doc ? (
          <p className="p-6 text-center text-sm text-ink-soft">Choose a document above, or select a source in the dossier, to see its page here.</p>
        ) : (
          <div className="flex flex-col gap-4">
            {pdfError ? <p className="text-xs text-haldi">The local PDF preview failed ({pdfError}); showing the filed pages instead.</p> : null}
            {(pages ?? []).map((n) => (
              <LazyPage
                key={n}
                pageId={`${doc.doc_id}-${n}`}
                ratio={A4.height / A4.width}
                force={activeSelection?.page === n}
                label={`${docLabel}, page ${n}`}
              >
                <PageView
                  caseId={caseId}
                  docId={doc.doc_id}
                  pageNo={n}
                  showEn={showEn}
                  selection={activeSelection}
                  label={`${docLabel}, page ${n}`}
                />
              </LazyPage>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
