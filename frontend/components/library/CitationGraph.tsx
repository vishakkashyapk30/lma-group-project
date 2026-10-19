"use client";
// Citation graph with good-law badges (plan §5.3). Nodes are judgments, edges are treatments. Loaded with
// next/dynamic (ssr: false) by LibraryPage. A table below carries the same information for keyboard and screen-reader users.
import {
  Background, Controls, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactElement } from "react";
import { Button, Input, Skeleton } from "@/components/ui";
import { StatusBadge } from "@/components/common/StatusBadge";
import { getCitationGraph } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { formatCourtDate } from "@/lib/format";
import { TREATMENT_LABELS } from "@/lib/labels";
import { cn } from "@/lib/utils";
import type { CitationGraphData, CitationNode, Treatment } from "@/lib/types";

export interface CitationGraphProps {
  /** Judgment to centre the graph on. */
  docId?: string;
  onSelectDoc?: (docId: string) => void;
  className?: string;
}

const TREATMENT_COLOR: Record<Treatment, string> = {
  FOLLOWED: "rgb(var(--rgb-neem))",
  RELIED_ON: "rgb(var(--rgb-indigo))",
  DISTINGUISHED: "rgb(var(--rgb-haldi))",
  OVERRULED: "rgb(var(--rgb-sindoor))",
  REFERRED: "rgb(var(--rgb-clay))",
  UNKNOWN: "rgb(var(--rgb-ink-soft))",
};
const TREATMENT_DASH: Record<Treatment, string | undefined> = {
  FOLLOWED: undefined,
  RELIED_ON: undefined,
  DISTINGUISHED: "6 4",
  OVERRULED: "2 3",
  REFERRED: "1 5",
  UNKNOWN: "4 4",
};

type JudgmentData = { node: CitationNode; root: boolean; selected: boolean };
type JudgmentNode = Node<JudgmentData, "judgment">;

function JudgmentCard({ data }: NodeProps<JudgmentNode>): ReactElement {
  const { node, root, selected } = data;
  return (
    <div
      className={cn(
        "w-[210px] rounded-md border bg-cream p-2.5 text-left shadow-sm",
        selected ? "border-maroon ring-2 ring-maroon/40" : root ? "border-gold" : "border-line-strong/60",
        node.good_law === "OVERRULED" && "bg-sindoor/[0.04]",
      )}
    >
      <Handle type="target" position={Position.Top} className="!size-1.5 !border-0 !bg-ink-soft" />
      <p className="font-display text-[13px] font-semibold leading-tight text-ink">{node.citation}</p>
      <p className="mt-0.5 text-[11px] text-ink-soft">{node.court} · {formatCourtDate(node.date)}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-1">
        <StatusBadge status={node.good_law} kind="goodLaw" size="sm" />
        {root ? <span className="rounded-sm border border-gold/60 px-1 text-[10px] font-semibold text-ink-soft">focus</span> : null}
      </div>
      <Handle type="source" position={Position.Bottom} className="!size-1.5 !border-0 !bg-ink-soft" />
    </div>
  );
}

const NODE_TYPES = { judgment: JudgmentCard };

const LEVEL_ROW: Record<string, number> = { SC: 0, HC: 1, DC: 2 };

function layout(data: CitationGraphData, selected: string | null): { nodes: JudgmentNode[]; edges: Edge[] } {
  const rows = new Map<number, CitationNode[]>();
  for (const n of data.nodes) {
    const r = LEVEL_ROW[n.court_level] ?? 1;
    rows.set(r, [...(rows.get(r) ?? []), n]);
  }
  const nodes: JudgmentNode[] = [];
  for (const [r, list] of rows) {
    list.sort((a, b) => a.date.localeCompare(b.date));
    list.forEach((n, i) => {
      const x = (i - (list.length - 1) / 2) * 250;
      nodes.push({
        id: n.doc_id,
        type: "judgment",
        position: { x, y: r * 190 },
        data: { node: n, root: n.doc_id === data.root, selected: n.doc_id === selected },
        ariaLabel: `${n.citation}, ${n.court}, good law status ${n.good_law}`,
      });
    });
  }
  const edges: Edge[] = data.edges.map((e, i) => {
    const color = TREATMENT_COLOR[e.treatment];
    return {
      id: `${e.citing_doc_id}->${e.cited_doc_id}-${i}`,
      source: e.citing_doc_id,
      target: e.cited_doc_id,
      label: TREATMENT_LABELS[e.treatment],
      animated: false,
      style: { stroke: color, strokeWidth: 2, strokeDasharray: TREATMENT_DASH[e.treatment] },
      labelStyle: { fill: color, fontWeight: 700, fontSize: 11 },
      labelBgStyle: { fill: "rgb(var(--rgb-cream))", fillOpacity: 0.95 },
      labelBgPadding: [4, 2],
      markerEnd: { type: MarkerType.ArrowClosed, color },
    };
  });
  return { nodes, edges };
}

export function CitationGraph({ docId = "DLHC-2022-1187", onSelectDoc, className }: CitationGraphProps): ReactElement {
  const [input, setInput] = useState(docId);
  const [current, setCurrent] = useState(docId);
  const [data, setData] = useState<CitationGraphData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    setInput(docId);
    setCurrent(docId);
  }, [docId]);

  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    setSelected(null);
    getCitationGraph(current)
      .then((g) => {
        if (!live) return;
        if (!g || !Array.isArray(g.nodes) || !Array.isArray(g.edges)) setError(`No citation graph was found for ${current}.`);
        else setData(g);
      })
      .catch((e) => { if (live) setError(errorMessage(e)); });
    return () => { live = false; };
  }, [current]);

  const flow = useMemo(() => (data ? layout(data, selected) : null), [data, selected]);
  const byId = useMemo(() => new Map((data?.nodes ?? []).map((n) => [n.doc_id, n])), [data]);
  const sel = selected ? byId.get(selected) ?? null : null;

  const onSubmit = useCallback((e: FormEvent) => {
    e.preventDefault();
    if (input.trim()) setCurrent(input.trim());
  }, [input]);

  return (
    <div className={cn("space-y-4", className)}>
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
        <div className="min-w-[16rem] flex-1">
          <label htmlFor="graph-doc" className="mb-1 block text-sm font-semibold">Judgment (document id)</label>
          <Input id="graph-doc" className="font-mono" value={input} onChange={(e) => setInput(e.target.value)} />
        </div>
        <Button type="submit">Show graph</Button>
      </form>

      <ul aria-label="Legend" className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-ink-soft">
        {(Object.keys(TREATMENT_COLOR) as Treatment[]).filter((t) => t !== "UNKNOWN").map((t) => (
          <li key={t} className="flex items-center gap-1.5">
            <svg width="28" height="8" aria-hidden><line x1="0" y1="4" x2="28" y2="4" stroke={TREATMENT_COLOR[t]} strokeWidth="2" strokeDasharray={TREATMENT_DASH[t]} /></svg>
            {TREATMENT_LABELS[t]}
          </li>
        ))}
        <li>Supreme Court judgments sit on the top row.</li>
      </ul>

      {error ? <p role="alert" className="rounded-md border border-sindoor/50 bg-sindoor/[0.06] p-3 text-sm text-sindoor">{error}</p> : null}
      {!data && !error ? <Skeleton className="h-[32rem]" /> : null}
      {flow ? (
        <div className="h-[34rem] overflow-hidden rounded-lg border border-line bg-parchment" role="region" aria-label="Citation graph. A table with the same information follows.">
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            nodeTypes={NODE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.2 }}
            nodesDraggable={false}
            nodesConnectable={false}
            minZoom={0.3}
            proOptions={{ hideAttribution: true }}
            onNodeClick={(_, n) => setSelected(n.id)}
          >
            <Background color="rgb(176 141 87 / 0.35)" gap={22} />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
      ) : null}

      {sel ? (
        <section aria-label="Selected judgment" className="rounded-lg border border-gold/50 bg-cream p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-display text-lg font-semibold">{sel.citation}</h3>
            <StatusBadge status={sel.good_law} kind="goodLaw" />
          </div>
          <p className="mt-1 text-sm text-ink-soft">
            {sel.court} · {formatCourtDate(sel.date)} · authority {sel.authority.toFixed(2)}
            {sel.sc_root ? <> · SC root <span className="font-mono text-xs">{sel.sc_root}</span></> : null}
          </p>
          {sel.good_law === "OVERRULED" ? (
            <p role="note" className="mt-2 text-sm font-semibold text-sindoor">Overruled{sel.overruled_by ? ` by ${sel.overruled_by}` : ""}. Cite only with a warning.</p>
          ) : null}
          <div className="mt-2 flex gap-2">
            {onSelectDoc ? <Button size="sm" variant="secondary" onClick={() => { onSelectDoc(sel.doc_id); }}>Centre on this judgment</Button> : null}
          </div>
        </section>
      ) : null}

      {data ? (
        <details className="rounded-lg border border-line bg-cream p-3">
          <summary className="cursor-pointer text-sm font-semibold text-maroon">Treatments as a table ({data.edges.length})</summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Who cites whom and how</caption>
              <thead><tr className="border-b border-line text-xs uppercase tracking-caps text-ink-soft"><th scope="col" className="py-1 pr-3">Citing</th><th scope="col" className="py-1 pr-3">Treatment</th><th scope="col" className="py-1 pr-3">Cited</th><th scope="col" className="py-1">Cited status</th></tr></thead>
              <tbody>
                {data.edges.map((e, i) => {
                  const cited = byId.get(e.cited_doc_id);
                  return (
                    <tr key={i} className="border-b border-line/60 align-top">
                      <td className="py-1.5 pr-3">{byId.get(e.citing_doc_id)?.citation ?? e.citing_doc_id}</td>
                      <td className="py-1.5 pr-3 font-semibold" style={{ color: TREATMENT_COLOR[e.treatment] }}>{TREATMENT_LABELS[e.treatment]}</td>
                      <td className="py-1.5 pr-3">{cited?.citation ?? e.cited_doc_id}</td>
                      <td className="py-1.5">{cited ? <StatusBadge status={cited.good_law} kind="goodLaw" size="sm" /> : null}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </div>
  );
}

export default CitationGraph;
