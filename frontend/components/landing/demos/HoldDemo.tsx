"use client";
// Hold: the sample case's two approvals. "Confirm facts and continue" holds while a fact is open (the antecedents are
// not in the papers): pressing or pulling it moves it a few pixels against the rubber band and lists what is open.
// Mark the fact as unknown and the gate opens, then asks for confirmation and says what it locks. After that the export
// gate holds on the draft's four open items, and there is no export button anywhere until counsel approves.
import { Check } from "lucide-react";
import { useEffect, useRef, useState, type ReactElement } from "react";
import { HoldButton } from "@/components/common/HoldButton";
import { AnimatePresence, m, MotionProvider, usePresenceTransition } from "@/components/motion/MotionProvider";
import { Button } from "@/components/ui/button";
import { sampleCaseHref } from "@/lib/sampleCase";
import { cn } from "@/lib/utils";
import { GATE1_ITEMS, GATE1_LOCKS, GATE2_ITEMS } from "../sample";

function OpenList({ id, title, items, onAcknowledge, focusFirst, footer }: {
  id: string;
  title: string;
  items: { key: string; label: string; canAcknowledge: boolean }[];
  onAcknowledge?: (key: string) => void;
  focusFirst: boolean;
  footer?: ReactElement;
}): ReactElement {
  const tr = usePresenceTransition();
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    if (focusFirst) ref.current?.querySelector<HTMLElement>("li button, a")?.focus();
  }, [focusFirst]);
  return (
    <m.section ref={ref} key={id} role="region" aria-labelledby={`${id}-t`} data-testid={`${id}-list`} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }} transition={tr()} className="mt-3 border-y border-line py-2">
      <h4 id={`${id}-t`} className="font-sans text-sm font-semibold text-ink">{title}</h4>
      <ul className="mt-1 divide-y divide-line">
        {items.map((i) => (
          <li key={i.key} data-testid={`${id}-item`} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2">
            <p className="min-w-0 flex-1 text-sm text-ink">{i.label}</p>
            {i.canAcknowledge && onAcknowledge ? <Button variant="secondary" size="sm" onClick={() => onAcknowledge(i.key)}>Mark as unknown</Button> : null}
          </li>
        ))}
      </ul>
      {footer}
    </m.section>
  );
}

export function HoldDemo({ className }: { className?: string }): ReactElement {
  const tr = usePresenceTransition();
  const [acknowledged, setAcknowledged] = useState<string[]>([]);
  const [list1, setList1] = useState<"closed" | "open" | "focus">("closed");
  const [confirming, setConfirming] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [list2, setList2] = useState<"closed" | "open" | "focus">("closed");
  const open1 = GATE1_ITEMS.filter((i) => !acknowledged.includes(i.key));
  const confirmRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  return (
    <MotionProvider>
      <div data-testid="hold-demo" className={cn("rounded-lg border border-line bg-cream p-4 sm:p-5", className)}>
        <div data-testid="gate1-demo">
          <h3 className="font-sans text-base font-semibold text-ink">Review facts</h3>
          {confirmed ? (
            <p data-testid="gate1-confirmed" className="mt-2 flex items-center gap-1.5 text-sm font-medium text-neem-deep"><Check aria-hidden className="size-4" /> Facts confirmed by you. Drafting starts from them.</p>
          ) : (
            <>
              <p id="gate1-hint" className="mt-1 text-sm text-ink-soft">{open1.length > 0 ? `${open1.length} item needs you before you can confirm.` : "Nothing is open. Confirming records the decision as yours."}</p>
              <AnimatePresence initial={false}>
                {list1 !== "closed" && open1.length > 0 ? (
                  <OpenList id="gate1" title="Still open before you can confirm" items={open1} focusFirst={list1 === "focus"} onAcknowledge={(k) => { setAcknowledged((a) => [...a, k]); setList1("closed"); }} />
                ) : null}
                {confirming ? (
                  <m.section key="confirm" role="region" aria-labelledby="gate1-confirm-t" data-testid="gate1-confirm" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={tr()} className="mt-3 border-y border-line py-3">
                    <h4 id="gate1-confirm-t" className="font-sans text-sm font-semibold text-ink">Confirm these facts</h4>
                    <p className="mt-1 text-sm text-ink-soft">What this locks:</p>
                    <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-ink-soft">
                      {GATE1_LOCKS.map((l) => <li key={l}>{l}</li>)}
                    </ul>
                    <div className="mt-3 flex justify-end gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>Cancel</Button>
                      <Button ref={confirmRef} size="sm" data-testid="gate1-confirm-button" onClick={() => { setConfirming(false); setConfirmed(true); }}>Confirm facts</Button>
                    </div>
                  </m.section>
                ) : null}
              </AnimatePresence>
              <div className="mt-3 flex justify-end">
                <HoldButton
                  label="Confirm facts and continue"
                  held={open1.length > 0}
                  openCount={open1.length}
                  testId="gate1-demo-button"
                  describedBy="gate1-hint"
                  onPress={() => setConfirming(true)}
                  onHold={() => setList1("focus")}
                />
              </div>
            </>
          )}
        </div>

        <div data-testid="gate2-demo" className="mt-5 border-t border-line pt-4">
          <h3 className="font-sans text-base font-semibold text-ink">Export</h3>
          <p id="gate2-hint" className="mt-1 text-sm text-ink-soft">
            {confirmed ? `There is no export button before you approve the draft. ${GATE2_ITEMS.length} items in the draft need you first.` : "Opens once you confirm the facts. There is no export button before the draft is approved."}
          </p>
          {confirmed ? (
            <>
              <AnimatePresence initial={false}>
                {list2 !== "closed" ? (
                  <OpenList
                    id="gate2"
                    title="Still open before you can approve"
                    items={GATE2_ITEMS}
                    focusFirst={list2 === "focus"}
                    footer={<p className="mt-2 text-sm"><a href={sampleCaseHref("#walk")} className="font-medium text-maroon underline-offset-4 hover:underline">Resolve them in the sample case</a></p>}
                  />
                ) : null}
              </AnimatePresence>
              <div className="mt-3 flex justify-end">
                <HoldButton label="Approve this draft for export" held openCount={GATE2_ITEMS.length} testId="gate2-demo-button" describedBy="gate2-hint" next={false} onPress={() => {}} onHold={() => setList2("focus")} />
              </div>
            </>
          ) : null}
        </div>
      </div>
    </MotionProvider>
  );
}
