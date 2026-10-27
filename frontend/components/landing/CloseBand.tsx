"use client";
// The close: open the sample case (its title moves into the workspace's top bar when it opens), who built this, and how
// it is tested, with a link to the method and limits. Flat maroon, no pattern.
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useRef, type ReactElement } from "react";
import { rv } from "./rv";
import { startMorph } from "@/components/motion/Morph";
import { primeCaseMeta } from "@/components/shell/meta";
import { Button } from "@/components/ui/button";
import { SAMPLE_CASE_ID, SAMPLE_CASE_OPENS, sampleCaseHref } from "@/lib/sampleCase";

/** The sample case's title as the cause list shows it (lib/mock/cases.ts). */
const LIST_TITLE = "State v. Accused-1 · FIR 112/2024, PS-1 · BNS 318(4), 316(2)";

export function CloseBand(): ReactElement {
  const title = useRef<HTMLSpanElement>(null);
  return (
    <div className="mx-auto max-w-[76rem] px-4 py-16 sm:px-6 lg:py-20">
      <h2 id="close-heading" data-rv style={rv(0)} className="font-display text-4xl font-semibold text-cream sm:text-5xl">Open the sample case</h2>
      <p data-rv style={rv(1)} className="mt-4 max-w-[38rem] text-lg text-gold-pale">
        <span ref={title} className="font-semibold text-cream">State v. Accused-1, FIR 112/2024</span>: every step above, in the workspace, from the papers to the hearing card. Nothing to install and no sign-in.
      </p>
      <div data-rv style={rv(2)} className="mt-8 flex flex-wrap items-center gap-4">
        <Button asChild size="lg" variant="secondary" className="lift">
          <Link
            href={sampleCaseHref("/cases")}
            data-testid="close-open-sample"
            onClick={() => {
              if (!SAMPLE_CASE_OPENS) return;
              primeCaseMeta(SAMPLE_CASE_ID, LIST_TITLE);
              startMorph(`case-title-${SAMPLE_CASE_ID}`, title.current);
            }}
            className="!text-ink no-underline"
          >
            {SAMPLE_CASE_OPENS ? "Open the sample case" : "Open workspace"} <ArrowRight aria-hidden className="arrow" />
          </Link>
        </Button>
      </div>
      <div data-rv style={rv(3)} className="mt-12 grid gap-6 border-t border-cream/20 pt-6 text-sm text-gold-pale md:grid-cols-2">
        <p>
          <span className="font-semibold text-cream">Who built it.</span> A team of four at IIIT Hyderabad, as the LMA Group Project 2026: a bail-preparation tool for legal-aid counsel, not a service for the public.
        </p>
        <p>
          <span className="font-semibold text-cream">How it is tested.</span> Each part is measured against simpler baselines on test sets drawn from court text, official tables and existing datasets. No hand-made labels, and no model grades its own work.{" "}
          <Link href="/about" className="font-medium text-cream underline underline-offset-4">How it works and its limits</Link>
        </p>
      </div>
    </div>
  );
}
