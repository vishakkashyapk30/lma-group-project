"use client";
// Privacy: what leaves this computer in each setting of the external-services switch (VS_EXTERNAL). Off is the default.
// The example is a real line of the sample FIR as an external service would receive it: names already replaced.
import { ArrowRight, Ban } from "lucide-react";
import { useState, type ReactElement } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { READ_FACTS } from "../sample";

const PARTIES = READ_FACTS.find((f) => f.key === "parties")!;

const MODES = [
  { id: "off", label: "Off", sends: null, body: "Nothing leaves. Reading, checking and drafting run on this computer. This is the default." },
  { id: "public", label: "Public", sends: "Public law text only: sections of the statutes and published judgments.", body: "No line of the case file is sent." },
  {
    id: "pseudonymised",
    label: "Pseudonymised",
    sends: PARTIES.quoteEn,
    body: "Case text after names, places and numbers are replaced, as in the line above from the sample FIR. Page images and audio are never sent.",
  },
  { id: "consented", label: "Consented", sends: PARTIES.quoteEn, body: "As pseudonymised, and only for a case whose client has consented. The consent is recorded with the case." },
] as const;

export function PrivacyDemo({ className }: { className?: string }): ReactElement {
  const [mode, setMode] = useState<(typeof MODES)[number]["id"]>("off");
  return (
    <div data-testid="privacy-demo" className={cn("rounded-lg bg-cream p-4 sm:p-5", className)}>
      <Tabs value={mode} onValueChange={(v) => setMode(v as typeof mode)}>
        <TabsList aria-label="External model services">
          {MODES.map((m) => (
            <TabsTrigger key={m.id} value={m.id} data-testid={`privacy-${m.id}`}>{m.label}</TabsTrigger>
          ))}
        </TabsList>
        {MODES.map((m) => (
          <TabsContent key={m.id} value={m.id} className="pt-4">
            <div className="grid items-stretch gap-3 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
              <div className="rounded-md border border-line-strong/60 p-3">
                <p className="text-sm font-semibold text-ink">This computer</p>
                <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">
                  <li>The case papers, page images and audio</li>
                  <li>The dossier, the drafts and the record of approvals</li>
                  <li>The models that run here</li>
                </ul>
              </div>
              <div aria-hidden className="grid place-items-center text-ink-muted">
                {m.sends ? <ArrowRight className="size-5 rotate-90 sm:rotate-0" /> : <Ban className="size-5" />}
              </div>
              <div className={cn("rounded-md p-3", m.sends ? "border border-line-strong/60" : "border border-dashed border-line-strong/60")}>
                <p className="text-sm font-semibold text-ink">External model services</p>
                {m.sends ? (
                  <p data-testid="privacy-sends" className={cn("mt-1 text-sm text-ink", m.id !== "public" && "font-mono text-[12px]")}>{m.sends}</p>
                ) : (
                  <p data-testid="privacy-sends" className="mt-1 text-sm text-ink-soft">Receive nothing.</p>
                )}
              </div>
            </div>
            <p className="mt-3 text-sm text-ink-soft">{m.body}</p>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
