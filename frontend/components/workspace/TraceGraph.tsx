"use client";
// The live agent-trace graph (plan §13.1, §13.4): agents, tools and stores as nodes; an edge lights as each call happens.
// Built from the event stream, so it works the same in live and demo mode. Loaded through next/dynamic (ssr: false).
import "@xyflow/react/dist/style.css";
import { Background, Controls, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMemo, type ReactElement } from "react";
import { AGENTS, isAgentName } from "@/lib/agents";
import { STORES, STORE_LIST, storeForEvent } from "@/lib/stores";
import type { AgentEvent, AgentName } from "@/lib/types";
import { AGENT_NAMES } from "@/lib/types";
import { useReducedMotion } from "@/lib/useReducedMotion";

export interface TraceGraphProps {
  events: readonly AgentEvent[];
  /** Index where the current run starts (ActivityState.runStart). */
  runStart: number;
  className?: string;
}

/** Events that move work between an agent, a tool and a store. */
const TRACE_KINDS = new Set(["TOOL_CALL", "TOOL_RESULT", "STORE_WRITE"]);
const MAX_TOOLS = 14;
const RECENT = 6;

interface Hop {
  agent: AgentName | null;
  tool: string | null;
  store: string | null;
  recent: boolean;
  latest: boolean;
}

function traceHops(events: readonly AgentEvent[], runStart: number): Hop[] {
  let window = events.slice(runStart).filter((e) => TRACE_KINDS.has(e.kind));
  if (window.length < 3) window = events.filter((e) => TRACE_KINDS.has(e.kind)).slice(-40);
  return window.map((e, i) => {
    const actor = typeof e.actor === "string" ? e.actor.toUpperCase() : "";
    return {
      agent: isAgentName(actor) ? actor : null,
      tool: e.tool ?? null,
      store: storeForEvent(e),
      recent: i >= window.length - RECENT,
      latest: i === window.length - 1,
    };
  });
}

const COL = { agent: 0, tool: 215, store: 450 };
const ROW = 52;

const palette = {
  maroon: "rgb(var(--rgb-maroon))",
  cream: "rgb(var(--rgb-cream))",
  parchment: "rgb(var(--rgb-parchment-deep))",
  ink: "rgb(var(--rgb-ink))",
  gold: "rgb(var(--rgb-gold-leaf))",
  line: "rgb(var(--rgb-line-strong))",
};

export default function TraceGraph({ events, runStart, className }: TraceGraphProps): ReactElement {
  const reduced = useReducedMotion();

  const { nodes, edges } = useMemo(() => {
    const hops = traceHops(events, runStart);
    const agentUse = new Map<AgentName, { recent: boolean; latest: boolean }>();
    const toolUse = new Map<string, { recent: boolean; latest: boolean; order: number }>();
    const storeUse = new Map<string, { recent: boolean; latest: boolean }>();
    const edgeUse = new Map<string, { source: string; target: string; count: number; recent: boolean; latest: boolean }>();
    const bump = (m: Map<string, { source: string; target: string; count: number; recent: boolean; latest: boolean }>, source: string, target: string, h: Hop) => {
      const key = `${source}>${target}`;
      const cur = m.get(key) ?? { source, target, count: 0, recent: false, latest: false };
      m.set(key, { ...cur, count: cur.count + 1, recent: cur.recent || h.recent, latest: cur.latest || h.latest });
    };
    hops.forEach((h, i) => {
      if (h.agent) agentUse.set(h.agent, { recent: h.recent || Boolean(agentUse.get(h.agent)?.recent), latest: h.latest || Boolean(agentUse.get(h.agent)?.latest) });
      if (h.tool) toolUse.set(h.tool, { recent: h.recent || Boolean(toolUse.get(h.tool)?.recent), latest: h.latest || Boolean(toolUse.get(h.tool)?.latest), order: i });
      if (h.store) storeUse.set(h.store, { recent: h.recent || Boolean(storeUse.get(h.store)?.recent), latest: h.latest || Boolean(storeUse.get(h.store)?.latest) });
      if (h.agent && h.tool) bump(edgeUse, `a:${h.agent}`, `t:${h.tool}`, h);
      if (h.tool && h.store) bump(edgeUse, `t:${h.tool}`, `s:${h.store}`, h);
      else if (h.agent && h.store) bump(edgeUse, `a:${h.agent}`, `s:${h.store}`, h);
    });

    const keptTools = Array.from(toolUse.entries()).sort((a, b) => b[1].order - a[1].order).slice(0, MAX_TOOLS).map(([t]) => t);
    const toolOrder = keptTools.sort((a, b) => (toolUse.get(a)?.order ?? 0) - (toolUse.get(b)?.order ?? 0));
    const agents = AGENT_NAMES.filter((a) => agentUse.has(a));
    const stores = STORE_LIST.map((s) => s.id).filter((s) => storeUse.has(s));

    const ns: Node[] = [];
    const place = (items: string[], x: number, make: (id: string, y: number) => Node) => {
      const offset = (Math.max(agents.length, toolOrder.length, stores.length) - items.length) * ROW * 0.5;
      items.forEach((id, i) => ns.push(make(id, offset + i * ROW)));
    };
    const base = { draggable: false, selectable: false, connectable: false, focusable: false } as const;

    place(agents, COL.agent, (id, y) => {
      const u = agentUse.get(id as AgentName)!;
      return {
        id: `a:${id}`, position: { x: COL.agent, y }, ...base,
        data: { label: AGENTS[id as AgentName].name },
        className: u.latest && !reduced ? "animate-breathe" : undefined,
        style: {
          width: 150, background: palette.maroon, color: palette.cream, border: `2px solid ${u.recent ? palette.gold : palette.maroon}`,
          borderRadius: 8, fontFamily: "var(--font-display)", fontWeight: 600, fontSize: 13, opacity: u.recent ? 1 : 0.7,
          boxShadow: u.recent ? `0 0 0 3px rgb(var(--rgb-gold-leaf) / 0.35)` : "none",
        },
        sourcePosition: "right", targetPosition: "left",
      } as Node;
    });
    place(toolOrder, COL.tool, (id, y) => {
      const u = toolUse.get(id)!;
      return {
        id: `t:${id}`, position: { x: COL.tool, y }, ...base,
        data: { label: id },
        className: u.latest && !reduced ? "animate-breathe" : undefined,
        style: {
          width: 170, background: palette.cream, color: palette.ink, border: `${u.recent ? 2 : 1}px solid ${u.recent ? palette.maroon : palette.line}`,
          borderRadius: 6, fontFamily: "var(--font-mono)", fontSize: 11.5, opacity: u.recent ? 1 : 0.7,
        },
        sourcePosition: "right", targetPosition: "left",
      } as Node;
    });
    place(stores, COL.store, (id, y) => {
      const u = storeUse.get(id)!;
      return {
        id: `s:${id}`, position: { x: COL.store, y }, ...base,
        data: { label: STORES[id as keyof typeof STORES].label + " · " + id.split(".")[0] },
        className: u.latest && !reduced ? "animate-breathe" : undefined,
        style: {
          width: 160, background: palette.parchment, color: palette.ink, border: `${u.recent ? 2 : 1}px dashed ${u.recent ? palette.gold : palette.line}`,
          borderRadius: 6, fontSize: 11.5, opacity: u.recent ? 1 : 0.7,
        },
        sourcePosition: "right", targetPosition: "left",
      } as Node;
    });

    const known = new Set(ns.map((n) => n.id));
    const es: Edge[] = Array.from(edgeUse.values())
      .filter((e) => known.has(e.source) && known.has(e.target))
      .map((e) => ({
        id: `${e.source}>${e.target}`, source: e.source, target: e.target,
        animated: e.latest && !reduced,
        label: e.count > 1 ? `×${e.count}` : undefined,
        labelStyle: { fontSize: 10, fontFamily: "var(--font-mono)" },
        style: { stroke: e.recent ? palette.gold : palette.line, strokeWidth: e.recent ? 2.4 : 1.2, opacity: e.recent ? 1 : 0.6 },
      }));
    return { nodes: ns, edges: es };
  }, [events, runStart, reduced]);

  return (
    <div className={className} style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        nodesDraggable={false}
        nodesConnectable={false}
        nodesFocusable={false}
        edgesFocusable={false}
        elementsSelectable={false}
        zoomOnScroll={false}
        panOnScroll={false}
        minZoom={0.3}
        maxZoom={1.4}
        proOptions={{ hideAttribution: false }}
        aria-label="Agent trace graph"
      >
        <Background gap={20} color="rgb(var(--rgb-line))" />
        <Controls showInteractive={false} position="bottom-left" />
      </ReactFlow>
    </div>
  );
}
