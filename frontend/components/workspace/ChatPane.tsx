"use client";
// Centre pane, the core of the workspace (plan §13.5, §6.4): counsel's questions and the agents' answers, each with the agent's
// name, subtitle and signature (in working mode while it runs), tool and store chips, "Show the plan", and a composer with a
// mic and attach. Answers are short and cited; requests for outcome predictions or lay advice are refused (NALSA 15100).
import { ArrowUp, FileText, MessageSquareText, Paperclip, Scale, ShieldAlert, Sparkles } from "lucide-react";
import { Fragment, useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactElement } from "react";
import { AgentSignature } from "@/components/agents/AgentSignature";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { Button } from "@/components/ui/button";
import { agentTitle, AGENTS } from "@/lib/agents";
import { formatClock } from "@/lib/format";
import type { AgentName, ChatMessage } from "@/lib/types";
import { prefersReducedMotion } from "@/lib/useReducedMotion";
import { cn } from "@/lib/utils";
import { useWorkspace } from "@/lib/workspace";
import { MicButton } from "./MicButton";
import { rememberUpload } from "./pdfShared";
import { ToolChips } from "./ToolChips";
import { TraceDrawer } from "./TraceDrawer";

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
        <span key={n++} className="rounded-sm bg-gold/15 px-1 font-mono text-[0.8em] text-ink-soft">
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
      className="mx-0.5 inline-flex items-center gap-0.5 rounded-sm border border-line-strong/50 bg-cream px-1 font-mono text-[0.8em] text-maroon hover:border-maroon"
      aria-label={`Open ${doc}, page ${page}`}
    >
      <FileText aria-hidden className="size-3" />
      {doc} · p.{page}
    </button>
  );
}

function AgentHeading({ agent }: { agent: AgentName }): ReactElement {
  const meta = AGENTS[agent];
  return (
    <p className="flex items-center gap-2">
      <span aria-hidden className="grid size-7 shrink-0 place-items-center rounded-full border border-gold/60 bg-parchment text-maroon">
        <AgentGlyph agent={agent} size={16} />
      </span>
      <span className="font-display text-sm font-semibold text-maroon">{meta.name}</span>
      <span className="text-xs text-ink-soft">{meta.subtitle}</span>
    </p>
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
        <article aria-label="Counsel" data-testid="chat-message" data-role="counsel" className="max-w-[88%] rounded-lg rounded-br-sm border border-maroon/25 bg-maroon/[0.07] px-3.5 py-2.5">
          <p className="mb-1 text-2xs font-semibold uppercase tracking-caps text-maroon">Counsel</p>
          {body}
        </article>
      </li>
    );
  }
  const agent: AgentName = message.agent ?? "SUTRADHAR";
  return (
    <li>
      <article
        aria-label={agentTitle(agent)}
        data-testid="chat-message"
        data-role="agent"
        data-agent={agent}
        className={cn(
          "max-w-[94%] rounded-lg rounded-bl-sm border px-3.5 py-3",
          message.refused ? "border-haldi/50 bg-haldi/[0.07]" : "border-line-strong/50 bg-cream shadow-sm",
        )}
      >
        <AgentHeading agent={agent} />
        {message.refused ? (
          <p className="mt-2 inline-flex items-center gap-1 rounded-pill border border-haldi/50 bg-cream px-2 py-1 text-xs font-semibold text-haldi">
            <ShieldAlert aria-hidden className="size-3.5" /> Out of scope: not answered
          </p>
        ) : null}
        <div className="mt-2">{body}</div>
        {message.refused && !message.text.includes("15100") ? (
          <p className="mt-2 text-xs text-ink-soft">
            Members of the public can call the NALSA legal-aid helpline on{" "}
            <a href="tel:15100" className="font-semibold text-maroon underline underline-offset-2">15100</a>.
          </p>
        ) : null}
        {message.chips.length > 0 ? <ToolChips chips={message.chips} className="mt-2.5" /> : null}
      </article>
    </li>
  );
}

/** Munshi's read-back of a dictation: the dates and sections it heard. Nothing is filed until counsel confirms (plan §4.5). */
function ReadbackCard({ lines, onConfirm, onDismiss }: { lines: string[]; onConfirm: () => void; onDismiss: () => void }): ReactElement {
  const heard = lines.filter((l) => /\d/.test(l));
  const asks = lines.filter((l) => !/\d/.test(l));
  return (
    <section data-testid="readback-card" aria-label="Munshi's read-back of your dictation" className="mt-4 max-w-[94%] rounded-lg rounded-bl-sm border border-gold/60 bg-cream px-3.5 py-3 shadow-sm">
      <AgentHeading agent="MUNSHI" />
      <p className="mt-2 text-sm text-ink">This is what I heard. Nothing is filed until you confirm.</p>
      <ul className="mt-2 space-y-1">
        {heard.map((l) => (
          <li key={l} data-testid="readback-item" className="rounded-md border border-line bg-parchment/60 px-2.5 py-1.5 text-sm text-ink">
            {l}
          </li>
        ))}
      </ul>
      {asks.map((a) => (
        <p key={a} className="mt-2 text-sm font-semibold text-maroon">{a}</p>
      ))}
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" data-testid="readback-confirm" onClick={onConfirm}>
          Confirm
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Not right: dismiss
        </Button>
      </div>
      <p className="mt-2 text-xs text-ink-soft">Confirmed facts are filed as stated by counsel, and the brief will say so.</p>
    </section>
  );
}

export function ChatPane({ caseId, className }: ChatPaneProps): ReactElement {
  const ws = useWorkspace();
  const [draft, setDraft] = useState("");
  const [planOpen, setPlanOpen] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const planButton = useRef<HTMLButtonElement>(null);

  const messages = ws.data.chat;
  const working = ws.activity.working;
  const runningAgent: AgentName | null = working[0] ?? (ws.chatPending ? "SUTRADHAR" : ws.drafting ? "SUTRADHAR" : null);
  const running = runningAgent ? ws.activity.byAgent[runningAgent] : null;

  // Munshi's questions after an upload, unless the chat history already carries them (the demo does).
  const questions = ws.uploadQuestions.filter((q) => !messages.some((m) => m.text === q));

  const notes = useMemo(
    () =>
      ws.events
        .filter((e) => e.kind === "AGENT_MESSAGE" && typeof e.outputs?.text === "string")
        .filter((e) => {
          const t = e.outputs.text as string;
          return t !== "Answered in chat" && !t.startsWith("Refused:");
        })
        .slice(-8)
        .reverse(),
    [ws.events],
  );

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
  const gate1 = ws.gates.approvals.gate1;

  return (
    <section aria-labelledby="chat-title" className={cn("flex min-h-0 flex-col bg-parchment/40", className)}>
      <header className="flex flex-wrap items-center gap-2 border-b border-line bg-cream px-4 py-2.5">
        <MessageSquareText aria-hidden className="size-4 text-maroon" />
        <div className="min-w-0 flex-1">
          <h2 id="chat-title" className="font-display text-base font-semibold text-maroon">
            Ask the case
          </h2>
          <p className="text-xs text-ink-soft">Short, cited answers from the case file and the stores. For counsel only.</p>
        </div>
        <div className="flex w-full flex-wrap items-center gap-2">
        <AgentSignature
          agent="SUTRADHAR"
          mode="working"
          active={ws.activity.byAgent.SUTRADHAR.phase === "working"}
          className="max-w-[7rem]"
          litStores={ws.activity.activeStores}
          activeTool={ws.activity.byAgent.SUTRADHAR.tool}
          statusText={ws.activity.byAgent.SUTRADHAR.phase === "working" ? ws.activity.byAgent.SUTRADHAR.text : undefined}
        />
        <Button
          ref={planButton}
          data-testid="show-plan-button"
          variant="pill"
          size="sm"
          onClick={() => setPlanOpen(true)}
          aria-haspopup="dialog"
          aria-expanded={planOpen}
        >
          <Scale aria-hidden /> Show the plan
        </Button>
        <Button
          variant="secondary"
          size="sm"
          data-testid="draft-brief-button"
          onClick={() => void ws.startDraft()}
          disabled={!gate1 || ws.drafting}
          title={gate1 ? "Sutradhar plans, Vakeel drafts, Abhiyojak spars" : "Approve the dossier (Gate 1) before drafting"}
          aria-describedby={gate1 ? undefined : "draft-why"}
        >
          <Sparkles aria-hidden /> {ws.drafting ? "Drafting…" : "Draft bail brief"}
        </Button>
        {!gate1 ? (
          <span id="draft-why" className="sr-only">
            Drafting opens after counsel approves the dossier at Gate 1.
          </span>
        ) : null}
        </div>
      </header>

      {notes.length > 0 ? (
        <details className="border-b border-line bg-cream/70 px-4 py-1.5 text-xs">
          <summary className="cursor-pointer select-none font-semibold text-ink-soft hover:text-ink">Agent notes ({notes.length})</summary>
          <ul className="mt-1.5 flex flex-col gap-1.5 pb-1">
            {notes.map((e) => {
              const actor = String(e.actor).toUpperCase() as AgentName;
              const known = actor in AGENTS;
              return (
                <li key={e.event_id} className="flex gap-2">
                  {known ? <AgentGlyph agent={actor} size={14} className="mt-0.5 shrink-0 text-maroon" /> : null}
                  <span className="min-w-0 text-ink-soft">
                    <span className="font-semibold text-ink">{known ? AGENTS[actor].name : String(e.actor)}</span>{" "}
                    <time dateTime={e.ts} className="font-mono text-2xs text-ink-muted">{formatClock(e.ts)}</time>
                    <span className="block">{e.outputs.text as string}</span>
                  </span>
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}

      <div
        ref={logRef}
        role="log"
        aria-label="Conversation"
        aria-live="polite"
        aria-relevant="additions"
        tabIndex={0}
        data-lenis-prevent=""
        className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4"
      >
        {messages.length === 0 && questions.length === 0 ? (
          <div className="mx-auto mt-6 max-w-md rounded-lg border border-dashed border-gold/60 bg-cream p-5 text-center">
            <p className="font-display text-lg text-maroon">Ask anything about this case</p>
            <p className="mt-1 text-sm text-ink-soft">
              Custody days, BNS equivalents, rights that may be open, precedents, or how the State usually opposes. Every answer shows where it came from.
            </p>
          </div>
        ) : (
          <ol className="flex flex-col gap-4">
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
          <div className="mt-4" role="status" aria-label={`${agentTitle(runningAgent)} is working`}>
            <div className="max-w-[94%] rounded-lg rounded-bl-sm border border-gold/50 bg-cream px-3.5 py-3 shadow-sm" aria-busy="true">
              <AgentHeading agent={runningAgent} />
              <div className="mt-2">
                <AgentSignature
                  agent={runningAgent}
                  mode="working"
                  active
                  className="max-w-[13rem]"
                  statusText={running.phase === "working" ? running.text : AGENTS[runningAgent].workingText}
                  litStores={runningAgent === "SUTRADHAR" ? ws.activity.activeStores : undefined}
                  activeTool={runningAgent === "SUTRADHAR" ? running.tool : undefined}
                  unanswered={runningAgent === "ABHIYOJAK" ? ws.gates.checklists.GATE_2_EXPORT.blocking.filter((i) => i.kind === "UNANSWERED").length : undefined}
                />
              </div>
            </div>
          </div>
        ) : null}
      </div>

      <div className="border-t border-line bg-cream px-3 pb-3 pt-2">
        <ul aria-label="Suggested questions" data-lenis-prevent="" className="mb-2 flex gap-1.5 overflow-x-auto pb-1">
          {SUGGESTIONS.map((s) => (
            <li key={s} className="shrink-0">
              <button
                type="button"
                onClick={() => void submit(s)}
                disabled={ws.chatPending}
                className="rounded-pill border border-line-strong/60 bg-parchment px-2.5 py-1 text-xs text-ink hover:border-maroon hover:text-maroon disabled:opacity-50"
              >
                {s}
              </button>
            </li>
          ))}
        </ul>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void submit(draft);
          }}
          className="flex items-end gap-1.5 rounded-lg border border-line-strong/70 bg-parchment/50 p-1.5 focus-within:border-maroon"
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
            placeholder="Ask about custody, sections, rights, precedents…"
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
        <p id="chat-hint" className="mt-1.5 px-1 text-2xs text-ink-muted">
          Enter sends, Shift+Enter adds a line. No outcome predictions or advice to the public: for free legal aid the public can call NALSA on 15100.
        </p>
      </div>

      <TraceDrawer
        caseId={caseId}
        open={planOpen}
        onClose={() => {
          setPlanOpen(false);
          planButton.current?.focus();
        }}
      />
    </section>
  );
}

export default ChatPane;
