// The ten stores on four shelves (plan §5.1) and the tools that reach them (plan §4.3, §6, §7.1, §8.1). Used by tool
// chips, the trace graph, Munshi's four shelves and Sutradhar's 24-spoke wheel.
import type { AgentEvent, AgentName, Shelf, StoreName } from "./types";

export interface ShelfMeta {
  id: Shelf;
  label: string;
  description: string;
}

export const SHELF_META: Record<Shelf, ShelfMeta> = {
  law: { id: "law", label: "Law", description: "Statutes and the IPC↔BNS concordance graph" },
  caselaw: { id: "caselaw", label: "Case law", description: "Reasoning paragraphs, the citation graph and similar facts" },
  advocacy: { id: "advocacy", label: "Advocacy", description: "What each side usually argues" },
  case: { id: "case", label: "Case", description: "This client's documents, timeline and facts (private)" },
};

/** Shelf order for Munshi's four shelves and the wheel (case shelf first: it is what Munshi files into). */
export const SHELF_ORDER: readonly Shelf[] = ["case", "law", "caselaw", "advocacy"];

export type IndexKind = "exact" | "graph" | "hybrid" | "vectors";

export interface StoreMeta {
  id: StoreName;
  shelf: Shelf;
  label: string;
  index: IndexKind;
  indexLabel: string;
  tools: string[];
  contents: string;
}

export const STORES: Record<StoreName, StoreMeta> = {
  "law.statutes": { id: "law.statutes", shelf: "law", label: "Statutes", index: "exact", indexLabel: "Exact lookup + BM25", tools: ["get_statute", "search_statutes"], contents: "IPC, BNS, CrPC, BNSS and the special-act bail bars" },
  "law.concordance": { id: "law.concordance", shelf: "law", label: "Concordance", index: "graph", indexLabel: "Graph", tools: ["map_section", "transfer_check"], contents: "IPC↔BNS and CrPC↔BNSS edges with text diffs" },
  "caselaw.reasoning": { id: "caselaw.reasoning", shelf: "caselaw", label: "Reasoning", index: "hybrid", indexLabel: "BM25 + BGE-M3", tools: ["search_reasoning", "get_paragraph"], contents: "Court reasoning paragraphs from bail orders" },
  "caselaw.citations": { id: "caselaw.citations", shelf: "caselaw", label: "Citations", index: "graph", indexLabel: "Graph + authority score", tools: ["citations", "good_law_check"], contents: "Who cites whom, with treatment" },
  "caselaw.similar": { id: "caselaw.similar", shelf: "caselaw", label: "Similar facts", index: "vectors", indexLabel: "Whole-order vectors", tools: ["similar_orders"], contents: "One vector per order's facts, plus a fact signature" },
  "advocacy.arguments": { id: "advocacy.arguments", shelf: "advocacy", label: "Arguments", index: "hybrid", indexLabel: "Hybrid + filters", tools: ["search_arguments"], contents: "Defence submissions by factor (never cited as authority)" },
  "advocacy.objections": { id: "advocacy.objections", shelf: "advocacy", label: "Objections", index: "hybrid", indexLabel: "Hybrid + filters", tools: ["search_objections"], contents: "Prosecution submissions by factor" },
  "case.docs": { id: "case.docs", shelf: "case", label: "Documents", index: "hybrid", indexLabel: "Hybrid", tools: ["search_case_docs"], contents: "The client's documents in structure-aware chunks" },
  "case.timeline": { id: "case.timeline", shelf: "case", label: "Timeline", index: "exact", indexLabel: "Exact lookup", tools: ["get_timeline", "date_calc"], contents: "Dated events with sources" },
  "case.facts": { id: "case.facts", shelf: "case", label: "Facts", index: "exact", indexLabel: "Exact lookup", tools: ["get_fact"], contents: "The dossier, every field with status and source" },
};

export const STORE_LIST: readonly StoreMeta[] = Object.values(STORES);

export function storesOnShelf(shelf: Shelf): StoreMeta[] {
  return STORE_LIST.filter((s) => s.shelf === shelf);
}

export interface ToolMeta {
  name: string;
  label: string;
  /** Store the tool reads or writes, if any. */
  store?: StoreName;
  agents: AgentName[];
}

const t = (name: string, label: string, agents: AgentName[], store?: StoreName): ToolMeta => ({ name, label, agents, store });

/** Every tool named in the plan. */
export const TOOLS: Record<string, ToolMeta> = Object.fromEntries(
  [
    // Munshi (plan §4.3)
    t("inspect_page", "Inspect page", ["MUNSHI"]),
    t("read_text_layer", "Read text layer", ["MUNSHI"]),
    t("parse_layout", "Parse layout", ["MUNSHI"]),
    t("clean_image", "Clean image", ["MUNSHI"]),
    t("ocr_page", "OCR page", ["MUNSHI"]),
    t("vision_read_page", "Vision read", ["MUNSHI"]),
    t("detect_script", "Detect script", ["MUNSHI"]),
    t("translate", "Translate hi→en", ["MUNSHI"]),
    t("transcribe", "Transcribe audio", ["MUNSHI"]),
    t("split_bundle", "Split bundle", ["MUNSHI"]),
    t("classify_document", "Classify document", ["MUNSHI"]),
    t("pseudonymise", "Pseudonymise", ["MUNSHI"]),
    t("file_item", "File item", ["MUNSHI"]),
    t("search_pages", "Search pages", ["MUNSHI"]),
    t("ask_user", "Ask counsel", ["MUNSHI", "PESHKAR"]),
    // Peshkar (plan §7.1)
    t("extract_dossier", "Extract dossier", ["PESHKAR"], "case.facts"),
    t("span_check", "Span check", ["PESHKAR"]),
    t("rights_check", "Rights Radar", ["PESHKAR", "SUTRADHAR"]),
    t("diff_case_state", "Diff case state", ["PESHKAR"]),
    // Stores (plan §5.1)
    t("get_statute", "Get statute", ["SUTRADHAR", "VAKEEL", "ABHIYOJAK"], "law.statutes"),
    t("search_statutes", "Search statutes", ["SUTRADHAR", "ABHIYOJAK"], "law.statutes"),
    t("map_section", "Map section", ["PESHKAR", "SUTRADHAR", "VAKEEL"], "law.concordance"),
    t("transfer_check", "Transfer check", ["SUTRADHAR", "VAKEEL"], "law.concordance"),
    t("search_reasoning", "Search reasoning", ["SUTRADHAR", "VAKEEL", "ABHIYOJAK"], "caselaw.reasoning"),
    t("get_paragraph", "Get paragraph", ["VAKEEL"], "caselaw.reasoning"),
    t("citations", "Citations", ["SUTRADHAR", "VAKEEL"], "caselaw.citations"),
    t("good_law_check", "Good-law check", ["VAKEEL"], "caselaw.citations"),
    t("similar_orders", "Similar orders", ["SUTRADHAR", "VAKEEL"], "caselaw.similar"),
    t("search_arguments", "Search arguments", ["SUTRADHAR", "VAKEEL"], "advocacy.arguments"),
    t("search_objections", "Search objections", ["SUTRADHAR", "ABHIYOJAK"], "advocacy.objections"),
    t("search_case_docs", "Search case docs", ["SUTRADHAR", "VAKEEL", "ABHIYOJAK", "PESHKAR"], "case.docs"),
    t("get_timeline", "Get timeline", ["PESHKAR", "SUTRADHAR"], "case.timeline"),
    t("date_calc", "Date calc", ["PESHKAR", "SUTRADHAR"], "case.timeline"),
    t("get_fact", "Get fact", ["SUTRADHAR", "VAKEEL", "ABHIYOJAK"], "case.facts"),
    // Vakeel (plan §8.1)
    t("check_claim", "Check claim", ["VAKEEL"]),
    t("render_citation", "Render citation", ["VAKEEL"]),
    t("assemble_application", "Assemble application", ["VAKEEL"]),
    t("request_approval", "Request approval", ["PESHKAR", "VAKEEL"]),
    t("export", "Export", ["VAKEEL"]),
    // Pairokar (plan §11)
    t("triage_case", "Triage case", ["PAIROKAR"]),
  ].map((m) => [m.name, m]),
);

/** Store a tool reads, if known. */
export function storeForTool(tool: string | null | undefined): StoreName | null {
  if (!tool) return null;
  return TOOLS[tool]?.store ?? null;
}

export function toolLabel(tool: string): string {
  return TOOLS[tool]?.label ?? tool.replace(/_/g, " ");
}

/**
 * Sutradhar's 24 spokes (plan §13.4): the fifteen store tools in shelf order, then the nine checking and control
 * tools. Each spoke lights as its tool (or a tool on its store) is queried.
 */
export const WHEEL_SPOKES: readonly { index: number; tool: string; store: StoreName | null; shelf: Shelf | null }[] = [
  "search_case_docs", "get_timeline", "date_calc", "get_fact",
  "get_statute", "search_statutes", "map_section", "transfer_check",
  "search_reasoning", "get_paragraph", "citations", "good_law_check", "similar_orders",
  "search_arguments", "search_objections",
  "rights_check", "span_check", "check_claim", "render_citation", "extract_dossier", "diff_case_state",
  "assemble_application", "request_approval", "ask_user",
].map((tool, index) => {
  const store = storeForTool(tool);
  return { index, tool, store, shelf: store ? STORES[store].shelf : null };
});

/** Spoke to light for an event: its tool's spoke, else the first spoke on its store; null if neither. */
export function spokeForEvent(event: Pick<AgentEvent, "tool" | "inputs">): number | null {
  const tool = event.tool ?? null;
  if (tool) {
    const hit = WHEEL_SPOKES.find((s) => s.tool === tool);
    if (hit) return hit.index;
  }
  const store = (typeof event.inputs?.store === "string" ? event.inputs.store : null) ?? storeForTool(tool);
  if (store) {
    const hit = WHEEL_SPOKES.find((s) => s.store === store);
    if (hit) return hit.index;
  }
  return null;
}

/** Store an event touched: inputs.store, else its tool's store. */
export function storeForEvent(event: Pick<AgentEvent, "tool" | "inputs">): StoreName | null {
  const s = event.inputs?.store;
  if (typeof s === "string" && s in STORES) return s as StoreName;
  return storeForTool(event.tool);
}
