"use client";
// Spar: what the prosecution is likely to say against the sample draft, the unanswered objection first. Each reply
// names what it relies on. Writing a reply here marks the objection as answered by you; nothing is answered for you.
import { useCallback, useState, type ReactElement } from "react";
import { StatusBadge } from "@/components/common/StatusBadge";
import { AnimatePresence, m, MotionProvider, PRESENCE } from "@/components/motion/MotionProvider";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { OBJECTIONS } from "../sample";

const ORDER = { UNANSWERED: 0, PARTLY: 1, ANSWERED: 2 } as Record<string, number>;
const AGAINST: Record<string, string> = { G1: "Against ground A, parity", G4: "Against the gravity ground", general: "Against the application as a whole" };

export function SparDemo({ className }: { className?: string }): ReactElement {
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [writing, setWriting] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  // The reply box takes focus when it appears (after the button's exit, so a mount-time ref, not an effect).
  const box = useCallback((el: HTMLTextAreaElement | null) => el?.focus(), []);
  const list = [...OBJECTIONS].sort((a, b) => (ORDER[a.verdict ?? ""] ?? 3) - (ORDER[b.verdict ?? ""] ?? 3));

  return (
    <MotionProvider>
      <ol data-testid="spar-demo" aria-label="Likely objections to the sample draft" className={cn("space-y-3", className)}>
        {list.map((o) => {
          const mine = replies[o.id];
          const verdict = mine ? "ANSWERED" : (o.verdict ?? "UNANSWERED");
          return (
            <li key={o.id} data-testid="spar-card" data-verdict={verdict} className={cn("rounded-lg border bg-cream p-4", verdict === "UNANSWERED" ? "border-sindoor/50" : "border-line")}>
              <p className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-xs text-ink-muted">
                <span>{AGAINST[o.against] ?? "Against the draft"}</span>
                <StatusBadge status={verdict} kind="verdict" size="sm" label={mine ? "Answered by you" : undefined} testId="spar-verdict" />
              </p>
              <p className="doc-text mt-1.5 text-[16px] text-ink">{o.objection}</p>
              {mine ? (
                <p data-testid="spar-mine" className="mt-2 border-l-2 border-neem pl-3 text-sm text-ink">{mine}</p>
              ) : o.reply ? (
                <p className="mt-2 border-l-2 border-line pl-3 text-sm text-ink-soft">{o.reply}</p>
              ) : (
                <p className="mt-2 text-sm text-ink-soft">{o.reason}</p>
              )}
              {o.verdict === "PARTLY" && !mine ? <p className="mt-1 text-sm text-saffron-ink">{o.reason}</p> : null}
              {o.verdict === "UNANSWERED" && !mine ? (
                <AnimatePresence initial={false} mode="wait">
                  {writing === o.id ? (
                    <m.form
                      key="form"
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={PRESENCE}
                      className="mt-3"
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (!draft.trim()) return;
                        setReplies((r) => ({ ...r, [o.id]: draft.trim() }));
                        setWriting(null);
                        setDraft("");
                      }}
                    >
                      <label htmlFor={`reply-${o.id}`} className="text-sm font-medium text-ink">Your reply</label>
                      <Textarea ref={box} id={`reply-${o.id}`} data-testid="spar-reply-input" rows={3} value={draft} onChange={(e) => setDraft(e.target.value)} className="mt-1" />
                      <div className="mt-2 flex justify-end gap-2">
                        <Button type="button" variant="ghost" size="sm" onClick={() => setWriting(null)}>Cancel</Button>
                        <Button type="submit" size="sm" data-testid="spar-reply-save" disabled={!draft.trim()}>Save reply</Button>
                      </div>
                    </m.form>
                  ) : (
                    <m.div key="btn" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={PRESENCE} className="mt-3">
                      <Button variant="secondary" size="sm" data-testid="spar-write" onClick={() => setWriting(o.id)}>Write a reply</Button>
                    </m.div>
                  )}
                </AnimatePresence>
              ) : null}
            </li>
          );
        })}
      </ol>
    </MotionProvider>
  );
}
