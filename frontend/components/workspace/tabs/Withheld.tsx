"use client";
// What the draft left out (strict abstention of the chosen architecture): under a ground, the sentences taken out of its argument
// and why, behind a short disclosure; after the grounds, the grounds that lost every sentence and are left for counsel to draft.
import type { ReactElement } from "react";
import { humanize, plural } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import type { Factor, WithheldGround } from "@/lib/types";
import { reasonSentence } from "@/lib/withheld";
import { cn } from "@/lib/utils";
import { SectionTitle } from "./shared";

function SentenceList({ group, className }: { group: WithheldGround; className?: string }): ReactElement {
  return (
    <ul className={cn("m-0 list-none space-y-3 border-l-2 border-line p-0 pl-4", className)}>
      {group.sentences.map((s, i) => (
        <li key={`${i}-${s.sentence}`} data-testid="withheld-sentence">
          <p className="doc-text text-ink">{s.sentence}</p>
          <p className="mt-0.5 text-ink-soft">{reasonSentence(s.reason, group.factor)}</p>
        </li>
      ))}
    </ul>
  );
}

/** Under a ground: "Removed from the argument", closed until counsel opens it. Nothing renders when nothing was removed. */
export function RemovedSentences({ group }: { group: WithheldGround | null }): ReactElement | null {
  if (!group || group.sentences.length === 0) return null;
  return (
    <details className="mt-4 text-sm" data-testid="withheld-list" data-ground={group.ground} data-print-hide>
      <summary className="inline-flex cursor-pointer select-none rounded-sm font-medium text-ink-soft underline-offset-4 hover:text-ink hover:underline">
        Removed from the argument ({plural(group.sentences.length, "sentence")})
      </summary>
      <p className="mt-2 text-ink-soft">These are not in the draft. Add one back only if you can point to its source.</p>
      <SentenceList group={group} className="mt-3" />
    </details>
  );
}

/** After the grounds: factors where no sentence could be supported, so no ground was drafted. */
export function DroppedGrounds({ groups }: { groups: WithheldGround[] }): ReactElement | null {
  if (groups.length === 0) return null;
  return (
    <section aria-labelledby="brief-not-drafted" data-print-hide>
      <SectionTitle id="brief-not-drafted">Grounds left for you to draft</SectionTitle>
      <p className="mt-1 text-ink-soft">Nothing in these could be tied to the record or an authority, so they are not in the draft.</p>
      <ul className="mt-2 divide-y divide-line border-y border-line">
        {groups.map((g) => (
          <li key={g.ground} className="py-4" data-testid="dropped-ground" data-ground={g.ground}>
            <h4 className="font-display text-lg font-semibold leading-snug text-ink">
              <span className="sr-only">{g.ground}: </span>
              {FACTOR_LABELS[g.factor as Factor] ?? humanize(g.factor)}
            </h4>
            <p className="mt-1 text-sm text-ink-soft">Removed from the argument:</p>
            <SentenceList group={g} className="mt-2 text-sm" />
          </li>
        ))}
      </ul>
    </section>
  );
}
