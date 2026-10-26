"use client";
// About: how it works, the safety rules, the limits and evaluation
// results as clearly marked placeholders (no invented numbers).
import { Hourglass } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { PageHeader } from "@/components/common/PageHeader";
import { AGENT_LIST } from "@/lib/agents";
import { GATE_LABELS, STAGES } from "@/lib/stages";
import { SHELF_META, SHELF_ORDER, storesOnShelf } from "@/lib/stores";
import { cn } from "@/lib/utils";

export interface AboutPageProps {
  className?: string;
}

const SAFETY: { area: string; rule: string }[] = [
  { area: "Approvals", rule: "Export works only after Gate 2, enforced in code. The batch desk never exports in bulk: each case needs its own approval." },
  { area: "Privacy", rule: "Text is pseudonymised after OCR and before it leaves the laptop. Page images and audio stay on the laptop unless you consent to an external model service for a case. The GPU server sees only pseudonymised text and public test data. Audio is deleted after transcription unless counsel keeps it." },
  { area: "Documents are data", rule: "Instructions found inside documents, including scans, Hindi text and handwriting, are never followed." },
  { area: "Scope", rule: "No outcome predictions or grant rates. The similar-facts shelf shows reasoning, never rates. No advice to accused persons or the public; the landing page points them to NALSA 15100." },
  { area: "Rights Radar", rule: "Outputs are possible entitlements to check, each with its rule text, source and the dates used. Where the law is unsettled the answer is CHECK." },
  { area: "Sensitive matters", rule: "Sexual-offence, POCSO and juvenile matters are declined at intake, because the law protects the identity of victims and children." },
  { area: "National symbols", rule: "No State Emblem, national flag or court logos. All artwork is our own." },
  { area: "Data", rule: "Only public court orders and constructed files. Demos use public or synthetic files." },
  { area: "Bias", rule: "Results are compared across offence types, courts, bail outcomes and input kinds (Hindi and English, scanned and digital), and gaps are reported." },
];

const LIMITS = [
  "It drafts for counsel. It is not legal advice and does not replace an advocate's judgement.",
  "It never predicts whether bail will be granted and never shows grant rates.",
  "A claim it cannot tie to a source is marked unsupported instead of being smoothed over.",
  "Where the law is unsettled, the Rights Radar says CHECK and leaves the decision to counsel.",
  "Case law is limited to the public corpus we indexed; a missing precedent does not mean none exists.",
  "OCR and handwriting errors are possible. Every dossier field shows its source so counsel can check it against the page.",
  "Hindi and English documents are supported; other languages are not.",
  "Sexual-offence, POCSO and juvenile matters are declined.",
];

const EVAL_ROWS: { rq: string; what: string; metric: string }[] = [
  { rq: "RQ1", what: "Orchestrated retrieval against five baselines", metric: "Factor recall and precision; unsupported-fact rate; tokens and store calls per case" },
  { rq: "H1c", what: "Section-family expansion on BNS-era cases", metric: "Recall@10 of court-cited precedents" },
  { rq: "RQ2", what: "Agentic ingestion on scanned, photographed, Hindi and bundled files", metric: "Downstream field accuracy; cost per page" },
  { rq: "Rights Radar", what: "Seven procedural checks", metric: "Accuracy; false-ELIGIBLE rate" },
  { rq: "Safety", what: "Unapproved-export attempts, planted instructions, prediction requests", metric: "Success and refusal rates; leak rate of planted names" },
  { rq: "Frontend", what: "Accessibility, performance, reduced motion, user flows", metric: "Lighthouse; axe-core violations; flow completion" },
];

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }): ReactElement {
  return (
    <section aria-labelledby={id} className="mt-10 border-t border-line pt-6">
      <h2 id={id} className="mb-4 font-display text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function AboutPage({ className }: AboutPageProps): ReactElement {
  return (
    <div className={cn("mx-auto max-w-content px-4 py-6 sm:px-6 sm:py-8", className)}>
      <PageHeader
        title="How Vakeel-Sahayak works"
        description="Six agents, named for the people in an Indian court office, help counsel prepare a bail application. Every claim in the draft points to a source. Counsel approves at two gates, and nothing is exported without that approval."
      />

      <Section id="agents" title="The agents">
        <ul className="m-0 grid list-none gap-x-8 gap-y-5 p-0 sm:grid-cols-2">
          {AGENT_LIST.map((a) => (
            <li key={a.id} className="flex gap-3">
              <span aria-hidden className="mt-0.5 text-maroon"><AgentGlyph agent={a.id} size={22} /></span>
              <div>
                <h3 className="font-sans text-base font-semibold leading-tight">{a.name} <span lang="hi" className="font-normal text-ink-soft">{a.nameHi}</span><span className="font-normal text-ink-soft">, {a.subtitle}</span></h3>
                <p className="mt-1 text-sm">{a.job}</p>
                <p className="mt-1 font-mono text-xs text-ink-muted">{a.runsOn}</p>
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="flow" title="From the first page to the filing">
        <ol className="m-0 grid list-none gap-x-8 gap-y-3 p-0 sm:grid-cols-2">
          {STAGES.map((s) => (
            <li key={s.id}>
              <h3 className="font-sans text-sm font-semibold">{s.label}</h3>
              <p className="text-sm text-ink-soft">{s.description}</p>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="shelves" title="Where the agents look">
        <ul className="m-0 grid list-none gap-x-8 gap-y-5 p-0 sm:grid-cols-2 lg:grid-cols-4">
          {SHELF_ORDER.map((id) => (
            <li key={id}>
              <h3 className="font-sans text-sm font-semibold">{SHELF_META[id].label}</h3>
              <p className="mb-2 text-sm text-ink-soft">{SHELF_META[id].description}</p>
              <ul className="m-0 list-none space-y-1 p-0 text-sm">
                {storesOnShelf(id).map((s) => <li key={s.id}>{s.label} <span className="text-xs text-ink-muted">{s.indexLabel}</span></li>)}
              </ul>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="gates" title="Counsel approves, always">
        <ul className="m-0 grid list-none gap-x-8 gap-y-4 p-0 sm:grid-cols-2">
          {(Object.keys(GATE_LABELS) as (keyof typeof GATE_LABELS)[]).map((g) => (
            <li key={g}><h3 className="font-sans text-sm font-semibold">{GATE_LABELS[g].label}</h3><p className="text-sm text-ink-soft">{GATE_LABELS[g].description}</p></li>
          ))}
        </ul>
        <p className="mt-3 max-w-prose text-sm text-ink-soft">
          A gate opens only when every unsupported field is resolved or acknowledged, and every item that needs review or is unanswered is settled.
        </p>
      </Section>

      <Section id="safety" title="Rules the system keeps">
        <dl className="m-0 divide-y divide-line border-y border-line">
          {SAFETY.map((r) => (
            <div key={r.area} className="grid gap-1 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="font-semibold">{r.area}</dt>
              <dd className="m-0 text-sm text-ink-soft">{r.rule}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section id="limits" title="What it does not do">
        <ul className="m-0 max-w-prose list-disc space-y-1.5 pl-5 text-sm text-ink-soft">
          {LIMITS.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </Section>

      <Section id="eval" title="Evaluation results">
        <p role="note" className="mb-3 flex items-start gap-2 text-sm text-haldi">
          <Hourglass aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>The evaluation has not been run yet. The result cells are empty on purpose; they will be filled in from the test runs, and no figure here is an estimate.</span>
        </p>
        {/* The table scrolls sideways on a phone; the region is focusable so keyboard users can scroll it too (WCAG 2.1.1). */}
        <div role="region" aria-label="Planned evaluations, scrolls sideways" tabIndex={0} className="overflow-x-auto border-y border-line focus-visible:outline focus-visible:outline-2 focus-visible:outline-maroon">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <caption className="sr-only">Planned evaluations and their results</caption>
            <thead>
              <tr className="border-b border-line text-xs text-ink-muted">
                <th scope="col" className="py-2 pr-3 font-medium">Question</th><th scope="col" className="px-3 py-2 font-medium">What is tested</th><th scope="col" className="px-3 py-2 font-medium">Metrics</th><th scope="col" className="px-3 py-2 font-medium">Result</th>
              </tr>
            </thead>
            <tbody>
              {EVAL_ROWS.map((r) => (
                <tr key={r.rq} className="border-b border-line/60 align-top last:border-0">
                  <th scope="row" className="py-2 pr-3 font-semibold">{r.rq}</th>
                  <td className="px-3 py-2">{r.what}</td>
                  <td className="px-3 py-2 text-ink-soft">{r.metric}</td>
                  <td className="px-3 py-2 text-haldi">Pending</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <p className="mt-10 border-t border-line pt-4 text-xs text-ink-muted">
        AI-generated drafts for counsel; not legal advice. If you are an accused person or a family member looking for free legal help, call NALSA on 15100.
      </p>
    </div>
  );
}

export default AboutPage;
