"use client";
// react-pdf rendering of a PDF the counsel dropped in this session. Loaded on demand through next/dynamic (ssr: false)
// by PdfPages, so PDF.js is not fetched in demo mode or on the server.
import { useEffect, useRef, useState, type ReactElement } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { SelectedSource } from "@/lib/types";
import { A4, HighlightBox, LazyPage, isBox } from "./pdfShared";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

export interface PdfCanvasProps {
  url: string;
  /** File pages to show (the active document's range); null shows the whole file. */
  pages: number[] | null;
  selection: SelectedSource | null;
  docLabel: string;
  onError?: (message: string) => void;
}

export default function PdfCanvas({ url, pages, selection, docLabel, onError }: PdfCanvasProps): ReactElement {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(420);
  const [numPages, setNumPages] = useState(0);
  const [sizes, setSizes] = useState<Record<number, { w: number; h: number }>>({});

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const measure = () => setWidth(Math.max(200, Math.floor(el.clientWidth)));
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const shown = pages ?? Array.from({ length: Math.min(numPages, 200) }, (_, i) => i + 1);

  return (
    <div ref={wrapRef} className="flex flex-col gap-4">
      <Document
        file={url}
        onLoadSuccess={(d) => setNumPages(d.numPages)}
        onLoadError={(e) => onError?.(e.message)}
        loading={<p className="p-4 text-sm text-ink-soft">Opening the PDF…</p>}
        error={<p className="p-4 text-sm text-sindoor">This PDF could not be opened. Check that it is not locked or damaged.</p>}
        className="flex flex-col gap-4"
      >
        {shown.map((n) => {
          const size = sizes[n] ?? { w: A4.width, h: A4.height };
          const selected = selection && selection.page === n && isBox(selection.box) ? selection : null;
          return (
            <LazyPage
              key={n}
              pageId={`${selection?.doc_id ?? "file"}-${n}`}
              ratio={size.h / size.w}
              force={selection?.page === n}
              label={`${docLabel}, page ${n}`}
            >
              <Page
                pageNumber={n}
                width={width}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                onLoadSuccess={(p) =>
                  setSizes((prev) => (prev[n] ? prev : { ...prev, [n]: { w: p.originalWidth, h: p.originalHeight } }))
                }
                loading={<div className="grid h-60 place-items-center text-sm text-ink-soft">Page {n}…</div>}
              />
              {selected && isBox(selected.box) ? (
                <HighlightBox
                  box={selected.box}
                  width={size.w}
                  height={size.h}
                  label={`Source${selected.origin ? ` for ${selected.origin}` : ""}: ${selected.quote ?? "highlighted region"}`}
                />
              ) : null}
            </LazyPage>
          );
        })}
      </Document>
    </div>
  );
}
