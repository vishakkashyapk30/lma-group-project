// Typed API client for the FastAPI backend (plan §13.1). Mirrors src/vakeel_sahayak/api/routers/.
import type {
  BailBrief, CaseDossier, CaseSummary, ChatMessage, GateId, GateStatus, IngestionReport, RightsReport, SparringRecord, TriageCard,
} from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const todo = (name: string): never => { throw new Error(`api.${name}: not implemented (skeleton)`); };

export const api = {
  listCases: (): Promise<CaseSummary[]> => todo("listCases"),
  createCase: (title?: string): Promise<CaseSummary> => todo("createCase"),
  getIngestion: (caseId: string): Promise<IngestionReport> => todo("getIngestion"),
  getDossier: (caseId: string): Promise<CaseDossier> => todo("getDossier"),
  editField: (caseId: string, field: string, value: unknown): Promise<CaseDossier> => todo("editField"),
  getDates: (caseId: string): Promise<unknown[]> => todo("getDates"),
  getRights: (caseId: string): Promise<RightsReport> => todo("getRights"),
  startDraft: (caseId: string): Promise<void> => todo("startDraft"),
  getBrief: (caseId: string): Promise<BailBrief> => todo("getBrief"),
  getSpar: (caseId: string): Promise<SparringRecord> => todo("getSpar"),
  getPrep: (caseId: string): Promise<Record<string, unknown>> => todo("getPrep"),
  uploadFiles: (caseId: string, files: File[]): Promise<{ accepted: string[]; questions: string[] }> => todo("uploadFiles"),
  uploadAudio: (caseId: string, file: Blob): Promise<{ accepted: string[]; questions: string[] }> => todo("uploadAudio"),
  chat: (caseId: string, text: string): Promise<ChatMessage> => todo("chat"),
  getGate: (caseId: string, gate: GateId): Promise<GateStatus> => todo("getGate"),
  approveGate: (caseId: string, gate: GateId, acknowledged: string[]): Promise<GateStatus> => todo("approveGate"),
  exportCase: (caseId: string, format: "DOCX" | "PDF"): Promise<string[]> => todo("exportCase"),
  deskUpload: (file: File): Promise<string[]> => todo("deskUpload"),
  deskBoard: (): Promise<{ cards: TriageCard[] }> => todo("deskBoard"),
  librarySearch: (q: string): Promise<unknown[]> => todo("librarySearch"),
  libraryCitations: (docId: string): Promise<unknown> => todo("libraryCitations"),
  libraryBridge: (code: string, section: string): Promise<unknown> => todo("libraryBridge"),
};
