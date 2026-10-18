"use client";
// Drop zone: drag and drop, a file picker, and a mic for dictation (plan §13.5, §4.5). Keyboard: the zone is a button.
import { FileUp, Headphones, Loader2 } from "lucide-react";
import { useCallback, useId, useRef, useState, type DragEvent, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { MicButton } from "./MicButton";
import { rememberUpload } from "./pdfShared";

export interface DropZoneProps {
  caseId: string;
  className?: string;
  /** Tighter layout for when documents are already filed. */
  compact?: boolean;
}

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.tif,.tiff,.docx,application/pdf,image/*";

export function DropZone({ caseId, className, compact = false }: DropZoneProps): ReactElement {
  const ws = useWorkspace();
  const inputId = useId();
  const fileInput = useRef<HTMLInputElement>(null);
  const audioInput = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const [status, setStatus] = useState("");
  const [dictation, setDictation] = useState<"" | "Recording" | "Transcribing" | "Heard">("");

  const send = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      rememberUpload(caseId, files);
      setStatus(`Sending ${files.length} file${files.length === 1 ? "" : "s"} to Munshi…`);
      const res = await ws.upload(files);
      setStatus(res ? `Munshi accepted ${res.accepted.length} file${res.accepted.length === 1 ? "" : "s"} and is reading them.` : "The upload did not go through.");
    },
    [caseId, ws],
  );

  const sendAudio = useCallback(
    async (blob: Blob, name: string) => {
      setStatus("Munshi is transcribing your dictation…");
      setDictation("Transcribing");
      const res = await ws.uploadAudio(blob, name);
      setDictation(res ? "Heard" : "");
      setStatus(res ? "Dictation received. Munshi will read back the dates and sections for you to confirm in the chat." : "The dictation did not go through.");
    },
    [ws],
  );

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setOver(false);
    void send(Array.from(e.dataTransfer.files));
  };

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-md border-2 border-dashed transition-colors duration-fast",
          over ? "border-maroon bg-gold/15" : "border-line-strong/70 bg-cream hover:border-maroon/70 hover:bg-parchment-deep/60",
        )}
      >
        <button
          type="button"
          aria-label="Add files to this case: drop them here or press Enter to choose"
          aria-describedby={`${inputId}-hint`}
          onClick={() => fileInput.current?.click()}
          className={cn(
            "flex w-full cursor-pointer items-center gap-3 rounded-md px-3",
            compact ? "py-2 text-left" : "flex-col justify-center py-6 text-center",
          )}
        >
          {ws.uploading ? (
            <Loader2 aria-hidden className="size-5 shrink-0 animate-spin text-maroon" />
          ) : (
            <FileUp aria-hidden className={cn("shrink-0 text-maroon", compact ? "size-5" : "size-8")} strokeWidth={1.6} />
          )}
          <span className="min-w-0">
            <span className="block font-display text-sm font-semibold text-maroon">{over ? "Release to add" : compact ? "Add files" : "Drop the bundle here"}</span>
            <span id={`${inputId}-hint`} className="block text-xs text-ink-soft">
              PDF, photos of pages or DOCX. Hindi and English, scanned or typed.
            </span>
          </span>
        </button>
        <input
          ref={fileInput}
          id={inputId}
          data-testid="upload-input"
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            const files = Array.from(e.target.files ?? []);
            e.target.value = "";
            void send(files);
          }}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <MicButton
          testId="mic-button"
          onRecorded={sendAudio}
          busy={ws.uploading}
          label="Dictate"
          variant="secondary"
          size="sm"
          onUnavailable={setStatus}
          onRecordingChange={(r) => {
            if (r) setDictation("Recording");
          }}
        />
        <span data-testid="dictation-status" role="status" aria-live="polite" className="text-xs font-semibold text-ink-soft">
          {dictation}
        </span>
        <Button variant="ghost" size="sm" onClick={() => audioInput.current?.click()} disabled={ws.uploading}>
          <Headphones aria-hidden /> Upload audio
        </Button>
        <input
          ref={audioInput}
          type="file"
          accept="audio/*"
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) void sendAudio(file, file.name);
          }}
        />
        <p className="sr-only" role="status" aria-live="polite">{status}</p>
        {status ? <p className="min-w-0 flex-1 text-xs text-ink-soft" aria-hidden>{status}</p> : null}
      </div>
    </div>
  );
}

export default DropZone;
