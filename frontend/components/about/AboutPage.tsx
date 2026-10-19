"use client";
// Method and safety page (plan §13.5, §3.2, §5.1, §16): how it works, the safety rules, the limits and evaluation
// results as clearly marked placeholders (no invented numbers).
import { Hourglass, ShieldCheck } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import { AgentGlyph } from "@/components/common/AgentGlyph";
import { Badge } from "@/components/ui";
import { AGENT_LIST } from "@/lib/agents";
import { GATE_LABELS, STAGES } from "@/lib/stages";
import { SHELF_META, SHELF_ORDER, storesOnShelf } from "@/lib/stores";
import { cn } from "@/lib/utils";

export interface AboutPageProps {
  className?: string;
}

const SAFETY: { area: string; rule: string }[] = [
  { area: "Approvals", rule: "Export works only after Gate 2, enforced in code. The batch desk never exports in bulk: each case needs its own approval." },
  { area: "Privacy", rule: "Text is pseudonymised after OCR and before it leaves the laptop. Page images and audio stay on the laptop. The GPU server sees only pseudonymised text and public test data. Audio is deleted after transcription unless counsel keeps it." },
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

function Section({ id, title, kicker, children }: { id: string; title: string; kicker: string; children: ReactNode }): ReactElement {
  return (
    <section aria-labelledby={id} className="mt-12">
      <p className="text-xs font-semibold uppercase tracking-caps text-ink-soft">{kicker}</p>
      <h2 id={id} className="mb-4 font-display text-3xl font-semibold text-maroon">{title}</h2>
      {children}
    </section>
  );
}

export function AboutPage({ className }: AboutPageProps): ReactElement {
  return (
    <div className={cn("mx-auto max-w-content px-4 py-8 sm:px-6 sm:py-10", className)}>
      <header className="border-b-2 border-maroon/70 pb-5">
        <p className="text-xs font-semibold uppercase tracking-caps text-ink-soft">Method and safety</p>
        <h1 className="font-display text-4xl font-semibold text-maroon sm:text-5xl">How Vakeel-Sahayak works</h1>
        <p className="mt-2 max-w-prose text-base text-ink-soft">
          A team of six agents, named for the people in an Indian court office, helps counsel prepare a bail application. Every claim in the
          draft points to a source. Counsel approves at two gates, and nothing is exported without that approval.
        </p>
      </header>

      <Section id="agents" kicker="Six agents" title="The court office">
        <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {AGENT_LIST.map((a) => (
            <li key={a.id} className="rounded-lg border border-line bg-cream p-4 shadow-sm">
              <div className="flex items-center gap-3">
                <span className="grid size-11 place-items-center rounded-full border border-gold/60 bg-parchment text-maroon"><AgentGlyph agent={a.id} size={26} /></span>
                <div>
                  <h3 className="font-display text-xl font-semibold leading-tight">{a.name} <span lang="hi" className="font-devanagari text-lg text-maroon">{a.nameHi}</span></h3>
                  <p className="text-sm text-ink-soft">{a.subtitle}</p>
                </div>
              </div>
              <p className="mt-3 text-sm italic text-ink-soft">{a.role}</p>
              <p className="mt-1 text-sm">{a.job}</p>
              <p className="mt-2 font-mono text-xs text-ink-muted">{a.runsOn}</p>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="flow" kicker="Seven stages" title="From the first page to the filing">
        <ol className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2 lg:grid-cols-4">
          {STAGES.map((s) => (
            <li key={s.id} className="flex gap-3 rounded-md border border-line bg-cream p-3">
              <span className="font-display text-2xl font-semibold text-maroon/80" aria-hidden>{s.numeral}</span>
              <div><h3 className="text-sm font-semibold"><span className="sr-only">Stage {s.numeral}: </span>{s.label}</h3><p className="text-xs text-ink-soft">{s.description}</p></div>
            </li>
          ))}
        </ol>
      </Section>

      <Section id="shelves" kicker="Four shelves, ten stores" title="Where the agents look">
        <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2 lg:grid-cols-4">
          {SHELF_ORDER.map((id) => (
            <li key={id} className="rounded-lg border border-line bg-parchment-deep/50 p-4">
              <h3 className="font-display text-lg font-semibold text-maroon">{SHELF_META[id].label}</h3>
              <p className="mb-2 text-sm text-ink-soft">{SHELF_META[id].description}</p>
              <ul className="m-0 list-none space-y-1 p-0 text-sm">
                {storesOnShelf(id).map((s) => <li key={s.id}><span className="font-semibold">{s.label}</span> <span className="text-xs text-ink-muted">· {s.indexLabel}</span></li>)}
              </ul>
            </li>
          ))}
        </ul>
      </Section>

      <Section id="gates" kicker="Two gates" title="Counsel approves, always">
        <ul className="m-0 grid list-none gap-4 p-0 sm:grid-cols-2">
          {(Object.keys(GATE_LABELS) as (keyof typeof GATE_LABELS)[]).map((g) => (
            <li key={g} className="flex gap-3 rounded-lg border border-gold/50 bg-cream p-4">
              <span aria-hidden className="mt-1 text-xl text-maroon">◆</span>
              <div><h3 className="font-display text-lg font-semibold">{GATE_LABELS[g].label}</h3><p className="text-sm text-ink-soft">{GATE_LABELS[g].description}</p></div>
            </li>
          ))}
        </ul>
        <p className="mt-3 max-w-prose text-sm text-ink-soft">
          A gate opens only when every unsupported field is resolved or acknowledged, and every item that needs review or is unanswered is settled.
        </p>
      </Section>

      <Section id="safety" kicker="Safety and ethics" title="Rules the system keeps">
        <dl className="m-0 divide-y divide-line overflow-hidden rounded-lg border border-line bg-cream">
          {SAFETY.map((r) => (
            <div key={r.area} className="grid gap-1 px-4 py-3 sm:grid-cols-[11rem_1fr]">
              <dt className="flex items-center gap-2 font-semibold text-maroon"><ShieldCheck aria-hidden className="size-4 shrink-0" />{r.area}</dt>
              <dd className="m-0 text-sm text-ink-soft">{r.rule}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section id="limits" kicker="Limits" title="What it does not do">
        <ul className="m-0 max-w-prose list-disc space-y-1.5 pl-5 text-sm text-ink-soft">
          {LIMITS.map((l) => <li key={l}>{l}</li>)}
        </ul>
      </Section>

      <Section id="eval" kicker="Evaluation" title="Results">
        <p role="note" className="mb-3 flex items-start gap-2 rounded-md border border-haldi/50 bg-haldi/[0.07] p-3 text-sm text-haldi">
          <Hourglass aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span><strong>Placeholders.</strong> The evaluation has not been run yet. The cells below are empty on purpose; numbers will be filled in from the test runs and no figure here is an estimate.</span>
        </p>
        <div className="overflow-x-auto rounded-lg border border-line bg-cream">
          <table className="w-full min-w-[40rem] text-left text-sm">
            <caption className="sr-only">Planned evaluations and their results</caption>
            <thead>
              <tr className="border-b border-line bg-parchment-deep/60 text-xs uppercase tracking-caps text-ink-soft">
                <th scope="col" className="px-3 py-2">Question</th><th scope="col" className="px-3 py-2">What is tested</th><th scope="col" className="px-3 py-2">Metrics</th><th scope="col" className="px-3 py-2">Result</th>
              </tr>
            </thead>
            <tbody>
              {EVAL_ROWS.map((r) => (
                <tr key={r.rq} className="border-b border-line/60 align-top">
                  <th scope="row" className="px-3 py-2 font-display text-base font-semibold text-maroon">{r.rq}</th>
                  <td className="px-3 py-2">{r.what}</td>
                  <td className="px-3 py-2 text-ink-soft">{r.metric}</td>
                  <td className="px-3 py-2"><Badge variant="haldi"><Hourglass aria-hidden /> Pending: to be filled in</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <p className="mt-12 border-t border-line pt-4 text-xs text-ink-muted">
        AI-generated drafts for counsel; not legal advice. If you are an accused person or a family member looking for free legal help, call NALSA on 15100.
      </p>
    </div>
  );
}

export default AboutPage;
