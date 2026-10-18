# Frontend foundation: exports for later agents

Verified: `npx tsc --noEmit -p .`, `npm run lint`, `npm run build` pass. `tsconfig.json` excludes `e2e/`, `tests/` and the
vitest/playwright configs (they had type errors against `DossierFields`: `fields: {}` and string indexing). Check them with
`npx tsc --noEmit -p tsconfig.tests.json`.

Demo mode: with `NEXT_PUBLIC_API_BASE` unset or the API unreachable, everything runs from `lib/mock` (case-0007 plus 5 other cases).

## Design system
- `styles/tokens.css` (palette, status colours, type scale, spacing, radii, motion), `styles/fonts.css` (self-hosted @fontsource:
  Fraunces, Tiro Devanagari Hindi, Noto Sans Devanagari, DM Sans, IBM Plex Mono; next/font/google could not download at build),
  `app/globals.css` (base, focus ring, jaali utility, reduced-motion base). Tailwind maps: `bg-parchment|cream|maroon|oxblood|gold-leaf|ink`,
  `text-neem|indigo|sindoor|haldi|clay`, `font-display|devanagari|devanagari-body|sans|mono`, `duration-fast`, `ease-standard`, `rounded-pill`.
- `lib/utils`: `cn`, `isBrowser`, `sleep`, `clone`, `uid`, `clamp`, `groupBy`.

## lib/types.ts
Enums with `*_NAMES`/`*_STATUSES` arrays: `FieldStatus, SlotStatus, ClaimState, ClaimCheck, SparringVerdict, RightsStatus, RightsCheckName,
TransferFlag, GoodLawStatus, Treatment, OpenIssueType, AgentName, Factor, Shelf, StoreName, DocumentType, ParseRoute, PageStatus, EventKind,
GateId, Stage, ExportFormat, DocLang, Actor`. Models: `SourceRef, Box, TrackedField<T>, IngestionReport, DocumentEntry, DossierFields,
DossierFieldName, DOSSIER_FIELD_NAMES, CaseDossier, TimelineEvent, RightsReport, RightsCheckResult, RetrievalPlan, PlanStep, SlotResult,
EvidencePack, BailBrief, Ground, Authority, OpenIssue, SparringRecord, Objection, Reply, TriageCard, AgentEvent/Event, ChangeSet, FieldChange,
ChatMessage, ToolChip, CaseSummary, GateStatus, BudgetState, DeskBoard, ParagraphRecord, HearingPrepCard, CitationGraphData, BridgeData,
LibrarySearchHit, GroundRevision, SelectedSource, MockPage`, plus request/response types (`UploadResponse, DraftStartResponse, ...`).

## lib/api.ts (one function per route; demo fallback automatic)
`listCases, createCase, getCase, getIngestion, getDossier, editField, getDates, getRights, startDraft, getBrief, getBriefRevisions, getSpar,
getPrep, getBudget, getPage, pageImageUrl, uploadFiles, uploadAudio, postChat, getChatHistory, getGate, approveGate, exportCase, deskUpload,
getDeskBoard, openDeskCase, searchLibrary, getCitationGraph, getBridge`; mode: `getApiMode, isDemoMode, getDemoReason, enterDemoMode, onApiModeChange,
API_BASE, apiUrl, eventsUrl`; also default `api` object. Errors: `lib/errors` (`ApiError, errorMessage`).

## lib/mock (also `demoServer`)
`MOCK_CASE_ID, MOCK_INGESTION, MOCK_DOSSIER, MOCK_TIMELINE, MOCK_RIGHTS, MOCK_RETRIEVAL_PLAN(S), MOCK_BRIEF, MOCK_BRIEF_REVISIONS, MOCK_SPAR,
MOCK_PREP, MOCK_CHAT, MOCK_BUDGET, MOCK_CITATIONS, MOCK_DOC_TITLES, MOCK_CASES, CASE_SEEDS, MOCK_TRIAGE_CARDS, MOCK_DESK_BOARD, MOCK_EVENT_SCRIPT,
intakeScript/draftScript/..., MOCK_LIBRARY_RESULTS, MOCK_CITATION_GRAPH, MOCK_BRIDGE, MOCK_BRIDGES, MOCK_PAGES, getMockPage`.

## Hooks and helpers
- `lib/useEventStream(caseId, opts)` SSE with reconnect (mock replay in demo); `lib/useReducedMotion` (`useReducedMotion, prefersReducedMotion`).
- `lib/motion/register`: `registerMotion()` (idempotent, client-only), exports `gsap, ScrollTrigger, SplitText, DrawSVGPlugin, MorphSVGPlugin, useGSAP,
  Lenis`, `MOTION`, `whenMotionAllowed`, `killAllScrollTriggers`, `startLenis`, `useLenis(enabled)`, `getLenis`, `scrollToTarget`.
- `lib/status`: `getStatusMeta(status, kind?)`, `STATUS_META`, `*_META` per family, `TONE_CLASSES`, `parseRightsChip, sortRightsChips`, `BLOCKING_STATUSES`.
- `lib/stages`: `STAGES, STAGE_BY_ID, WORKSPACE_TABS, TAB_LABELS, GATE_LABELS, isStageUnlocked, lockReason, stageState, tabForStage`.
- `lib/agents`: `AGENTS, AGENT_LIST, agentTitle, agentForActor`. `lib/labels, lib/fields, lib/format, lib/diff, lib/stores` (label maps, field formatting, date and source helpers, word diff, store/tool metadata).

## lib/workspace (import from "@/lib/workspace")
`<WorkspaceProvider caseId>` (already wrapped in `app/case/[id]/page.tsx`); hooks `useWorkspace()` (whole value), `useOptionalWorkspace()`, `useCaseData()`,
`useStageNav()`, `useSelectedSource()` (`selectSource(sourceRef)`, `selectedSource`, `sourceNonce`), `useGates()`, `useGateChecklist(gate)`, `useChat()`,
`useAgentActivity()`, `useWorkspaceEvents()`, `useEdits()` (`editField` marks USER_EDITED). Pure: `computeChecklist, checklistKey, attentionCount, deriveActivity`.

## Components
- `components/ui`: `Button` (variants primary, secondary, ghost, link, danger, pill, pill-dark, play, gold; sizes sm, md, lg, icon, round), `PlayButton`, `Card*`, `Badge`, `Tabs*`,
  `Dialog*`, `Tooltip`/`TooltipProvider`, `ScrollArea`, `Separator`, `Input`, `Textarea`, `Skeleton`, `SkeletonText`.
- `components/common`: `StatusBadge({status, kind?, label?, detail?, size?, solid?})`, `StatusIcon`, `SourceChip({source})`, `AgentGlyph({agent, size?, title?})`, `Logo`, `BandsMark`, `TopNav`.
- Pages in `app/*/page.tsx` are thin wrappers (`/`, `/cases`, `/case/[id]`, `/desk`, `/library`, `/about`); component bodies elsewhere are still stubs.
