/**
 * UI CONTRACT for the Playwright specs (plan §13.3-§13.7). UI implementers MUST expose these hooks; the specs depend on
 * nothing else about the DOM. Everything here is an ASSUMPTION of the test author (the plan names the concepts, not the ids).
 *
 * RECONCILED (2026-10-26, docs/handoff/workspace-redesign.md and docs/handoff/landing-colour-motion.md): this contract now describes
 * the redesigned landing and the one-step-at-a-time workspace. The scene, gate-diamond, three-pane and right-tab hooks of the earlier
 * design are gone; every rule they carried is still tested through the hooks below.
 *
 * Conventions
 *  - `data-testid` values are listed in TID. Parametrised ids are functions (stage("II") -> "stage-II").
 *  - "interactive element" means the testid sits on the focusable control itself (button / link / tab), not a wrapper.
 *  - Status text is real text. Icons are glyphs from lib/status.ts, wrapped in an aria-hidden span; the label is visible text.
 *
 * LANDING (/)
 *  - h1 states the product; open-case-button ("Try the sample case", href /case/case-0007, or /cases in a strict live build) and a
 *    "See how it works" link to #walk in the hero. The header offers "Open workspace", or continue-case ("Continue: <title>")
 *    once a case has been opened in this browser (localStorage vs:last-case).
 *  - Hero demo file-demo: fir-card (drag) or add-fir-button, dossier-drop, then demo-page and demo-row (data-status).
 *  - The walk (nav "Walk through the sample case"): read-demo (read-row, read-quote), check-demo (hearing-handle role=slider,
 *    hearing-date, custody-days, word-default-bail, word-undertrial), hold-demo (gate1-demo-button, gate1-list, gate1-confirm,
 *    gate2-demo-button, gate2-list), draft-demo (draft-cite, draft-paragraph, draft-ground data-check), spar-demo (spar-card
 *    data-verdict, spar-write, spar-reply-input, spar-reply-save); then privacy-demo, desk-band, close-open-sample.
 *  - Bands, as h2, in order: see e2e/landing.spec.ts BANDS.
 *  - site-footer: contains "यतो धर्मस्ततो जयः", "AI-generated drafts for counsel. Not legal advice.", "NALSA", "15100" and the Preamble's line.
 *
 * WORKSPACE (/case/[id])
 *  - stage-rail (navigation landmark) with six steps stage-I, II, III, IV, VI, VII (Add documents, Review facts, Check rights,
 *    Draft grounds, Prepare for the hearing, Export; interactive; aria-current="step" on the step shown; aria-disabled="true"
 *    while locked). SPAR (Likely objections) is shown inside Draft grounds and has no step.
 *  - pane-main holds the one step on screen. documents-button opens the case file (pane-case-file), chat-button the chat drawer
 *    (pane-chat), details-button the Details drawer with the trace (trace-drawer, trace-step with data-tool).
 *  - needs-you / needs-you-item: what needs counsel on the current step (unreadable pages, questions, UNSUPPORTED fields, grounds
 *    that need review, unanswered objections), each with one jump button.
 *  - Add documents: upload-input, mic-button (aria-pressed; dictation-status), document-item (data-doc-id) with doc-type-stamp;
 *    route-badge under each document's "Reading details" expander.
 *  - Review facts: right-tab-dossier / right-tab-dates (role="tab"); dossier-field (data-field, data-status, data-changed) with
 *    status-badge, dossier-field-edit / -input / -save, dossier-field-source (opens source-panel with pdf-viewer and pdf-highlight
 *    data-box="x0,y0,x1,y1"), "Mark <Label> as unknown" for an UNSUPPORTED field, changed-marker; date-row per List of dates event;
 *    confirm-facts-button (Gate 1; disabled while something needs counsel) opens gate-modal.
 *  - Check rights: rights-chip (data-check, data-status, data-changed) with status-badge; less urgent checks under "Other checks".
 *  - Draft grounds: draft-brief-button; brief-ground (data-ground, data-state CURRENT|STALE, data-changed) with change-reason,
 *    needs-review-marker, per-counsel-label, and its claim check as aux-badge under "Details"; spar-objection (data-objection)
 *    with a status-badge for its verdict.
 *  - Prepare for the hearing: prep-card. Export: approve-export-button (Gate 2; disabled while items are open) opens gate-modal;
 *    export-button and export-link appear only after approval.
 *  - gate-modal (role="dialog"): what the approval locks, gate-checklist-item (data-kind, data-item) for what counsel dealt with,
 *    gate-approve-button. error-banner (role="alert") shows API errors.
 *  - change-banner (role="status") with change-item (data-kind field|right, data-name) while a change set awaits re-confirmation.
 *  - readback-card (in the chat drawer) with readback-item and readback-confirm, after a dictation.
 *  - agent-signature (data-agent) with agent-status: the quiet indicator shown while an agent works.
 *
 * DESK (/desk): desk-upload-input, desk-board, triage-card (data-case-id; DOM order = urgency_rank ascending), triage-reason,
 *  triage-flag, triage-missing, triage-next-step, a link to /case/{case_id}; the page states that each case needs its own
 *  approval and that there is no bulk export. No "Export all" control anywhere.
 *
 * LIBRARY (/library): library-search (textbox), bridge-view.
 */
export const TID = {
  siteFooter: "site-footer",
  sidebar: "sidebar",
  brandHome: "brand-home", // the logo link in the sidebar and the mobile drawer; goes to the landing page
  continueCase: "continue-case", // landing: "Continue: <last case title>" (only once a case was opened)
  openCaseButton: "open-case-button",

  stageRail: "stage-rail",
  stage: (numeral: string) => `stage-${numeral}`,
  paneCaseFile: "pane-case-file",
  paneChat: "pane-chat",
  rightTab: (name: "dossier" | "dates") => `right-tab-${name}`, // the Facts / List of dates tabs of Review facts

  statusBadge: "status-badge",
  dossierField: "dossier-field",
  dossierFieldEdit: "dossier-field-edit",
  dossierFieldInput: "dossier-field-input",
  dossierFieldSave: "dossier-field-save",
  dossierFieldSource: "dossier-field-source",
  rightsChip: "rights-chip",
  pdfViewer: "pdf-viewer",
  pdfHighlight: "pdf-highlight",
  documentItem: "document-item",
  docTypeStamp: "doc-type-stamp",
  routeBadge: "route-badge",
  uploadInput: "upload-input",

  chatInput: "chat-input",
  chatSend: "chat-send",
  chatMessage: "chat-message",
  toolChip: "tool-chip",
  draftBriefButton: "draft-brief-button",
  traceDrawer: "trace-drawer",
  traceStep: "trace-step",
  briefGround: "brief-ground",
  needsReviewMarker: "needs-review-marker",
  sparObjection: "spar-objection",
  prepCard: "prep-card",

  gateModal: "gate-modal",
  gateChecklistItem: "gate-checklist-item",
  gateApproveButton: "gate-approve-button",
  exportButton: "export-button",
  exportLink: "export-link",
  errorBanner: "error-banner",

  changeBanner: "change-banner",
  changeItem: "change-item",
  changedMarker: "changed-marker",
  changeReason: "change-reason",
  micButton: "mic-button",
  dictationStatus: "dictation-status",
  readbackCard: "readback-card",
  readbackItem: "readback-item",
  readbackConfirm: "readback-confirm",
  perCounselLabel: "per-counsel-label",

  agentSignature: "agent-signature",
  agentStatus: "agent-status",

  deskUploadInput: "desk-upload-input",
  paneMain: "pane-main",
  documentsButton: "documents-button",
  chatButton: "chat-button",
  detailsButton: "details-button",
  sourcePanel: "source-panel",
  dateRow: "date-row",
  confirmFactsButton: "confirm-facts-button",
  approveExportButton: "approve-export-button",
  needsYou: "needs-you",
  needsYouItem: "needs-you-item",
  auxBadge: "aux-badge", // a ground's claim check (under Details) and the "Needs check" mark
  deskBoard: "desk-board",
  triageCard: "triage-card",
  triageReason: "triage-reason",
  triageFlag: "triage-flag",
  triageMissing: "triage-missing",
  triageNextStep: "triage-next-step",

  librarySearch: "library-search",
  bridgeView: "bridge-view",
} as const;

/** RECONCILED: the stepper's buttons, in order (stage-V, Likely objections, is shown inside Draft grounds and has no button). */
export const STAGE_NUMERALS = ["I", "II", "III", "IV", "VI", "VII"] as const;

/** The six steps of the stepper with their plain-language labels (lib/stages.ts). */
export const STEPS = [
  { key: "I", label: "Add documents" },
  { key: "II", label: "Review facts" },
  { key: "III", label: "Check rights" },
  { key: "IV", label: "Draft grounds" },
  { key: "VI", label: "Prepare for the hearing" },
  { key: "VII", label: "Export" },
] as const;

/** Accessible names / visible strings the specs rely on (plan text). */
export const TEXT = {
  // RECONCILED: the colour-band landing (docs/handoff/landing-colour-motion.md) replaced the scene headline, stats band and
  // "Watch the journey"; frontend-endeavours made the hero's way in "Try the sample case" (openCase below is the header's).
  headline: "Prepare a bail application from the case file",
  openCase: /open workspace/i,
  seeHow: /see how it works/i,
  motto: "यतो धर्मस्ततो जयः",
  disclaimer: "AI-generated drafts for counsel. Not legal advice.",
  nalsa: "NALSA",
  nalsaNumber: "15100",
  needsOwnApproval: /needs its own approval/i,
  exportAll: /export all/i,
  changed: /changed/i,
  perCounsel: "per counsel, not on record",
  statedByCounsel: "Entered by you", // RECONCILED: plain-language label of USER_STATED (lib/status.ts)
} as const;

export const AGENTS = ["MUNSHI", "PESHKAR", "SUTRADHAR", "VAKEEL", "ABHIYOJAK", "PAIROKAR"] as const;
