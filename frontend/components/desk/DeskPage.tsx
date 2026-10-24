"use client";
// Batch desk: upload a folder or zip, triage board, open a case; Pairokar's cause-list bars while scoring (plan §11, §13.5).
import { FolderUp, FileArchive } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ChangeEvent, type DragEvent, type ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { PageHeader } from "@/components/common/PageHeader";
import { Button, Skeleton } from "@/components/ui";
import { deskUpload, getDeskBoard } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { cn } from "@/lib/utils";
import type { TriageCard } from "@/lib/types";
import { TriageBoard } from "./TriageBoard";
import { zipFolder } from "./zip";

export interface DeskPageProps {
  className?: string;
}

export function DeskPage({ className }: DeskPageProps): ReactElement {
  const [cards, setCards] = useState<TriageCard[] | null>(null);
  const [scoring, setScoring] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const zipRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setCards((await getDeskBoard()).cards);
    } catch (e) {
      setError(errorMessage(e));
      setCards([]);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const send = useCallback(async (build: () => Promise<File>) => {
    setScoring(true);
    setError(null);
    setMessage(null);
    try {
      const file = await build();
      const ids = await deskUpload(file);
      await load();
      setMessage(`Pairokar scored ${ids.length} ${ids.length === 1 ? "case" : "cases"} from ${file.name}.`);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setScoring(false);
    }
  }, [load]);

  function onZip(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (f) void send(async () => f);
  }
  function onFolder(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";
    if (files.length) void send(() => zipFolder(files));
  }
  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDrag(false);
    const f = Array.from(e.dataTransfer.files).find((x) => /\.zip$/i.test(x.name));
    if (f) void send(async () => f);
    else setError("Drop a .zip file, or use Choose folder.");
  }

  return (
    <div className={cn("mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10", className)}>
      <PageHeader
        title="Batch desk"
        description="Add a folder of undertrial files. Each file is read and checked, then ranked: legal deadlines first, then days past a threshold, then custody length. Each case still needs its own approval."
      />

      <section aria-label="Upload" className="mt-6">
        <div
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-start justify-center gap-3 rounded-lg border border-dashed bg-cream p-6 transition-colors duration-fast",
            drag ? "border-maroon bg-parchment-deep" : "border-line-strong/60",
          )}
        >
          <h2 className="font-display text-xl font-semibold text-ink">Upload case files</h2>
          <p className="text-sm text-ink-soft">Drop a zip here, or choose a zip or a folder of PDFs. Nothing is exported; the board only ranks work.</p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => zipRef.current?.click()} disabled={scoring}><FileArchive aria-hidden /> Choose zip</Button>
            <Button variant="secondary" onClick={() => folderRef.current?.click()} disabled={scoring}><FolderUp aria-hidden /> Choose folder</Button>
          </div>
          <input ref={zipRef} type="file" data-testid="desk-upload-input" accept=".zip,application/zip" className="sr-only" tabIndex={-1} aria-label="Zip file" onChange={onZip} />
          <input
            ref={folderRef}
            type="file"
            multiple
            className="sr-only"
            tabIndex={-1}
            aria-label="Folder of case files"
            onChange={onFolder}
            {...({ webkitdirectory: "", directory: "" } as Record<string, string>)}
          />
          <div role="status" aria-live="polite" className="min-h-5 text-sm">
            {scoring ? <span className="font-semibold text-maroon">Scoring files…</span> : null}
            {message ? <span className="text-neem">{message}</span> : null}
          </div>
          {error ? <p role="alert" className="text-sm text-sindoor">{error}</p> : null}
          <AgentSignature
            agent="PAIROKAR"
            mode={scoring ? "working" : "static"}
            active={scoring}
            statusText={scoring ? "Scoring and ranking cases" : "Cause list ready"}
          />
        </div>
      </section>

      <section aria-label="Triage board" className="mt-8">
        <h2 className="mb-3 font-display text-xl font-semibold">Triage board</h2>
        {cards === null ? (
          <div className="space-y-2" aria-busy="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-24" />)}</div>
        ) : (
          <TriageBoard cards={cards} />
        )}
        <p className="mt-4 text-xs text-ink-muted">
          Ranking explains itself with the reasons shown. It orders work and never predicts an outcome. There is no bulk export: open a case to review and approve it on its own.
        </p>
      </section>
    </div>
  );
}

export default DeskPage;
