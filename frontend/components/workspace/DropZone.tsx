"use client";
// Add documents: drag and drop or a file picker, plus dictation (plan §13.5, §4.5). Keyboard: the zone is a button.
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
      setStatus(`Sending ${files.length} file${files.length === 1 ? "" : "s"}…`);
      const res = await ws.upload(files);
      setStatus(res ? `Added ${res.accepted.length} file${res.accepted.length === 1 ? "" : "s"}. Reading them now.` : "The upload did not go through.");
    },
    [caseId, ws],
  );

  const sendAudio = useCallback(
    async (blob: Blob, name: string) => {
      setStatus("Transcribing your dictation…");
      setDictation("Transcribing");
      const res = await ws.uploadAudio(blob, name);
      setDictation(res ? "Heard" : "");
      setStatus(res ? "Dictation received. The dates and sections it heard will appear in the chat for you to confirm." : "The dictation did not go through.");
    },
    [ws],
  );

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setOver(false);
    void send(Array.from(e.dataTransfer.files));
  };

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-lg border border-dashed transition-colors duration-fast",
          over ? "border-maroon bg-maroon/[0.04]" : "border-line-strong bg-cream hover:border-ink-soft",
        )}
      >
        <button
          type="button"
          id="add-files"
          aria-label="Add files to this case: drop them here or press Enter to choose"
          aria-describedby={`${inputId}-hint`}
          onClick={() => fileInput.current?.click()}
          className={cn(
            "flex w-full cursor-pointer items-center gap-3 rounded-lg px-4",
            compact ? "py-3 text-left" : "flex-col justify-center py-12 text-center",
          )}
        >
          {ws.uploading ? (
            <Loader2 aria-hidden className="size-5 shrink-0 animate-spin text-ink-soft" />
          ) : (
            <FileUp aria-hidden className={cn("shrink-0 text-ink-soft", compact ? "size-5" : "size-7")} strokeWidth={1.6} />
          )}
          <span className="min-w-0">
            <span className="block font-medium text-ink">{over ? "Release to add" : compact ? "Add more documents" : "Drop the case papers here, or choose files"}</span>
            <span id={`${inputId}-hint`} className="block text-sm text-ink-soft">
              PDF, photos of pages or Word. Hindi and English, scanned or typed.
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
          label="Dictate what you know"
          variant="ghost"
          size="sm"
          onUnavailable={setStatus}
          onRecordingChange={(r) => {
            if (r) setDictation("Recording");
          }}
        />
        <Button variant="ghost" size="sm" onClick={() => audioInput.current?.click()} disabled={ws.uploading}>
          <Headphones aria-hidden /> Upload audio
        </Button>
        <span data-testid="dictation-status" role="status" aria-live="polite" className="text-sm text-ink-soft">
          {dictation}
        </span>
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
        {status ? <p className="min-w-0 basis-full text-sm text-ink-soft" aria-hidden>{status}</p> : null}
      </div>
    </div>
  );
}

export default DropZone;
