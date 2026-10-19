/**
 * UI CONTRACT for the Playwright specs (plan §13.3-§13.7). UI implementers MUST expose these hooks; the specs depend on
 * nothing else about the DOM. Everything here is an ASSUMPTION of the test author (the plan names the concepts, not the ids).
 *
 * Conventions
 *  - `data-testid` values are listed in TID. Parametrised ids are functions (scene(3) -> "scene-3").
 *  - "interactive element" means the testid sits on the focusable control itself (button / link / tab), not a wrapper.
 *  - Status text is real text. Icons are glyphs from lib/status.ts, wrapped in an aria-hidden span; the label is visible text.
 *
 * LANDING (/)
 *  - scene-0 .. scene-6: seven sections in DOM order. Scene 0 contains the headline "Bail is the rule, jail the exception.",
 *    open-case-button ("Open a case"), watch-journey-button ("Watch the journey"), and stats-band (contains "75.8%").
 *    Scene 6 contains the text "Article 21" and "39A".
 *  - scene-indicator: container of exactly six scene-dot elements (scenes 1..6, "a row of six"). The dot of the scene in view
 *    has aria-current="true"; the other five have none. (Hero, scene 0, lights no dot.)
 *  - Reduced motion (prefers-reduced-motion: reduce): a static-storyboard element wraps the scenes; every scene-N carries
 *    data-motion="static" and one scene-caption (non-empty text); no running animation inside the scenes. When motion is
 *    allowed, static-storyboard is absent and scenes carry data-motion="animated".
 *  - site-footer: contains "यतो धर्मस्ततो जयः", "AI-generated drafts for counsel. Not legal advice.", "NALSA" and "15100".
 *  - watch-journey-button scrolls to scene 1.
 *
 * WORKSPACE (/case/[id])
 *  - pane-case-file | pane-chat | pane-right: the three panes.
 *  - stage-rail (navigation landmark) containing stage-I .. stage-VII (interactive; text = numeral + label; aria-current="step"
 *    on the current stage; aria-disabled="true" while locked) and gate-diamond-1 / gate-diamond-2 (interactive; open the
 *    gate modal; data-approved="true"|"false").
 *  - Gate state: RECONCILED with record/gates.py: GateStatus.open === true means the gate has NOT been approved yet (it is
 *    still open for counsel), false means approved; stages III-VII unlock once GATE_1_DOSSIER is approved (open === false);
 *    the unresolved_* lists say what still blocks approval.
 *  - right-tab-dossier|dates|rights|brief|spar|prep: role="tab" with aria-selected. Rail <-> tab sync: stage II <-> dossier,
 *    III <-> rights, IV <-> brief, V <-> spar, VI <-> prep (selecting either selects the other; stage becomes aria-current).
 *  - dossier-field (one per dossier field; data-field = field key) containing status-badge; dossier-field-edit (button inside the
 *    row), dossier-field-input (text input), dossier-field-save (button); dossier-field-source (button inside the row: click
 *    scrolls the PDF to the source box and draws pdf-highlight).
 *  - status-badge: icon + label text; data-status = raw status (e.g. "UNSUPPORTED").
 *  - rights-chip (one per RightsCheckResult; data-check = check name, data-status = status; text has the check title such as
 *    "Default bail" and a status-badge).
 *  - pdf-viewer (in pane-case-file; page images come from GET /api/cases/{id}/files/{doc}/pages/{n}); pdf-highlight
 *    (data-box="x0,y0,x1,y1").
 *  - document-item (data-doc-id), doc-type-stamp (text = document type), route-badge (text TEXT | LAYOUT | OCR | VISION from
 *    page_routes text_layer | layout | ocr | vision; data-route = lower-case route).
 *  - upload-input: the <input type="file" multiple> behind the drop zone (may be visually hidden).
 *  - chat-input (textbox), chat-send (button), chat-message (data-role = counsel|agent, data-agent = AgentName for agent
 *    messages), tool-chip (inside a chat-message; text = tool name). Identical agent questions are shown once.
 *  - draft-brief-button ("Draft bail brief"), show-plan-button ("Show the plan"), trace-drawer (dialog; Escape closes it),
 *    trace-step (one per Sutradhar TOOL_CALL event, data-tool = tool name).
 *  - brief-ground (data-ground = id) with status-badge for its ClaimCheck; needs-review-marker inside a ground whose check is
 *    NEEDS_REVIEW (maroon underline: computed text-decoration-line includes "underline").
 *  - spar-objection (data-objection = id) containing a status-badge for its verdict.
 *  - prep-card (hearing-prep card; renders the string values of GET .../prep).
 *  - gate-modal (role="dialog"), gate-checklist-item (one per unresolved item; data-kind = unsupported | needs_review |
 *    unanswered; data-item = item name; kind "unsupported" contains a checkbox that acknowledges it), gate-approve-button
 *    (disabled until every unsupported item is acknowledged and no needs_review / unanswered item is left). The modal
 *    re-fetches the GateStatus every time it opens. Escape closes it. Approve sends acknowledged_fields.
 *  - export-button ("Export"; in stage VII; disabled while GATE_2_EXPORT is not open, or enabled but the server's 403 is shown),
 *    export-link (anchor per returned file link), error-banner (role="alert"; shows API errors including the export 403).
 *
 * FLOW 4: THE CASE MOVES ON (plan §7.4, §10, §13.6; hooks added with e2e/flow4_case_moves_on.spec.ts)
 *  - The change set reaches the UI as events on the SSE stream (STORE_WRITE with outputs.change_set = a ChangeSet, then CHANGE_SET_APPROVED,
 *    CLAIM_STALED, an AGENT_MESSAGE and a STORE_WRITE with outputs.redrafted = ground ids). SKELETON-GAP: no REST route serves a ChangeSet.
 *  - change-banner (role="status"; in pane-right, visible while a change set is awaiting re-approval): lists one change-item per changed
 *    dossier field (data-kind="field", data-name = field key) and per changed Rights Radar check (data-kind="right", data-name = check name).
 *  - dossier-field gets data-changed="true" and contains changed-marker (visible text "Changed" plus a glyph, never colour alone) when its field is in
 *    the change set; every other dossier-field has no data-changed or data-changed="false". rights-chip likewise for changed checks.
 *  - Re-approval: while a change set is pending gate-diamond-1 has data-approved="false"; opening it shows gate-modal with no checklist items
 *    (nothing is unsupported) and an enabled gate-approve-button.
 *  - brief-ground carries data-state="CURRENT" | "STALE" (STALE between CLAIM_STALED and the redraft) and, once redrafted, data-changed="true" and a
 *    change-reason (the 'why': names the changed dependency, e.g. the charge sheet). Unchanged grounds have no data-changed="true" and
 *    their text is untouched, word for word.
 *
 * FLOW 5: A DICTATED CASE (plan §4.5, §13.6; hooks added with e2e/flow5_dictated_case.spec.ts)
 *  - mic-button: toggle button in pane-case-file next to the drop zone (aria-label "Dictate"); aria-pressed="true" while recording. Recording uses
 *    MediaRecorder; on stop the blob is POSTed (multipart field "file") to /api/cases/{id}/audio. dictation-status: live text ("Recording",
 *    "Transcribing", "Heard") next to the button.
 *  - readback-card (in pane-chat, from the UploadResponse.questions of the audio upload, Munshi speaking): one readback-item per line Munshi
 *    heard (dates, sections, numbers; plain text), and readback-confirm ("Confirm"), which sends a chat message containing the word "confirm"
 *    and the read-back values. SKELETON-GAP: no REST route confirms a read-back; the chat route stands in.
 *  - Confirmed dictated facts come back as dossier fields with data-status="USER_STATED" (badge "Stated by counsel").
 *  - per-counsel-label: inside a brief-ground whose facts are USER_STATED; text "per counsel, not on record".
 *
 * AGENT SIGNATURES
 *  - agent-signature (data-agent = AgentName; data-motion = "static" under reduced motion) with agent-status (non-empty text).
 *    Munshi: pane-case-file. Peshkar: Dates and Rights tabs. Sutradhar: chat header. Vakeel: Brief tab. Abhiyojak: Spar tab.
 *    Pairokar: /desk.
 *
 * DESK (/desk)
 *  - desk-upload-input (<input type="file">), desk-board, triage-card (data-case-id; DOM order = urgency_rank ascending),
 *    triage-reason, triage-flag, triage-missing, triage-next-step; every card shows "needs its own approval" and contains a
 *    link (role=link) to /case/{case_id}. There is no "Export all" control anywhere on the page.
 *
 * LIBRARY (/library): library-search (textbox), bridge-view.
 */
export const TID = {
  scene: (n: number) => `scene-${n}`,
  sceneIndicator: "scene-indicator",
  sceneDot: "scene-dot",
  sceneCaption: "scene-caption",
  staticStoryboard: "static-storyboard",
  statsBand: "stats-band",
  siteFooter: "site-footer",
  watchJourneyButton: "watch-journey-button",
  openCaseButton: "open-case-button",

  stageRail: "stage-rail",
  stage: (numeral: string) => `stage-${numeral}`,
  gateDiamond: (n: 1 | 2) => `gate-diamond-${n}`,
  paneCaseFile: "pane-case-file",
  paneChat: "pane-chat",
  paneRight: "pane-right",
  rightTab: (name: "dossier" | "dates" | "rights" | "brief" | "spar" | "prep") => `right-tab-${name}`,

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
  showPlanButton: "show-plan-button",
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
  deskBoard: "desk-board",
  triageCard: "triage-card",
  triageReason: "triage-reason",
  triageFlag: "triage-flag",
  triageMissing: "triage-missing",
  triageNextStep: "triage-next-step",

  librarySearch: "library-search",
  bridgeView: "bridge-view",
} as const;

export const STAGE_NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII"] as const;
export const RIGHT_TABS = ["dossier", "dates", "rights", "brief", "spar", "prep"] as const;
export type RightTab = (typeof RIGHT_TABS)[number];

/** Stage numeral -> right-pane tab it is synced with (stages without a tab are omitted). */
export const STAGE_TAB: Record<string, RightTab> = { II: "dossier", III: "rights", IV: "brief", V: "spar", VI: "prep" };

/** Accessible names / visible strings the specs rely on (plan text). */
export const TEXT = {
  headlineA: "Bail is the rule",
  headlineB: "jail the exception",
  openCase: /open a case/i,
  watchJourney: /watch the journey/i,
  stat: "75.8%",
  motto: "यतो धर्मस्ततो जयः",
  disclaimer: "AI-generated drafts for counsel. Not legal advice.",
  nalsa: "NALSA",
  nalsaNumber: "15100",
  article21: /Article\s*21|Art\.\s*21/,
  article39A: /39A/,
  needsOwnApproval: /needs its own approval/i,
  exportAll: /export all/i,
  changed: /changed/i,
  perCounsel: "per counsel, not on record",
  statedByCounsel: "Stated by counsel",
} as const;

export const AGENTS = ["MUNSHI", "PESHKAR", "SUTRADHAR", "VAKEEL", "ABHIYOJAK", "PAIROKAR"] as const;
