// Batch desk band: the sample folder ranked as the desk ranks it (legal deadlines first, then days past a threshold,
// then custody length), each with the reason in a sentence. Static: the ranking is the product's, not the visitor's.
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactElement } from "react";
import { rv } from "./rv";
import { Button } from "@/components/ui/button";
import { DESK_CARDS } from "./sample";

export function DeskBand(): ReactElement {
  return (
    <div className="mx-auto grid max-w-[76rem] items-start gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-20">
      <div>
        <h2 id="desk-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold lg:text-4xl">A folder of files, the most urgent first</h2>
        <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-ink-soft">
          The batch desk reads a whole folder and ranks it: legal deadlines first, then days past a threshold, then time in custody. Each case still needs its own approval, and nothing is exported in bulk.
        </p>
        <div data-rv style={rv(2)} className="mt-6">
          <Button asChild variant="secondary" className="lift"><Link href="/desk" className="no-underline">Open the batch desk <ArrowRight aria-hidden className="arrow" /></Link></Button>
        </div>
      </div>
      <ol data-rv style={rv(3)} data-testid="desk-band" aria-label="Sample folder, ranked" className="divide-y divide-line rounded-lg border border-line bg-cream">
        {DESK_CARDS.map((c) => (
          <li key={c.id} data-testid="desk-band-card" className="px-4 py-3">
            <p className="font-display text-[1.0625rem] font-semibold text-ink">{c.title}</p>
            <p className="mt-0.5 text-sm text-ink">{c.reason}</p>
            {c.missing.length > 0 ? <p className="mt-0.5 text-xs text-saffron-ink">Missing: {c.missing.join(", ")}</p> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}
