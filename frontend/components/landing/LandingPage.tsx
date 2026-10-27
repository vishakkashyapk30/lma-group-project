// Landing page (/): a product page built from full-width colour bands. Cream hero, saffron how-it-works, indigo sources,
// neem control, maroon close, neutral footer. Colour carries meaning (maroon acts, indigo informs, neem confirms, saffron
// asks for a check). Motion: the hero loop plays once; each band reveals once on scroll. See DESIGN.md.
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactElement } from "react";
import "@/styles/landing.css";
import { Logo } from "@/components/common/Logo";
import { Button } from "@/components/ui/button";
import { sampleCaseHref } from "@/lib/sampleCase";
import { ContinueCase } from "./ContinueCase";
import { Footer } from "./Footer";
import { FileDemo } from "./demos/FileDemo";
import { Reveal } from "./Reveal";

const STEPS = [
  { title: "Upload the file", body: "FIR, remand order and other papers, scanned or typed, in Hindi or English." },
  { title: "Review the dossier", body: "Each fact links to the page it came from. What cannot be found is marked, not guessed." },
  { title: "Check rights and draft", body: "Bail rights are checked against the dates, then the application is drafted for you to edit." },
  { title: "Approve and export", body: "Nothing leaves until you approve it. Take the draft away as a Word file." },
] as const;

const CONTROL = [
  { title: "Approval before anything is exported", body: "Two checkpoints need your sign-off: the dossier before drafting, and the application before export." },
  { title: "Every fact linked to its source", body: "Open any fact or citation to see the page and the exact words behind it." },
  { title: "No outcome predictions", body: "It reports the law and the dates. It does not guess whether bail will be granted." },
  { title: "Private by default", body: "Your files stay on your machine unless you turn on an external model service, which is off by default and asks for consent." },
] as const;

function CheckDraw(): ReactElement {
  return (
    <svg viewBox="0 0 16 16" width="18" height="18" aria-hidden className="check-draw mt-[3px] shrink-0 text-neem">
      <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const rv = (i: number) => ({ "--i": i }) as React.CSSProperties;

export function LandingPage(): ReactElement {
  return (
    <div className="bg-parchment">
      {/* Hero: cream */}
      <div className="overflow-x-clip">
        <header className="mx-auto flex h-16 max-w-[76rem] items-center justify-between px-4 sm:px-6">
          <Link href="/" aria-label="Vakeel-Sahayak home" className="rounded-sm no-underline"><Logo /></Link>
          <nav aria-label="Landing" className="flex items-center gap-1 sm:gap-3">
            <a href="#how" className="link-draw hidden px-3 py-2 text-sm text-ink-soft hover:text-ink md:block">How it works</a>
            <a href="#control" className="link-draw hidden px-3 py-2 text-sm text-ink-soft hover:text-ink md:block">Safeguards</a>
            <Link href="/help" className="link-draw hidden px-3 py-2 text-sm text-ink-soft hover:text-ink md:block">Help</Link>
            <ContinueCase />
          </nav>
        </header>

        <section aria-labelledby="hero-heading" className="mx-auto grid max-w-[76rem] items-center gap-12 px-4 pb-20 pt-8 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)] lg:gap-16 lg:pb-24 lg:pt-12">
          <div className="enter">
            <h1 id="hero-heading" className="max-w-[16ch] font-display text-[2.5rem] font-semibold leading-[1.08] text-ink sm:text-5xl lg:text-[3.25rem]">
              Prepare a bail application from the case file. <span className="text-maroon">Every fact traced to its source.</span>
            </h1>
            <p className="mt-5 max-w-[34rem] text-lg leading-relaxed text-ink-soft">
              Upload the case papers and Vakeel-Sahayak reads them, checks bail rights against the dates, and drafts an application for you to review.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg" className="lift"><Link href={sampleCaseHref("/cases")} data-testid="open-case-button" className="no-underline">Try the sample case <ArrowRight aria-hidden className="arrow" /></Link></Button>
              <Button asChild size="lg" variant="secondary" className="lift"><a href="#how" className="no-underline">See how it works</a></Button>
            </div>
            <p className="mt-4 max-w-[34rem] text-sm text-ink-muted">The sample case holds the papers of a bail file with the names replaced: an FIR in Hindi, two remand orders, two bail orders and an order sheet. No sign-in.</p>
          </div>
          <FileDemo className="enter min-w-0" />
        </section>
      </div>

      {/* How it works: saffron tint */}
      <section id="how" aria-labelledby="how-heading" className="scroll-mt-4 bg-saffron-tint">
        <Reveal className="mx-auto max-w-[76rem] px-4 py-16 sm:px-6 lg:py-20">
          <h2 id="how-heading" data-rv style={rv(0)} className="font-display text-3xl font-semibold lg:text-4xl">How it works</h2>
          <ol role="list" className="mt-10 grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.title} data-rv style={rv(i + 1)} className="border-t-[3px] border-saffron pt-4">
                <h3 className="font-sans text-base font-semibold text-ink">{s.title}</h3>
                <p className="mt-1.5 max-w-[22rem] text-ink-soft">{s.body}</p>
              </li>
            ))}
          </ol>
        </Reveal>
      </section>

      {/* Sources: indigo */}
      <section aria-labelledby="sources-heading" className="bg-indigo-deep">
        <Reveal className="mx-auto grid max-w-[76rem] items-center gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:gap-16 lg:py-20">
          <div>
            <h2 id="sources-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold text-cream lg:text-4xl">Open a fact and see the words behind it</h2>
            <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-indigo-pale">Each value in the dossier carries the document and page it was read from. If the file does not say, the field says so.</p>
          </div>
          <div data-rv style={rv(2)} className="rounded-lg bg-cream p-5 text-ink sm:p-6">
            <p className="font-mono text-xs text-indigo">Remand order · p. 1</p>
            <p className="doc-text mt-3">
              The accused was produced before this Court on <span className="sweep">14.08.2024</span>, and is remanded to judicial custody for fourteen days.
            </p>
            <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3 text-sm">
              <p><span className="text-ink-soft">Date of arrest</span> <span className="ml-1 font-medium">14.08.2024</span></p>
              <p className="flex items-center gap-1.5 font-medium text-neem"><CheckDraw /> Confirmed from the documents</p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* Control: neem tint */}
      <section id="control" aria-labelledby="control-heading" className="scroll-mt-4 bg-neem-tint">
        <Reveal className="mx-auto max-w-[76rem] px-4 py-16 sm:px-6 lg:py-20">
          <h2 id="control-heading" data-rv style={rv(0)} className="font-display text-3xl font-semibold lg:text-4xl">What you stay in control of</h2>
          <ul role="list" className="mt-10 grid gap-x-14 gap-y-8 md:grid-cols-2">
            {CONTROL.map((c, i) => (
              <li key={c.title} data-rv style={rv(i + 1)} className="flex gap-3">
                <CheckDraw />
                <div>
                  <h3 className="font-sans text-base font-semibold text-ink">{c.title}</h3>
                  <p className="mt-1 max-w-[32rem] text-ink-soft">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>
      </section>

      {/* Close: maroon, with a faint lattice */}
      <section aria-labelledby="close-heading" className="jaali-dark bg-maroon">
        <Reveal className="mx-auto max-w-[76rem] px-4 py-20 sm:px-6 lg:py-24">
          <h2 id="close-heading" data-rv style={rv(0)} className="max-w-[20ch] font-display text-4xl font-semibold text-cream sm:text-5xl">
            Justice, social, economic and political.
          </h2>
          <p data-rv style={rv(1)} className="mt-4 text-sm text-gold-pale">Preamble to the Constitution of India</p>
          <p lang="hi" data-rv style={rv(2)} className="mt-1 text-sm text-gold-pale">सामाजिक, आर्थिक और राजनैतिक न्याय</p>
          <div data-rv style={rv(3)} className="mt-8">
            <Button asChild size="lg" variant="secondary" className="lift"><Link href="/cases" className="no-underline">Open workspace <ArrowRight aria-hidden className="arrow" /></Link></Button>
          </div>
        </Reveal>
      </section>

      <Footer />
    </div>
  );
}
