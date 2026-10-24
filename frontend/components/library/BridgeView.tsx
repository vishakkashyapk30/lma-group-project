"use client";
// IPC<->BNS bridge with text diff and transfer flag (plan §5.4).
import { ArrowLeftRight } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent, type ReactElement } from "react";
import { Badge, Button, Input, Skeleton } from "@/components/ui";
import { StatusBadge } from "@/components/common/StatusBadge";
import { getBridge } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { EDGE_TYPE_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { BridgeData, DiffSegment } from "@/lib/types";

export interface BridgeViewProps {
  /** Starting section, e.g. "IPC 420" or "BNS 318(4)". */
  initialRef?: string;
  className?: string;
}

const PRESETS = ["IPC 420", "IPC 406", "BNS 318(4)"];

function splitRef(ref: string): { code: string; section: string } | null {
  const m = /^\s*(IPC|BNS|CRPC|BNSS)\s+(.+?)\s*$/i.exec(ref);
  return m ? { code: m[1].toUpperCase(), section: m[2] } : null;
}

/** One side of the diff: unchanged words plain, removed (old side) or added (new side) words marked by more than colour. */
function DiffText({ segments, side }: { segments: DiffSegment[]; side: "old" | "new" }): ReactElement {
  return (
    <p className="font-display text-[15px] leading-relaxed text-ink">
      {segments.map((s, i) => {
        if (s.op === "equal") return <span key={i}>{s.text}</span>;
        if (s.op === "delete" && side === "old")
          return <del key={i} className="rounded-sm bg-sindoor/15 px-0.5 text-sindoor decoration-sindoor"><span className="sr-only">[removed: </span>{s.text}<span className="sr-only">]</span></del>;
        if (s.op === "insert" && side === "new")
          return <ins key={i} className="rounded-sm bg-neem/15 px-0.5 font-semibold text-neem underline decoration-neem"><span className="sr-only">[added: </span>{s.text}<span className="sr-only">]</span></ins>;
        return null;
      })}
    </p>
  );
}

export function BridgeView({ initialRef = "IPC 420", className }: BridgeViewProps): ReactElement {
  const [input, setInput] = useState(initialRef);
  const [data, setData] = useState<BridgeData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (ref: string) => {
    const p = splitRef(ref);
    if (!p) {
      setError("Enter a code and section, for example IPC 420 or BNS 318(4).");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getBridge(p.code, p.section);
      if (!res || !res.old_ref || !Array.isArray(res.diff)) {
        setData(null);
        setError(`No concordance entry was found for ${ref}.`);
      } else {
        setData(res);
      }
    } catch (e) {
      setData(null);
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setInput(initialRef);
    void load(initialRef);
  }, [initialRef, load]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (loading) return;
    void load(input);
  }

  const same = data ? data.diff.every((s) => s.op === "equal") : false;

  return (
    <div data-testid="bridge-view" className={cn("space-y-5", className)}>
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
        <div className="min-w-[14rem] flex-1">
          <label htmlFor="bridge-ref" className="mb-1 block text-sm font-semibold">Section (IPC, BNS, CrPC or BNSS)</label>
          <Input id="bridge-ref" value={input} onChange={(e) => setInput(e.target.value)} placeholder="IPC 420" />
        </div>
        <Button type="submit" aria-busy={loading || undefined}>{loading ? "Looking up" : "Show bridge"}</Button>
        <div className="flex flex-wrap gap-1.5" aria-label="Examples">
          {PRESETS.map((p) => <Button key={p} type="button" size="sm" variant="pill" onClick={() => { setInput(p); void load(p); }}>{p}</Button>)}
        </div>
      </form>

      {error ? <p role="alert" className="rounded-md border border-sindoor/50 bg-sindoor/[0.06] p-3 text-sm text-sindoor">{error}</p> : null}
      {loading && !data ? <Skeleton className="h-64" /> : null}

      {data ? (
        <section aria-label={`${data.old_ref} and ${data.new_ref}`} className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[1fr_11rem_1fr]">
            <article className="rounded-lg border border-line bg-cream p-4">
              <p className="text-xs font-semibold text-ink-soft">Old law</p>
              <h3 className="font-display text-2xl font-semibold text-maroon">{data.old_ref}</h3>
              {data.old_heading ? <p className="text-sm text-ink-soft">{data.old_heading}</p> : null}
              <div className="mt-3"><DiffText segments={data.diff} side="old" /></div>
              {data.old_max_punishment ? <p className="mt-3 text-sm"><span className="font-semibold">Maximum:</span> {data.old_max_punishment}</p> : null}
            </article>

            <div className="flex flex-col items-center justify-center gap-2 text-center" aria-label="Link between the sections">
              <div aria-hidden className="hidden h-px w-full bg-gold lg:block" />
              <ArrowLeftRight aria-hidden className="size-5 text-maroon" />
              <Badge variant="solid" size="lg">{EDGE_TYPE_LABELS[data.edge_type]}</Badge>
              <StatusBadge status={data.flag} kind="transfer" />
              <p className="text-xs text-ink-soft">Transfer flag for precedents under {data.old_ref.split(" ")[0]}</p>
              <div aria-hidden className="hidden h-px w-full bg-gold lg:block" />
            </div>

            <article className="rounded-lg border border-line bg-cream p-4">
              <p className="text-xs font-semibold text-ink-soft">New law</p>
              <h3 className="font-display text-2xl font-semibold text-maroon">{data.new_ref}</h3>
              {data.new_heading ? <p className="text-sm text-ink-soft">{data.new_heading}</p> : null}
              <div className="mt-3"><DiffText segments={data.diff} side="new" /></div>
              {data.new_max_punishment ? <p className="mt-3 text-sm"><span className="font-semibold">Maximum:</span> {data.new_max_punishment}</p> : null}
            </article>
          </div>

          <p role="status" className={cn("rounded-md border px-3 py-2 text-sm", same ? "border-neem/50 bg-neem/[0.07] text-neem" : "border-haldi/50 bg-haldi/[0.07] text-haldi")}>
            {same
              ? "The wording was carried over unchanged, so precedents decided under the old section apply."
              : "The wording changed. Precedents under the old section are usable only with a qualification, which the brief must state."}
          </p>
          {data.qualification ? (
            <p className="rounded-md border border-gold/50 bg-parchment p-3 text-sm"><span className="font-semibold">Qualification for the brief:</span> {data.qualification}</p>
          ) : null}

          {data.text_diff ? (
            <div>
              <h4 className="mb-1 font-sans text-sm font-semibold">Text diff</h4>
              <pre className="max-h-60 overflow-auto whitespace-pre-wrap rounded-md border border-line bg-cream p-3 font-mono text-xs leading-relaxed text-ink" tabIndex={0}>{data.text_diff}</pre>
            </div>
          ) : null}

          {(data.related ?? []).length > 0 ? (
            <div>
              <h4 className="mb-1 font-sans text-sm font-semibold">Neighbouring sections</h4>
              <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
                {(data.related ?? []).map((r) => (
                  <li key={`${r.old_ref}-${r.new_ref}`}>
                    <button
                      type="button"
                      onClick={() => { setInput(r.old_ref); void load(r.old_ref); }}
                      className="inline-flex items-center gap-2 rounded-md border border-line-strong/60 bg-cream px-2.5 py-1.5 text-sm hover:bg-parchment-deep"
                    >
                      <span className="font-mono text-xs">{r.old_ref}</span>
                      <ArrowLeftRight aria-hidden className="size-3.5 text-ink-muted" />
                      <span className="font-mono text-xs">{r.new_ref}</span>
                      <Badge variant="outline" size="sm">{EDGE_TYPE_LABELS[r.type]}</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

export default BridgeView;
