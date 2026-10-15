// The six agents (plan §3.2, §13.4). Court-office names with English subtitles; each has one motif and one glyph.
import type { AgentName, Stage } from "./types";
import { AGENT_NAMES } from "./types";

/** Glyph ids drawn by components/common/AgentGlyph. */
export type AgentGlyphKind = "papers" | "calendar" | "wheel" | "manuscript" | "scales" | "bars";

export interface AgentMeta {
  id: AgentName;
  /** Court-office name shown in the UI. */
  name: string;
  /** The name in Devanagari (real text, never an image). */
  nameHi: string;
  /** English subtitle, shown with the name everywhere ("Munshi · Intake agent"). */
  subtitle: string;
  /** Who that is in a court office (plan §3.2). */
  role: string;
  /** What the agent does. */
  job: string;
  /** Signature motif (plan §13.4). */
  motif: string;
  glyph: AgentGlyphKind;
  /** The subtle working loop (<= 2 s, low amplitude). */
  working: string;
  /** The full version (plays once per session or on click). */
  full: string;
  /** Where the animation lives. */
  where: string;
  /** Workspace stages the agent works in. */
  stages: Stage[];
  /** Model and where it runs (plan §3.2). */
  runsOn: string;
  /** Static status text under reduced motion, while working. */
  workingText: string;
  /** Static status text when idle. */
  idleText: string;
}

export const AGENTS: Record<AgentName, AgentMeta> = {
  MUNSHI: {
    id: "MUNSHI",
    name: "Munshi",
    nameHi: "मुंशी",
    subtitle: "Intake agent",
    role: "An advocate's clerk, who keeps the papers",
    job: "Reads every page, splits bundles, labels documents, files each item and asks for what is missing.",
    motif: "Paper storm",
    glyph: "papers",
    working: "Page cards flip and gain route badges (TEXT, LAYOUT, OCR, VISION) and a document-type stamp.",
    full: "The pages fly onto the four shelves.",
    where: "Intake stage, case-file pane",
    stages: ["INTAKE"],
    runsOn: "Qwen3-4B + OCR + vision model, on counsel's laptop",
    workingText: "Munshi is reading and filing pages",
    idleText: "Munshi: papers filed",
  },
  PESHKAR: {
    id: "PESHKAR",
    name: "Peshkar",
    nameHi: "पेशकार",
    subtitle: "Dossier & Rights Radar",
    role: "The court reader, who keeps the file and the dates",
    job: "Builds the source-checked dossier, the List of Dates and the Rights Radar, and detects changes.",
    motif: "Calendar and bars",
    glyph: "calendar",
    working: "Calendar pages tick; custody bars grow.",
    full: "The Rights Radar sweeps the timeline and flags pop out as chips.",
    where: "Dates and Rights tabs",
    stages: ["DOSSIER", "RIGHTS"],
    runsOn: "Fine-tuned Qwen3-4B + rules, on counsel's laptop",
    workingText: "Peshkar is checking the dossier and the dates",
    idleText: "Peshkar: dossier ready for review",
  },
  SUTRADHAR: {
    id: "SUTRADHAR",
    name: "Sutradhar",
    nameHi: "सूत्रधार",
    subtitle: "Orchestrator",
    role: "“The one who holds the strings”, the director in Indian theatre",
    job: "Decides, per bail factor, what to fetch from which of ten stores, checks sufficiency and stops within budget.",
    motif: "24-spoke wheel",
    glyph: "wheel",
    working: "Each spoke lights as its store or tool is queried.",
    full: "“Show the plan” opens the live trace graph.",
    where: "Chat header, trace drawer",
    stages: ["BRIEF"],
    runsOn: "Qwen3-14B, on the Ada cluster (pseudonymised text only)",
    workingText: "Sutradhar is planning retrieval",
    idleText: "Sutradhar: plan complete",
  },
  VAKEEL: {
    id: "VAKEEL",
    name: "Vakeel",
    nameHi: "वकील",
    subtitle: "Drafter",
    role: "The advocate",
    job: "Drafts grounds that cite only facts on record and real judgments, checks and repairs every claim.",
    motif: "Living manuscript",
    glyph: "manuscript",
    working: "The brief inks itself line by line inside an illuminated border.",
    full: "Citations settle as gold marginalia; NEEDS_REVIEW lines get a maroon underline.",
    where: "Brief stage",
    stages: ["BRIEF", "HEARING_PREP", "FILE"],
    runsOn: "Qwen3-14B, on the Ada cluster",
    workingText: "Vakeel is drafting and checking grounds",
    idleText: "Vakeel: draft ready",
  },
  ABHIYOJAK: {
    id: "ABHIYOJAK",
    name: "Abhiyojak",
    nameHi: "अभियोजक",
    subtitle: "Prosecution sparring",
    role: "The prosecutor",
    job: "Raises the objections the prosecution would, each grounded in a bank paragraph, statute or fact; judges replies.",
    motif: "Scales",
    glyph: "scales",
    working: "Objection cards drop on one pan.",
    full: "Replies drop on the other; the scales stay tipped while anything is unanswered.",
    where: "Spar stage",
    stages: ["SPAR"],
    runsOn: "Qwen3-14B with its own prompt and context, on the Ada cluster",
    workingText: "Abhiyojak is raising objections",
    idleText: "Abhiyojak: sparring complete",
  },
  PAIROKAR: {
    id: "PAIROKAR",
    name: "Pairokar",
    nameHi: "पैरोकार",
    subtitle: "Batch desk",
    role: "The person who follows up a case",
    job: "Triages many files at once by legal urgency and decides the order of work.",
    motif: "Cause-list bars",
    glyph: "bars",
    working: "Bars slide as cases are scored.",
    full: "The board re-ranks by urgency.",
    where: "/desk",
    stages: [],
    runsOn: "Rules + Qwen3-14B, on the laptop and Ada",
    workingText: "Pairokar is scoring cases",
    idleText: "Pairokar: board ranked by urgency",
  },
};

/** Agents in the plan's order. */
export const AGENT_LIST: readonly AgentMeta[] = AGENT_NAMES.map((a) => AGENTS[a]);

/** "Munshi · Intake agent". */
export function agentTitle(agent: AgentName): string {
  const a = AGENTS[agent];
  return `${a.name} · ${a.subtitle}`;
}

/** Agent meta for an event actor ("MUNSHI", "counsel", ...); null for counsel or unknown actors. */
export function agentForActor(actor: string | null | undefined): AgentMeta | null {
  if (!actor) return null;
  const key = actor.toUpperCase() as AgentName;
  return AGENTS[key] ?? null;
}

export function isAgentName(value: unknown): value is AgentName {
  return typeof value === "string" && (AGENT_NAMES as readonly string[]).includes(value);
}
