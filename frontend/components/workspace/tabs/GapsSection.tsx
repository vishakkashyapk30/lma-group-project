"use client";
// Gaps by factor (Review facts): for each of the twelve bail factors, whether the papers give the facts the draft needs for it.
// A factor with nothing in the file comes first; each missing fact is a link that opens it for editing. Fully covered factors
// are folded away. The factor-to-fact table is the drafter's own (lib/factorGaps.ts).
import { AlertTriangle, CircleDashed, CheckCircle2 } from "lucide-react";
import type { ReactElement } from "react";
import { factorGaps, type Coverage, type FactorGap } from "@/lib/factorGaps";
import { fieldLabel } from "@/lib/fields";
import { plural } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import type { DossierFieldName } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCaseData } from "@/lib/workspace";

const COVERAGE: Record<Coverage, { word: string; icon: typeof AlertTriangle; tone: string }> = {
  none: { word: "Nothing in the file", icon: AlertTriangle, tone: "text-sindoor" },
  partial: { word: "Partly in the file", icon: CircleDashed, tone: "text-haldi" },
  full: { word: "In the file", icon: CheckCircle2, tone: "text-neem" },
};

function FactLinks({ names, verb, onOpen }: { names: DossierFieldName[]; verb: string; onOpen: (name: DossierFieldName) => void }): ReactElement {
  return (
    <>
      {names.map((name, i) => (
        <span key={name}>
          {i > 0 ? ", " : ""}
          <button type="button" onClick={() => onOpen(name)} className="rounded-sm text-maroon underline-offset-4 hover:underline" aria-label={`${verb} ${fieldLabel(name)}`}>
            {fieldLabel(name)}
          </button>
        </span>
      ))}
    </>
  );
}

function GapRow({ gap, onOpen }: { gap: FactorGap; onOpen: (name: DossierFieldName, edit: boolean) => void }): ReactElement {
  const meta = COVERAGE[gap.coverage];
  const Icon = meta.icon;
  return (
    <li data-testid="factor-gap" data-factor={gap.factor} data-coverage={gap.coverage} className="grid gap-x-4 gap-y-1 py-3.5 sm:grid-cols-[minmax(0,1fr)_11rem]">
      <div className="min-w-0">
        <h4 className="font-sans text-base font-medium text-ink">{FACTOR_LABELS[gap.factor]}</h4>
        {gap.missing.length > 0 ? (
          <p className="mt-0.5 text-sm text-ink-soft">
            Not found: <FactLinks names={gap.missing} verb="Add" onOpen={(n) => onOpen(n, true)} />.
          </p>
        ) : null}
        {gap.unclear.length > 0 ? (
          <p className="mt-0.5 text-sm text-ink-soft">
            The documents disagree on: <FactLinks names={gap.unclear} verb="Check" onOpen={(n) => onOpen(n, false)} />.
          </p>
        ) : null}
        {gap.coverage !== "none" && gap.present.length > 0 ? (
          <p className="mt-0.5 text-sm text-ink-muted">From the file: {gap.present.map(fieldLabel).join(", ")}.</p>
        ) : null}
      </div>
      <p className={cn("m-0 inline-flex items-center gap-1.5 text-sm font-medium sm:justify-end sm:pt-0.5", meta.tone)}>
        <Icon aria-hidden className="size-4 shrink-0" /> {meta.word}
      </p>
    </li>
  );
}

export interface GapsSectionProps {
  /** Opens a fact in the Facts list (for editing when `edit`). */
  onOpenFact: (name: DossierFieldName, edit: boolean) => void;
}

export function GapsSection({ onOpenFact }: GapsSectionProps): ReactElement {
  const { dossier } = useCaseData();
  const gaps = factorGaps(dossier);
  const open = gaps.filter((g) => g.coverage !== "full").sort((a, b) => (a.coverage === b.coverage ? 0 : a.coverage === "none" ? -1 : 1));
  const covered = gaps.filter((g) => g.coverage === "full");
  const none = open.filter((g) => g.coverage === "none").length;

  return (
    <section aria-labelledby="gaps-title" data-testid="factor-gaps">
      <h3 id="gaps-title" className="sr-only">Gaps by factor</h3>
      <p className="text-ink-soft" aria-live="polite">
        {open.length === 0
          ? "The papers give a fact for every bail factor."
          : `${plural(open.length, "factor")} of ${gaps.length} lack facts in the papers${none > 0 ? `; ${none} with nothing at all` : ""}.`}
      </p>
      {open.length > 0 ? (
        <ul aria-label="Factors with gaps" className="mt-3 divide-y divide-line border-y border-line">
          {open.map((g) => (
            <GapRow key={g.factor} gap={g} onOpen={onOpenFact} />
          ))}
        </ul>
      ) : null}
      {covered.length > 0 ? (
        <details className="mt-4 text-sm">
          <summary className="inline-flex cursor-pointer select-none rounded-sm font-medium text-ink-soft underline-offset-4 hover:text-ink hover:underline">
            {plural(covered.length, "factor")} covered by the papers
          </summary>
          <ul aria-label="Factors covered by the papers" className="mt-2 divide-y divide-line border-y border-line">
            {covered.map((g) => (
              <GapRow key={g.factor} gap={g} onOpen={onOpenFact} />
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

export default GapsSection;
