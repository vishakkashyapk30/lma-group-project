// Re-exports of lib/types.ts for the e2e helpers, plus a loose tracked-field type for fixture edits.
export type {
  BailBrief, CaseDossier, GateStatus, IngestionReport, AgentEvent, ChatMessage, TrackedField, FieldStatus,
} from "../lib/types";
import type { TrackedField } from "../lib/types";
export type TrackedFieldAny = TrackedField<unknown>;
