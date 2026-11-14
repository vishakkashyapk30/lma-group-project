"use client";
// Guided demos on the cases page: the recorded demo cases an evaluator can walk through with Next. One row per tour with its
// title, its story and the four ways the demos differ, as plain text. Nothing is shown when the server has no demos.
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useEffect, useState, type ReactElement } from "react";
import { buttonVariants } from "@/components/ui/button";
import { listTours } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { TourSummary, TourVariant } from "@/lib/tour";
import { cn } from "@/lib/utils";

/** The workspace URL that opens a case in tour mode. */
export function tourHref(tour: Pick<TourSummary, "slug" | "case_id">): string {
  return `/case/${encodeURIComponent(tour.case_id)}?tour=${encodeURIComponent(tour.slug)}`;
}

export function GuidedDemos({ className }: { className?: string }): ReactElement | null {
  const t = useT();
  const [tours, setTours] = useState<TourSummary[] | null>(null);

  useEffect(() => {
    let live = true;
    listTours()
      .then((list) => live && setTours(list))
      .catch(() => live && setTours([])); // demos are optional: an error here hides the section, the cases list reports its own
    return () => {
      live = false;
    };
  }, []);

  if (!tours || tours.length === 0) return null;
  const facets: { key: keyof TourVariant; label: string }[] = [
    { key: "offence", label: t("Offence and law") },
    { key: "custody", label: t("Custody and rights") },
    { key: "record", label: t("Record quality") },
    { key: "parity", label: t("Parity and history") },
  ];

  return (
    <section aria-labelledby="guided-demos-title" data-testid="guided-demos" className={cn("mt-8", className)}>
      <h2 id="guided-demos-title" className="font-display text-xl font-semibold text-ink">
        {t("Guided demos")}
      </h2>
      <p className="mt-1 max-w-prose text-sm text-ink-soft">
        {t("Recorded cases that walk through every step, from the papers to the export. Open one and press Next after each step.")}
      </p>
      <ul className="mt-3 divide-y divide-line overflow-hidden rounded-lg border border-line bg-cream">
        {tours.map((tour) => (
          <li key={tour.slug} data-testid="guided-demo" data-slug={tour.slug} className="flex flex-col gap-3 px-4 py-4 sm:flex-row sm:items-start sm:gap-6 sm:px-5">
            <div className="min-w-0 flex-1">
              <h3 className="font-sans text-base font-semibold text-ink">{tour.title}</h3>
              {tour.story ? <p className="mt-1 max-w-prose text-sm text-ink-soft">{tour.story}</p> : null}
              <dl className="mt-3 grid gap-x-6 gap-y-1.5 text-sm sm:grid-cols-2">
                {facets.filter((f) => tour.variant[f.key]).map((f) => (
                  <div key={f.key} className="min-w-0">
                    <dt className="inline font-medium text-ink">{f.label}: </dt>
                    <dd className="inline text-ink-soft">{tour.variant[f.key]}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <Link
              href={tourHref(tour)}
              data-testid="guided-demo-start"
              aria-label={`${t("Start the guided demo")}: ${tour.title}`}
              className={cn(buttonVariants({ variant: "secondary", size: "md" }), "shrink-0 self-start no-underline")}
            >
              {t("Start the guided demo")} <ArrowRight aria-hidden />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default GuidedDemos;
