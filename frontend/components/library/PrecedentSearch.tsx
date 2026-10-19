"use client";
// Precedent search over court reasoning paragraphs (plan §5.2-5.4). A "before" date is REQUIRED: the leakage rule.
import { CalendarClock, GitCompareArrows, Network, Search, TriangleAlert } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent, type ReactElement } from "react";
import { Badge, Button, Input, Skeleton } from "@/components/ui";
import { fieldClasses } from "@/components/ui/input";
import { StatusBadge } from "@/components/common/StatusBadge";
import { getCitationGraph, searchLibrary } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatCourtDate } from "@/lib/format";
import { FACTOR_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { FACTORS, type Factor, type GoodLawStatus, type LibrarySearchHit } from "@/lib/types";

export interface PrecedentSearchProps {
  className?: string;
  /** Open a judgment in the citation graph tab. */
  onOpenGraph?: (docId: string) => void;
  /** Open a section in the bridge tab, e.g. "IPC 420". */
  onOpenBridge?: (ref: string) => void;
}

interface Extra {
  good_law?: GoodLawStatus;
  sc_root?: string | null;
  overruled_by?: string | null;
}

const COURTS = ["Supreme Court", "Delhi HC", "Bombay HC", "Punjab & Haryana HC"];
const OUTCOMES = ["granted", "rejected", "partly granted"];

function hitKey(h: LibrarySearchHit): string {
  return `${h.doc_id}#${h.para}`;
}

export function PrecedentSearch({ className, onOpenGraph, onOpenBridge }: PrecedentSearchProps): ReactElement {
  const [q, setQ] = useState("");
  const [factor, setFactor] = useState<Factor | "">("");
  const [family, setFamily] = useState("");
  const [court, setCourt] = useState("");
  const [outcome, setOutcome] = useState("");
  const [before, setBefore] = useState("");
  const [touched, setTouched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hits, setHits] = useState<LibrarySearchHit[] | null>(null);
  const [extra, setExtra] = useState<Record<string, Extra>>({});

  const beforeMissing = touched && !before;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (!before) return;
    setLoading(true);
    setError(null);
    try {
      setHits(await searchLibrary(q.trim()));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  const results = useMemo(() => {
    if (!hits || !before) return [];
    const fam = family.trim().toLowerCase().replace(/\s+/g, "");
    return hits.filter((h) => {
      if (!(h.date < before)) return false;
      if (factor && !h.factors.includes(factor)) return false;
      if (court && h.court !== court) return false;
      if (outcome && (h.outcome ?? "") !== outcome) return false;
      if (fam && ![...h.section_family, ...h.sections].some((s) => s.toLowerCase().replace(/\s+/g, "").includes(fam))) return false;
      return true;
    });
  }, [hits, before, factor, court, outcome, family]);

  // Good-law and SC root come from the citation graph; fetched for the visible results.
  useEffect(() => {
    let live = true;
    const need = Array.from(new Set(results.slice(0, 12).map((h) => h.doc_id))).filter((id) => !(id in extra));
    if (need.length === 0) return;
    void Promise.all(
      need.map(async (id) => {
        try {
          const g = await getCitationGraph(id);
          const n = g.nodes.find((x) => x.doc_id === id);
          return [id, n ? { good_law: n.good_law, sc_root: n.sc_root, overruled_by: n.overruled_by } : {}] as const;
        } catch {
          return [id, {}] as const;
        }
      }),
    ).then((rows) => {
      if (live) setExtra((prev) => ({ ...prev, ...Object.fromEntries(rows) }));
    });
    return () => { live = false; };
  }, [results, extra]);

  return (
    <div className={cn("space-y-5", className)}>
      <form onSubmit={onSubmit} className="space-y-4 rounded-lg border border-line bg-cream p-4 shadow-sm" noValidate>
        <div className="flex flex-wrap gap-3">
          <div className="min-w-[16rem] flex-1">
            <label htmlFor="lib-q" className="mb-1 block text-sm font-semibold">Search reasoning paragraphs</label>
            <div className="relative">
              <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-muted" />
              <Input id="lib-q" data-testid="library-search" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. parity with co-accused, cheating, charge sheet filed" />
            </div>
          </div>
          <div className="w-full sm:w-52">
            <label htmlFor="lib-before" className="mb-1 flex items-center gap-1 text-sm font-semibold">
              Decided before <span className="text-sindoor" aria-hidden>*</span><span className="sr-only">(required)</span>
            </label>
            <Input
              id="lib-before"
              type="date"
              required
              value={before}
              onChange={(e) => setBefore(e.target.value)}
              aria-invalid={beforeMissing}
              aria-describedby="lib-before-hint"
            />
          </div>
          <div className="flex items-end">
            <Button type="submit" size="lg" disabled={loading}><Search aria-hidden /> {loading ? "Searching" : "Search"}</Button>
          </div>
        </div>
        <p id="lib-before-hint" className={cn("flex items-start gap-2 rounded-md border px-3 py-2 text-sm", beforeMissing ? "border-sindoor/50 bg-sindoor/[0.06] text-sindoor" : "border-gold/40 bg-parchment text-ink-soft")}>
          <CalendarClock aria-hidden className="mt-0.5 size-4 shrink-0" />
          <span>
            <strong>Why a date is required.</strong> Only judgments decided before this date are shown. A brief must never lean on a ruling that
            did not exist when the case was decided, so search cannot run without a cut-off. For a live case, use the date of the application.
          </span>
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm font-semibold">Factor
            <select className={cn(fieldClasses, "mt-1 h-10")} value={factor} onChange={(e) => setFactor(e.target.value as Factor | "")}>
              <option value="">Any factor</option>
              {FACTORS.map((f) => <option key={f} value={f}>{FACTOR_LABELS[f]}</option>)}
            </select>
          </label>
          <label className="text-sm font-semibold">Section family
            <Input className="mt-1" list="lib-families" value={family} onChange={(e) => setFamily(e.target.value)} placeholder="IPC 420 or BNS 318(4)" />
            <datalist id="lib-families"><option value="IPC 420" /><option value="BNS 318(4)" /><option value="IPC 406" /><option value="BNS 316(2)" /></datalist>
          </label>
          <label className="text-sm font-semibold">Court
            <select className={cn(fieldClasses, "mt-1 h-10")} value={court} onChange={(e) => setCourt(e.target.value)}>
              <option value="">Any court</option>
              {COURTS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </label>
          <label className="text-sm font-semibold">Outcome
            <select className={cn(fieldClasses, "mt-1 h-10")} value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option value="">Any outcome</option>
              {OUTCOMES.map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
          </label>
        </div>
        {beforeMissing ? <p role="alert" className="text-sm font-semibold text-sindoor">Choose a &quot;decided before&quot; date to search.</p> : null}
      </form>

      <div role="status" aria-live="polite" className="text-sm text-ink-soft">
        {hits && before ? `${results.length} ${results.length === 1 ? "paragraph" : "paragraphs"} decided before ${formatCourtDate(before)}. Results show reasoning, never grant rates.` : null}
      </div>
      {error ? <p role="alert" className="text-sm text-sindoor">{error}</p> : null}
      {loading ? <div className="space-y-2" aria-busy="true">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-28" />)}</div> : null}

      {hits && !loading ? (
        results.length === 0 ? (
          <p className="rounded-lg border border-dashed border-line-strong/60 bg-cream p-8 text-center text-sm text-ink-soft">
            No paragraph matches these filters before that date. Try a later date or fewer filters.
          </p>
        ) : (
          <ol className="m-0 list-none space-y-3 p-0">
            {results.map((h, i) => {
              const x = extra[h.doc_id] ?? {};
              const gl = h.good_law ?? x.good_law ?? "UNKNOWN";
              const root = x.sc_root;
              const ref = h.sections.find((s) => /^(IPC|BNS)\s/i.test(s));
              return (
                <li key={hitKey(h)} className="rounded-lg border border-line bg-cream p-4 shadow-sm">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                    <span className="font-display text-2xl font-semibold text-maroon/80 tabular" aria-hidden>{i + 1}</span>
                    <h3 className="font-display text-lg font-semibold">{h.citation ?? h.doc_id}</h3>
                    <StatusBadge status={gl} kind="goodLaw" />
                    {h.transfer ? <StatusBadge status={h.transfer} kind="transfer" /> : null}
                  </div>
                  <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-soft">
                    <div className="flex gap-1"><dt className="font-semibold text-ink">Court</dt><dd>{h.court}</dd></div>
                    <div className="flex gap-1"><dt className="font-semibold text-ink">Date</dt><dd>{formatCourtDate(h.date)}</dd></div>
                    {h.outcome ? <div className="flex gap-1"><dt className="font-semibold text-ink">Outcome</dt><dd>{h.outcome}</dd></div> : null}
                    <div className="flex items-center gap-1.5">
                      <dt className="font-semibold text-ink">Authority</dt>
                      <dd className="flex items-center gap-1.5">
                        <span aria-hidden className="inline-block h-1.5 w-16 overflow-hidden rounded-pill bg-line"><span className="block h-full bg-maroon" style={{ width: `${Math.round(h.authority * 100)}%` }} /></span>
                        <span className="tabular">{h.authority.toFixed(2)}</span>
                      </dd>
                    </div>
                    {root ? <div className="flex gap-1"><dt className="font-semibold text-ink">SC root</dt><dd><button type="button" className="rounded-sm font-mono text-xs text-maroon underline underline-offset-2" onClick={() => onOpenGraph?.(root)}>{root}</button></dd></div> : null}
                  </dl>
                  {gl === "OVERRULED" ? (
                    <p role="note" className="mt-2 flex items-start gap-2 rounded-md border border-sindoor/50 bg-sindoor/[0.06] px-3 py-2 text-sm text-sindoor">
                      <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0" />
                      Overruled{x.overruled_by ? ` by ${x.overruled_by}` : ""}. This precedent cannot be cited without a warning.
                    </p>
                  ) : null}
                  <p className="mt-3 max-w-prose font-display text-[15px] leading-relaxed text-ink">{h.text}</p>
                  <div className="mt-3 flex flex-wrap items-center gap-1.5">
                    {h.factors.map((f) => <Badge key={f} variant="outline" shape="pill">{FACTOR_LABELS[f]}</Badge>)}
                    {h.sections.map((s) => <Badge key={s} variant="mono">{s}</Badge>)}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="secondary" onClick={() => onOpenGraph?.(h.doc_id)}><Network aria-hidden /> Citation graph</Button>
                    {ref ? <Button size="sm" variant="ghost" onClick={() => onOpenBridge?.(ref)}><GitCompareArrows aria-hidden /> Bridge {ref}</Button> : null}
                  </div>
                </li>
              );
            })}
          </ol>
        )
      ) : null}
    </div>
  );
}

export default PrecedentSearch;
