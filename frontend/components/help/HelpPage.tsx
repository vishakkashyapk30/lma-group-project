// Help: how to start, keyboard shortcuts, and where the method and limits are written down.
import Link from "next/link";
import type { ReactElement, ReactNode } from "react";
import { PageHeader } from "@/components/common/PageHeader";

const SHORTCUTS: { keys: string; does: string }[] = [
  { keys: "Ctrl K or Cmd K", does: "Search cases, pages and actions" },
  { keys: "Arrow keys, Enter", does: "Move through search results and open one" },
  { keys: "Esc", does: "Close search, menus and dialogs" },
  { keys: "Left and Right arrow", does: "Move between steps when the step list has focus" },
];

const PRIVACY_MODES: { mode: string; what: string }[] = [
  { mode: "Off", what: "Nothing leaves your machine. This is the default." },
  { mode: "Public data only", what: "An external service may be used on public or constructed data. Case text is never sent." },
  { mode: "Pseudonymised text", what: "As above, plus client text after names and identifiers are replaced and the text is checked. Page images and audio are not sent." },
  { mode: "Consented", what: "As above, plus the raw pages and audio of a case, only for a case where you recorded consent." },
];

function Block({ id, title, children }: { id: string; title: string; children: ReactNode }): ReactElement {
  return (
    <section aria-labelledby={id} className="mt-8 border-t border-line pt-5">
      <h2 id={id} className="mb-3 font-display text-xl font-semibold">{title}</h2>
      {children}
    </section>
  );
}

export function HelpPage(): ReactElement {
  return (
    <div className="mx-auto max-w-content px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader title="Help" description="Starting a case, keyboard shortcuts, privacy, and where to read about method and limits." />
      <div className="max-w-3xl">
        <Block id="start" title="Start a case">
          <ol className="m-0 list-decimal space-y-1.5 pl-5 text-ink-soft">
            <li>Choose <strong className="font-semibold text-ink">New case</strong> and give it a short reference. Use initials, not the client&apos;s full name.</li>
            <li>Add the FIR, remand order and other papers, or dictate what you know.</li>
            <li>Review the facts. Each one opens the page it came from. Confirm them to move on to drafting.</li>
            <li>Read the draft grounds and the likely objections, then approve the draft and export.</li>
          </ol>
          <p className="mt-3 text-sm text-ink-soft">For many files at once, use the <Link href="/desk">Batch desk</Link>. To check how courts have reasoned, use the <Link href="/library">Precedent library</Link>.</p>
        </Block>

        <Block id="shortcuts" title="Keyboard shortcuts">
          <dl className="m-0 divide-y divide-line border-y border-line">
            {SHORTCUTS.map((s) => (
              <div key={s.keys} className="grid gap-1 py-2.5 sm:grid-cols-[14rem_1fr]">
                <dt><kbd className="rounded-sm border border-line bg-cream px-1.5 py-0.5 font-sans text-xs text-ink-soft">{s.keys}</kbd></dt>
                <dd className="m-0 text-sm text-ink-soft">{s.does}</dd>
              </div>
            ))}
          </dl>
        </Block>

        <Block id="privacy" title="Privacy">
          <p className="text-ink-soft">
            Your files stay on your machine unless you turn on an external model service, which is off by default and asks for consent. The setting has four modes.
          </p>
          <dl className="m-0 mt-3 divide-y divide-line border-y border-line">
            {PRIVACY_MODES.map((m) => (
              <div key={m.mode} className="grid gap-1 py-2.5 sm:grid-cols-[11rem_1fr]">
                <dt className="font-medium text-ink">{m.mode}</dt>
                <dd className="m-0 text-sm text-ink-soft">{m.what}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-3 text-sm text-ink-soft">
            The mode is set on the server, not in this window. The mode chip at the top shows whether you are on sample data or connected to a server.
          </p>
        </Block>

        <Block id="limits" title="Method and limits">
          <p className="text-ink-soft">
            Drafts are for counsel to review and are not legal advice. Read <Link href="/about">how it works and what it does not do</Link>, including
            the safety rules and the matters it declines.
          </p>
        </Block>

        <Block id="aid" title="Free legal aid">
          <p className="text-ink-soft">If you or someone you know is held and cannot afford a lawyer, free legal aid is a right. Call <a href="tel:15100" className="font-medium">NALSA 15100</a>.</p>
        </Block>
      </div>
    </div>
  );
}

export default HelpPage;
