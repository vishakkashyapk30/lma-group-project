"use client";
// The foot of Review facts and Export while the gate is not yet approved: the holding gate button (HoldButton) and, when
// counsel presses it with items open, the list of those items with one action each (go to it, or mark an unknown fact as
// unknown), the same actions as the confirm dialog. The list takes focus; Escape closes it and returns focus.
import { useEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { HoldButton } from "@/components/common/HoldButton";
import { AnimatePresence, m, MotionProvider, usePresenceTransition } from "@/components/motion/MotionProvider";
import { Button } from "@/components/ui/button";
import { plural } from "@/lib/format";
import type { GateId } from "@/lib/types";
import { useGateChecklist, useWorkspace, type ChecklistItem } from "@/lib/workspace";
import { StepFooter } from "./StepFrame";

export interface GateFooterProps {
  gate: GateId;
  label: string;
  /** Opens the confirm dialog (only when nothing is open). */
  onApprove: () => void;
  testId: string;
  /** "confirm" or "approve", for the sentence under the button. */
  verb: string;
  next?: boolean;
  secondary?: ReactNode;
}

export function GateFooter({ gate, label, onApprove, testId, verb, next, secondary }: GateFooterProps): ReactElement {
  const tr = usePresenceTransition();
  const ws = useWorkspace();
  const checklist = useGateChecklist(gate);
  const open = checklist.blocking;
  const held = open.length > 0;
  const [listOpen, setListOpen] = useState(false);
  const listRef = useRef<HTMLElement>(null);
  const focusOnOpen = useRef(false);

  useEffect(() => {
    if (!held) setListOpen(false);
  }, [held]);
  useEffect(() => {
    if (listOpen && focusOnOpen.current) {
      focusOnOpen.current = false;
      listRef.current?.querySelector<HTMLElement>("[data-testid=gate-hold-item] button")?.focus();
    }
  }, [listOpen]);

  const close = () => {
    setListOpen(false);
    document.querySelector<HTMLElement>(`[data-testid="${testId}"]`)?.focus();
  };
  const go = (item: ChecklistItem) => {
    setListOpen(false);
    ws.focusItem(item.target.tab, item.target.id, item.kind === "UNSUPPORTED" ? "edit" : undefined);
  };

  const hint = held ? `${plural(open.length, "item")} above ${open.length === 1 ? "needs" : "need"} you before you can ${verb}.` : undefined;

  return (
    <MotionProvider>
      <StepFooter
        label={label}
        onClick={onApprove}
        hint={hint}
        secondary={secondary}
        above={
          <AnimatePresence initial={false}>
            {listOpen && held ? (
              <m.section
                key="hold-list"
                ref={listRef}
                role="region"
                aria-labelledby="hold-title"
                data-testid="gate-hold-list"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 6 }}
                transition={tr()}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    e.preventDefault();
                    e.stopPropagation();
                    close();
                  }
                }}
                className="mb-3 border-b border-line pb-3"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <h3 id="hold-title" className="font-sans text-sm font-semibold text-ink">Still open before you can {verb}</h3>
                  <button type="button" onClick={close} className="rounded-sm text-sm text-ink-soft hover:text-ink">Hide</button>
                </div>
                <ul className="mt-1 divide-y divide-line">
                  {open.map((item) => (
                    <li key={item.key} data-testid="gate-hold-item" data-item={item.ref} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 py-2">
                      <p className="min-w-0 flex-1 text-sm text-ink">{item.label}</p>
                      <div className="flex shrink-0 gap-2">
                        {item.canAcknowledge ? (
                          <Button variant="ghost" size="sm" onClick={() => ws.acknowledge(item.key)}>Mark as unknown</Button>
                        ) : null}
                        <Button variant="secondary" size="sm" onClick={() => go(item)}>Go to it</Button>
                      </div>
                    </li>
                  ))}
                </ul>
              </m.section>
            ) : null}
          </AnimatePresence>
        }
        control={
          <HoldButton
            label={label}
            held={held}
            openCount={open.length}
            onPress={onApprove}
            onHold={() => {
              focusOnOpen.current = true;
              setListOpen(true);
            }}
            testId={testId}
            describedBy={held ? "step-hint" : undefined}
            next={next}
          />
        }
      />
    </MotionProvider>
  );
}
