"use client";
// "Ask about this case": the chat, as a drawer on the right (plan §13.5, §6.4). Short, cited answers from the case file; a
// request for an outcome prediction or lay advice is refused and points to NALSA 15100. The composer has attach and a mic.
import { ArrowUp, FileText, Paperclip, ShieldAlert } from "lucide-react";
import { Fragment, useEffect, useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { Button } from "@/components/ui/button";
import { agentTitle, AGENTS } from "@/lib/agents";
import type { AgentName, ChatMessage } from "@/lib/types";
import { prefersReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { MicButton } from "./MicButton";
import { rememberUpload } from "./pdfShared";
import { ToolChips } from "./ToolChips";

export interface ChatPaneProps {
  caseId: string;
  className?: string;
}

const SUGGESTIONS = [
  "Days in custody?",
  "BNS equivalent of 420 IPC?",
  "Is my client eligible under s.479?",
  "Any SC case on parity in a cheating case?",
  "What did the Sessions Court say about antecedents?",
  "How does the State usually oppose bail in NDPS cases?",
] as const;

const DEVANAGARI = /[ऀ-ॿ]/;
const TOKEN = /\[[^\]]*\]|\bd\d+(?:,\s*|\s+)p\.?\s*\d+/g;
const DOC_REF = /\b(d\d+)(?:,\s*|\s+)p\.?\s*(\d+)/;

/** Message text with source references ("d4, p.10") as buttons that open the page, and [tool ...] citations as mono tags. */
function RichText({ text, onSource }: { text: string; onSource: (doc: string, page: number) => void }): ReactElement {
  const parts: ReactElement[] = [];
  let last = 0;
  let n = 0;
  for (const m of text.matchAll(TOKEN)) {
    const at = m.index ?? 0;
    if (at > last) parts.push(<Fragment key={n++}>{text.slice(last, at)}</Fragment>);
    const token = m[0];
    const ref = DOC_REF.exec(token);
    if (token.startsWith("[")) {
      parts.push(
        <span key={n++} className="rounded-sm bg-parchment-deep px-1 font-mono text-[0.8em] text-ink-soft">
          {ref ? (
            <>
              {token.slice(1, token.search(DOC_REF))}
              <SourceButton doc={ref[1]} page={Number(ref[2])} onSource={onSource} />
              {token.slice(token.search(DOC_REF) + ref[0].length, -1)}
            </>
          ) : (
            token
          )}
        </span>,
      );
    } else if (ref) {
      parts.push(<SourceButton key={n++} doc={ref[1]} page={Number(ref[2])} onSource={onSource} />);
    }
    last = at + token.length;
  }
  if (last < text.length) parts.push(<Fragment key={n++}>{text.slice(last)}</Fragment>);
  return <>{parts}</>;
}

function SourceButton({ doc, page, onSource }: { doc: string; page: number; onSource: (doc: string, page: number) => void }): ReactElement {
  return (
    <button
      type="button"
      onClick={() => onSource(doc, page)}
      className="mx-0.5 inline-flex items-center gap-0.5 rounded-sm font-mono text-[0.8em] text-maroon underline underline-offset-2 hover:bg-maroon/[0.08]"
      aria-label={`Open ${doc}, page ${page}`}
    >
      <FileText aria-hidden className="size-3" />
      {doc} · p.{page}
    </button>
  );
}

function Bubble({ message, onSource }: { message: ChatMessage; onSource: (doc: string, page: number) => void }): ReactElement {
  const hindi = DEVANAGARI.test(message.text);
  const body = (
    <p lang={hindi ? "hi" : undefined} className={cn("whitespace-pre-wrap text-sm leading-relaxed text-ink", hindi && "font-devanagari-body leading-devanagari")}>
      <RichText text={message.text} onSource={onSource} />
    </p>
  );
  if (message.role === "counsel") {
    return (
      <li className="flex justify-end">
        <article aria-label="You" data-testid="chat-message" data-role="counsel" className="max-w-[88%] rounded-lg bg-parchment-deep px-3.5 py-2.5">
          {body}
        </article>
      </li>
    );
  }
  const agent: AgentName = message.agent ?? "SUTRADHAR";
  return (
    <li>
      <article aria-label={agentTitle(agent)} data-testid="chat-message" data-role="agent" data-agent={agent} className="max-w-[94%]">
        <p className="mb-1 text-xs font-medium text-ink-muted">{AGENTS[agent].name}</p>
        {message.refused ? (
          <p className="mb-1 inline-flex items-center gap-1 text-sm font-medium text-haldi">
            <ShieldAlert aria-hidden className="size-4" /> Not answered: outside what this tool does
          </p>
        ) : null}
        {body}
        {message.refused && !message.text.includes("15100") ? (
          <p className="mt-2 text-sm text-ink-soft">
            Members of the public can call the NALSA legal-aid helpline on{" "}
            <a href="tel:15100" className="font-medium text-maroon underline underline-offset-2">15100</a>.
          </p>
        ) : null}
        {message.chips.length > 0 ? (
          <details className="mt-2 text-sm">
            <summary className="inline-flex cursor-pointer select-none rounded-sm text-ink-muted underline-offset-4 hover:text-ink hover:underline">How this was found</summary>
            <ToolChips chips={message.chips} className="mt-2" />
          </details>
        ) : null}
      </article>
    </li>
  );
}

/** A dictation read back: the dates and sections heard. Nothing is filed until the lawyer confirms (plan §4.5). */
function ReadbackCard({ lines, onConfirm, onDismiss }: { lines: string[]; onConfirm: () => void; onDismiss: () => void }): ReactElement {
  const heard = lines.filter((l) => /\d/.test(l));
  const asks = lines.filter((l) => !/\d/.test(l));
  return (
    <section data-testid="readback-card" aria-label="Read-back of your dictation" className="mt-4 border-l-2 border-line-strong pl-4">
      <p className="text-sm text-ink">This is what I heard. Nothing is filed until you confirm.</p>
      <ul className="mt-2 space-y-1">
        {heard.map((l) => (
          <li key={l} data-testid="readback-item" className="text-sm text-ink">
            {l}
          </li>
        ))}
      </ul>
      {asks.map((a) => (
        <p key={a} className="mt-2 text-sm font-medium text-ink">{a}</p>
      ))}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" data-testid="readback-confirm" onClick={onConfirm}>
          Confirm
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Not right, dismiss
        </Button>
      </div>
      <p className="mt-2 text-sm text-ink-soft">Confirmed facts are entered as yours, and the draft says so.</p>
    </section>
  );
}

export function ChatPane({ caseId, className }: ChatPaneProps): ReactElement {
  const ws = useWorkspace();
  const [draft, setDraft] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const messages = ws.data.chat;
  const working = ws.activity.working;
  const runningAgent: AgentName | null = working[0] ?? (ws.chatPending || ws.drafting ? "SUTRADHAR" : null);
  const running = runningAgent ? ws.activity.byAgent[runningAgent] : null;

  // Munshi's questions after an upload, unless the chat history already carries them (the demo does).
  const questions = ws.uploadQuestions.filter((q) => !messages.some((m) => m.text === q));

  useEffect(() => taRef.current?.focus(), []);

  useEffect(() => {
    const el = logRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }, [messages.length, ws.chatPending, questions.length]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 150)}px`;
  }, [draft]);

  const submit = async (text: string) => {
    const t = text.trim();
    if (!t || ws.chatPending) return;
    setDraft("");
    await ws.sendChat(t);
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      void submit(draft);
    }
  };

  const openSource = (doc: string, page: number) => ws.selectSource({ doc, page }, "chat answer");
  const empty = messages.length === 0 && questions.length === 0;

  return (
    <section aria-label="Chat" className={cn("flex min-h-0 flex-1 flex-col", className)}>
      <div
        ref={logRef}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 py-5"
      >
        {empty ? (
          <div className="max-w-sm">
            <p className="font-display text-lg font-semibold text-ink">Ask anything about this case</p>
            <p className="mt-1 text-sm text-ink-soft">Custody days, BNS equivalents, rights that may be open, precedents. Each answer shows where it came from.</p>
            <ul aria-label="Suggested questions" className="mt-4 flex flex-col items-start gap-1">
              {SUGGESTIONS.slice(0, 4).map((s) => (
                <li key={s}>
                  <button type="button" onClick={() => void submit(s)} disabled={ws.chatPending} className="rounded-sm py-1 text-left text-sm text-maroon underline-offset-4 hover:underline disabled:opacity-50">
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ol className="flex flex-col gap-5">
            {messages.map((m) => (
              <Bubble key={m.message_id} message={m} onSource={openSource} />
            ))}
            {questions.map((q) => (
              <Bubble
                key={q}
                onSource={openSource}
                message={{ message_id: `q-${q}`, case_id: caseId, role: "agent", agent: "MUNSHI", text: q, chips: [], refused: false }}
              />
            ))}
          </ol>
        )}

        {ws.readback ? <ReadbackCard lines={ws.readback} onConfirm={() => void ws.confirmReadback()} onDismiss={ws.dismissReadback} /> : null}

        {runningAgent && running ? (
          <div className="mt-5" aria-busy="true">
            <AgentSignature
              agent={runningAgent}
              mode="working"
              active
              statusText={running.phase === "working" ? running.text : AGENTS[runningAgent].workingText}
            />
          </div>
        ) : null}
      </div>

      <div className="shrink-0 border-t border-line bg-cream px-4 pb-3 pt-2">
        {!empty ? (
          <ul aria-label="Suggested questions" className="mb-2 flex gap-1.5 overflow-x-auto pb-1">
            {SUGGESTIONS.map((s) => (
              <li key={s} className="shrink-0">
                <button
                  type="button"
                  onClick={() => void submit(s)}
                  disabled={ws.chatPending}
                  className="rounded-md border border-line-strong/60 px-2.5 py-1 text-sm text-ink-soft hover:border-ink-soft hover:text-ink disabled:opacity-50"
                >
                  {s}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit(draft);
          }}
          className="flex items-end gap-1 rounded-lg border border-line-strong/70 bg-cream p-1.5 focus-within:border-maroon"
        >
          <label htmlFor="chat-input" className="sr-only">
            Ask a question about this case (Hindi or English)
          </label>
          <textarea
            id="chat-input"
            data-testid="chat-input"
            ref={taRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKey}
            rows={1}
            placeholder="Ask about custody, sections, rights, precedents"
            aria-describedby="chat-hint"
            className="max-h-36 min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-ink-muted focus:outline-none focus-visible:outline-none"
          />
          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.docx,application/pdf,image/*"
            className="sr-only"
            tabIndex={-1}
            aria-hidden
            onChange={(e) => {
              const files = Array.from(e.target.files ?? []);
              e.target.value = "";
              if (files.length) {
                rememberUpload(caseId, files);
                void ws.upload(files);
              }
            }}
          />
          <Button type="button" variant="ghost" size="icon" onClick={() => fileRef.current?.click()} disabled={ws.uploading} aria-label="Attach files to the case" title="Attach files to the case">
            <Paperclip aria-hidden />
          </Button>
          <MicButton onRecorded={(blob, name) => ws.uploadAudio(blob, name)} busy={ws.uploading} />
          <Button type="submit" size="icon" data-testid="chat-send" disabled={!draft.trim() || ws.chatPending} aria-label="Send question" title="Send (Enter)">
            <ArrowUp aria-hidden />
          </Button>
        </form>
        <p id="chat-hint" className="mt-1.5 px-1 text-xs text-ink-muted">
          Enter sends, Shift+Enter adds a line. No outcome predictions. Free legal aid for the public: NALSA 15100.
        </p>
      </div>
    </section>
  );
}

export default ChatPane;
