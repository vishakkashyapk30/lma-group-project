"use client";
// Dictation (plan §4.5, flow 5): record in the browser, then hand the audio to the workspace for Munshi to transcribe.
// The audio is deleted after transcription; the button says so. Without a microphone (or permission) the caller can
// still upload an audio file.
import { Loader2, Mic, Square } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface MicButtonProps {
  /** Called with the recording when counsel stops. */
  onRecorded: (blob: Blob, fileName: string) => void | Promise<unknown>;
  disabled?: boolean;
  busy?: boolean;
  /** Visible label next to the icon (omit for an icon-only button). */
  label?: string;
  size?: "icon" | "icon-sm" | "sm" | "md";
  variant?: "ghost" | "secondary" | "pill";
  className?: string;
  /** Called with a short message when recording cannot start. */
  onUnavailable?: (message: string) => void;
  /** Called when recording starts (true) or stops (false). */
  onRecordingChange?: (recording: boolean) => void;
  /** data-testid for the button. */
  testId?: string;
}

function pickMime(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  for (const m of ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"]) {
    if (MediaRecorder.isTypeSupported(m)) return m;
  }
  return undefined;
}

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function MicButton({ onRecorded, disabled, busy, label, size = "icon", variant = "ghost", className, onUnavailable, onRecordingChange, testId }: MicButtonProps): ReactElement {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [note, setNote] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const release = useCallback(() => {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  }, []);

  useEffect(
    () => () => {
      if (recorder.current && recorder.current.state !== "inactive") {
        recorder.current.onstop = null;
        recorder.current.stop();
      }
      release();
    },
    [release],
  );

  const fail = useCallback(
    (message: string) => {
      setNote(message);
      onUnavailable?.(message);
    },
    [onUnavailable],
  );

  const start = useCallback(async () => {
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      fail("This browser cannot record audio. Upload an audio file instead.");
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.current = media;
      const mime = pickMime();
      const rec = new MediaRecorder(media, mime ? { mimeType: mime } : undefined);
      chunks.current = [];
      rec.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.current.push(e.data);
      };
      rec.onstop = () => {
        onRecordingChange?.(false);
        const type = rec.mimeType || mime || "audio/webm";
        const blob = new Blob(chunks.current, { type });
        release();
        setRecording(false);
        setNote("Recording sent to Munshi. The audio is deleted after transcription.");
        const ext = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
        if (blob.size > 0) void onRecorded(blob, `dictation.${ext}`);
      };
      recorder.current = rec;
      rec.start();
      setSeconds(0);
      setRecording(true);
      onRecordingChange?.(true);
      setNote("Recording. Speak in Hindi or English, then stop.");
      timer.current = setInterval(() => setSeconds((s) => s + 1), 1000);
    } catch {
      release();
      fail("Microphone access was blocked. Allow it in the browser, or upload an audio file instead.");
    }
  }, [fail, onRecorded, onRecordingChange, release]);

  const stop = useCallback(() => {
    if (recorder.current && recorder.current.state !== "inactive") recorder.current.stop();
  }, []);

  const text = recording ? `Stop dictation (${clock(seconds)})` : "Dictate by voice";
  return (
    <>
      <Button
        data-testid={testId}
        variant={recording ? "danger" : variant}
        size={label ? (size === "icon" || size === "icon-sm" ? "sm" : size) : size}
        onClick={recording ? stop : start}
        disabled={disabled || busy}
        aria-pressed={recording}
        aria-label={label ? undefined : text}
        title={`${text}. Audio is deleted after transcription.`}
        className={cn(recording && "motion-safe:animate-breathe", className)}
      >
        {busy ? <Loader2 aria-hidden className="animate-spin" /> : recording ? <Square aria-hidden className="fill-current" /> : <Mic aria-hidden />}
        {label ? <span>{recording ? `Stop ${clock(seconds)}` : label}</span>  : null}
      </Button>
      <span className="sr-only" role="status" aria-live="polite">{note}</span>
    </>
  );
}

export default MicButton;
