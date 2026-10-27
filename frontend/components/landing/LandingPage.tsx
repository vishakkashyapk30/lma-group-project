// Landing page (/): "Walk the file". The hero and five hands-on demos run on the built-in sample case (case-0007) with no
// sign-in and no backend: put the FIR on the file, read a fact's source, check rights against the dates, try the gates,
// open a ground's authority, answer an objection. Then privacy, the batch desk, and the way into the sample case.
// Colour carries meaning (maroon acts, indigo informs, neem confirms, saffron asks for a check). Motion: one entrance,
// each band reveals once, and the demos move only under the visitor's hand. See DESIGN.md.
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import type { ReactElement } from "react";
import "@/styles/landing.css";
import { Logo } from "@/components/common/Logo";
import { Button } from "@/components/ui/button";
import { sampleCaseHref } from "@/lib/sampleCase";
import { CloseBand } from "./CloseBand";
import { ContinueCase } from "./ContinueCase";
import { DeskBand } from "./DeskBand";
import { Footer } from "./Footer";
import { CheckDemo } from "./demos/CheckDemo";
import { DraftDemo } from "./demos/DraftDemo";
import { FileDemo } from "./demos/FileDemo";
import { HoldDemo } from "./demos/HoldDemo";
import { PrivacyDemo } from "./demos/PrivacyDemo";
import { ReadDemo } from "./demos/ReadDemo";
import { SparDemo } from "./demos/SparDemo";
import { Reveal } from "./Reveal";
import { rv } from "./rv";


/** The walk through the sample case, as in-page links (plain words, not numbered). */
const WALK = [
  { href: "#read", label: "Read", hint: "the words behind a fact" },
  { href: "#check", label: "Check", hint: "rights against the dates" },
  { href: "#hold", label: "Hold", hint: "the two approvals" },
  { href: "#draft", label: "Draft", hint: "grounds and their authorities" },
  { href: "#spar", label: "Spar", hint: "the objections first" },
] as const;

export function LandingPage(): ReactElement {
  return (
    <div className="bg-parchment">
      <div className="overflow-x-clip">
        <header className="mx-auto flex h-16 max-w-[76rem] items-center justify-between gap-3 px-4 sm:px-6">
          <Link href="/" aria-label="Vakeel-Sahayak home" className="shrink-0 rounded-sm no-underline"><Logo /></Link>
          <nav aria-label="Landing" className="flex min-w-0 items-center gap-1 sm:gap-2">
            <a href="#walk" className="link-draw hidden px-2.5 py-2 text-sm text-ink-soft hover:text-ink md:block">How it works</a>
            <a href="#privacy" className="link-draw hidden px-2.5 py-2 text-sm text-ink-soft hover:text-ink md:block">Privacy</a>
            <a href="#desk" className="link-draw hidden px-2.5 py-2 text-sm text-ink-soft hover:text-ink lg:block">Batch desk</a>
            <Link href="/help" className="link-draw hidden px-2.5 py-2 text-sm text-ink-soft hover:text-ink md:block">Help</Link>
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
              <Button asChild size="lg" variant="secondary" className="lift"><a href="#walk" className="no-underline">See how it works</a></Button>
            </div>
            <p className="mt-4 max-w-[34rem] text-sm text-ink-muted">The sample case holds the papers of a bail file with the names replaced: an FIR in Hindi, two remand orders, two bail orders and an order sheet. No sign-in.</p>
          </div>
          <FileDemo className="enter min-w-0" />
        </section>
      </div>

      {/* The walk: in-page links to the five demos */}
      <nav id="walk" aria-label="Walk through the sample case" className="scroll-mt-4 border-y border-line bg-parchment">
        <ul className="mx-auto flex max-w-[76rem] gap-x-8 gap-y-2 overflow-x-auto px-4 py-4 text-sm sm:px-6">
          {WALK.map((w) => (
            <li key={w.href} className="shrink-0">
              <a href={w.href} className="link-draw font-semibold text-ink hover:text-maroon">{w.label}</a> <span className="text-ink-muted">{w.hint}</span>
            </li>
          ))}
        </ul>
      </nav>

      {/* Read: indigo, the colour of sources */}
      <section id="read" aria-labelledby="read-heading" className="scroll-mt-4 bg-indigo-deep">
        <Reveal className="mx-auto grid max-w-[76rem] items-start gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-20">
          <div>
            <h2 id="read-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold text-cream lg:text-4xl">Open a fact and see the words behind it</h2>
            <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-indigo-pale">
              Each value in the dossier carries the document, the page and the sentence it was read from, in the language of the paper. If the file does not say, the field says so.
            </p>
          </div>
          <div data-rv style={rv(2)}>
            <ReadDemo />
          </div>
        </Reveal>
      </section>

      {/* Check: saffron, the colour of "check this" */}
      <section id="check" aria-labelledby="check-heading" className="scroll-mt-4 bg-saffron-tint">
        <Reveal className="mx-auto grid max-w-[76rem] items-start gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,4fr)_minmax(0,8fr)] lg:gap-16 lg:py-20">
          <div>
            <h2 id="check-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold lg:text-4xl">Check bail rights against the dates</h2>
            <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-ink-soft">
              The default-bail window and the undertrial limit, worked out from the arrest, the first remand and the charge sheet in the papers. Where a fact is missing it says Check. It does not say whether bail will be granted.
            </p>
          </div>
          <div data-rv style={rv(2)}>
            <CheckDemo />
          </div>
        </Reveal>
      </section>

      {/* Hold: cream, maroon actions */}
      <section id="hold" aria-labelledby="hold-heading" className="scroll-mt-4 border-y border-line bg-cream">
        <Reveal className="mx-auto grid max-w-[76rem] items-start gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-20">
          <div>
            <h2 id="hold-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold lg:text-4xl">Nothing goes ahead until you confirm it</h2>
            <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-ink-soft">
              Two approvals belong to counsel and the server enforces them: the facts before drafting, and the draft before export. A gate that is not ready shows what is still open when you try it.
            </p>
          </div>
          <div data-rv style={rv(2)}>
            <HoldDemo />
          </div>
        </Reveal>
      </section>

      {/* Draft: parchment, document type */}
      <section id="draft" aria-labelledby="draft-heading" className="scroll-mt-4 bg-parchment">
        <Reveal className="mx-auto max-w-[76rem] px-4 py-16 sm:px-6 lg:py-20">
          <h2 id="draft-heading" data-rv style={rv(0)} className="max-w-[24ch] font-display text-3xl font-semibold lg:text-4xl">Every ground cites its authority, word for word</h2>
          <p data-rv style={rv(1)} className="mt-4 max-w-[40rem] text-lg text-ink-soft">
            Each ground is drafted from the confirmed facts and quotes the paragraph of the judgment it relies on. A ground that fails its check stays in the draft, marked for you, instead of being dropped.
          </p>
          <div data-rv style={rv(2)} className="mt-8">
            <DraftDemo />
          </div>
        </Reveal>
      </section>

      {/* Spar: cream */}
      <section id="spar" aria-labelledby="spar-heading" className="scroll-mt-4 border-y border-line bg-cream">
        <Reveal className="mx-auto grid max-w-[76rem] items-start gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-20">
          <div>
            <h2 id="spar-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold lg:text-4xl">Hear the prosecution&apos;s objections first</h2>
            <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-ink-soft">
              The draft is argued against with objections courts have recorded in similar cases, the unanswered one first. A reply names what it relies on, and only you can mark an objection answered.
            </p>
          </div>
          <div data-rv style={rv(2)}>
            <SparDemo />
          </div>
        </Reveal>
      </section>

      {/* Privacy: neem, the colour of control */}
      <section id="privacy" aria-labelledby="privacy-heading" className="scroll-mt-4 bg-neem-tint">
        <Reveal className="mx-auto grid max-w-[76rem] items-start gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16 lg:py-20">
          <div>
            <h2 id="privacy-heading" data-rv style={rv(0)} className="max-w-[18ch] font-display text-3xl font-semibold lg:text-4xl">What leaves this computer</h2>
            <p data-rv style={rv(1)} className="mt-4 max-w-[30rem] text-lg text-ink-soft">
              The client&apos;s papers stay here. External model services are off unless you turn them on, and even then they get only what the setting allows, after names are replaced.
            </p>
          </div>
          <div data-rv style={rv(2)}>
            <PrivacyDemo />
          </div>
        </Reveal>
      </section>

      {/* Batch desk: neutral */}
      <section id="desk" aria-labelledby="desk-heading" className="scroll-mt-4 bg-parchment-deep">
        <Reveal>
          <DeskBand />
        </Reveal>
      </section>

      {/* Close: flat maroon */}
      <section aria-labelledby="close-heading" data-surface="dark" className="bg-maroon">
        <Reveal>
          <CloseBand />
        </Reveal>
      </section>

      <Footer />
    </div>
  );
}
