/**
 * Stateful in-browser mock of the FastAPI backend (src/vakeel_sahayak/api/routers/*) via page.route. The Next app calls
 * NEXT_PUBLIC_API_BASE_URL (default http://localhost:8000); every `**\/api/**` request is answered here, including CORS
 * preflights and the SSE stream. Requests that match no router endpoint are recorded in `unmatched` (specs assert it is
 * empty, so the UI cannot call endpoints the backend does not have) and answered 404.
 */
import type { Page, Route } from "@playwright/test";
import type { BailBrief, CaseDossier, GateStatus, IngestionReport, AgentEvent, ChatMessage, TrackedFieldAny } from "./types";
import { fx } from "./fixtures";

export interface MockOptions {
  caseId?: string;
  /** Gate 1 already approved (stages III-VII unlocked). Default true. */
  gate1Approved?: boolean;
  /** "done": brief/spar/prep exist; "none": 404 until POST /draft. Default "done". */
  draft?: "done" | "none";
  /** Gate 2 starts blocked (unresolved NEEDS_REVIEW + UNANSWERED) unless already approved. Default blocked. */
  gate2Approved?: boolean;
  /** Fresh case with no documents yet: dossier empty and ingestion empty until the first upload. */
  fresh?: boolean;
  /**
   * "default": flows 1-3, 6, 7. "change": flow 4, an approved case (charge sheet not filed) to which counsel uploads a new order; the upload
   * produces a change set (Gate 1 must be re-approved) and approving it redrafts only G2. "dictation": flow 5, a fresh case where counsel
   * dictates in Hindi through the mic; Munshi reads back the date and section, the confirmed facts are USER_STATED.
   */
  scenario?: "default" | "change" | "dictation";
  /** Scenario "change": the uploaded document is a duplicate of one already filed (T3 no-op control): no change set, nothing redrafted. */
  duplicateUpload?: boolean;
}

const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "*",
  "access-control-allow-methods": "GET,POST,PATCH,PUT,DELETE,OPTIONS",
  "access-control-expose-headers": "*",
};
// 1x1 transparent PNG used for page images.
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
  "base64",
);

export class MockBackend {
  caseId: string;
  dossier: CaseDossier;
  ingestion: IngestionReport;
  ingested: boolean;
  gate1Approved: boolean;
  gate2: GateStatus;
  draftStarted: boolean;
  deskUploaded = false;
  eventsServed = 0;
  readonly drafts = fx.draftEvents();
  /** Events served over SSE: the draft events, plus change events appended by the "change" scenario. */
  eventLog: AgentEvent[] = [...this.drafts];
  brief: BailBrief = fx.brief();
  pendingChange = false;
  dictationHeard = false;
  dictationConfirmed = false;
  readonly options: Required<MockOptions>;

  // Recorded interactions the specs assert on.
  requests: string[] = [];
  unmatched: string[] = [];
  approveCalls: { gate: string; body: { acknowledged_fields: string[] } }[] = [];
  patchCalls: { field: string; value: unknown }[] = [];
  chatCalls: string[] = [];
  uploadCalls: { path: string; contentType: string; bytes: number }[] = [];
  exportResults: { status: number }[] = [];

  constructor(options: MockOptions = {}) {
    const o: Required<MockOptions> = {
      caseId: options.caseId ?? "case-0007",
      gate1Approved: options.gate1Approved ?? true,
      draft: options.draft ?? "done",
      gate2Approved: options.gate2Approved ?? false,
      fresh: options.fresh ?? false,
      scenario: options.scenario ?? "default",
      duplicateUpload: options.duplicateUpload ?? false,
    };
    this.options = o;
    this.caseId = o.caseId;
    this.ingested = !o.fresh;
    this.gate1Approved = o.gate1Approved;
    this.gate2 = o.gate2Approved ? fx.gate2Open() : fx.gate2Blocked();
    this.draftStarted = o.draft === "done";
    this.dossier = o.fresh ? { ...fx.dossier(), case_id: o.caseId, fields: {}, open_questions: [] } : fx.dossier();
    this.ingestion = o.fresh ? { ...fx.ingestionEmpty(), case_id: o.caseId } : { ...fx.ingestionBundle(), case_id: o.caseId };
    if (o.scenario === "change") {
      this.dossier = fx.dossierBeforeChange();
      this.brief = fx.briefBeforeChange();
    }
    if (o.scenario === "dictation") {
      this.brief = fx.briefDictated();
    }
  }

  static async install(page: Page, options: MockOptions = {}): Promise<MockBackend> {
    const mock = new MockBackend(options);
    await page.route("**/api/**", (route) => mock.handle(route));
    await page.route("**/files/**", (route) => route.fulfill({ status: 200, headers: CORS, contentType: "application/octet-stream", body: "mock" }));
    return mock;
  }

  // ---- state helpers used by specs
  /** Counsel resolves every NEEDS_REVIEW / UNANSWERED item (as if done in the Brief and Spar tabs). */
  resolveGate2Items(): void {
    this.gate2 = { ...this.gate2, unresolved_needs_review: [], unresolved_unanswered: [], unresolved_unsupported: [] };
  }
  /** Gate 1 checklist derived from the live dossier. */
  gate1Status(): GateStatus {
    if (this.gate1Approved) return fx.gate1Open();
    const unsupported = Object.entries(this.dossier.fields)
      .filter(([, f]) => (f as TrackedFieldAny).status === "UNSUPPORTED")
      .map(([k]) => k);
    return { gate: "GATE_1_DOSSIER", open: false, unresolved_unsupported: unsupported, unresolved_needs_review: [], unresolved_unanswered: [] };
  }

  private json(route: Route, body: unknown, status = 200) {
    return route.fulfill({ status, headers: CORS, contentType: "application/json", body: JSON.stringify(body) });
  }

  private summary() {
    const s = fx.caseSummary();
    return {
      ...s,
      case_id: this.caseId,
      stage: this.ingested ? (this.gate1Approved ? "BRIEF" : "DOSSIER") : "INTAKE",
    };
  }

  async handle(route: Route): Promise<void> {
    const req = route.request();
    const url = new URL(req.url());
    const method = req.method().toUpperCase();
    const p = url.pathname;
    if (method === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    this.requests.push(`${method} ${p}`);

    let m: RegExpMatchArray | null;
    // ---- cases
    if (p === "/api/cases") {
      if (method === "GET") return this.json(route, [this.summary()]);
      if (method === "POST") return this.json(route, { ...this.summary(), case_id: this.caseId, title: "New case", stage: "INTAKE" });
    }
    if ((m = p.match(/^\/api\/cases\/([^/]+)$/)) && method === "GET") {
      return this.json(route, { ...this.summary(), case_id: decodeURIComponent(m[1]) });
    }
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/(ingestion|dossier|dates|rights|brief|spar|prep|budget)$/)) && method === "GET") {
      const [, id, what] = m;
      const gated = ["brief", "spar", "prep"].includes(what) && !this.draftStarted;
      if (gated) return this.json(route, { detail: "not drafted yet" }, 404);
      switch (what) {
        case "ingestion": return this.json(route, { ...this.ingestion, case_id: decodeURIComponent(id) });
        case "dossier": return this.json(route, { ...this.dossier, case_id: decodeURIComponent(id) });
        case "dates": return this.json(route, this.ingested ? fx.timeline() : []);
        case "rights": return this.json(route, { ...fx.rights(), case_id: decodeURIComponent(id) });
        case "brief": return this.json(route, { ...this.brief, case_id: decodeURIComponent(id) });
        case "spar": return this.json(route, { ...fx.spar(), case_id: decodeURIComponent(id) });
        case "prep": return this.json(route, fx.prep());
        case "budget": return this.json(route, { tokens_spent: 42000, tokens_cap: 150000, store_calls: { "caselaw.reasoning": 3 } });
      }
    }
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/dossier\/([^/]+)$/)) && method === "PATCH") {
      const field = decodeURIComponent(m[2]);
      const body = req.postDataJSON() as { value: unknown };
      this.patchCalls.push({ field, value: body.value });
      const prev = (this.dossier.fields[field] ?? { value: null, source: null, status: "UNSUPPORTED" }) as TrackedFieldAny;
      this.dossier = {
        ...this.dossier,
        fields: { ...this.dossier.fields, [field]: { value: body.value, source: prev.source, status: "USER_EDITED" } },
      };
      return this.json(route, this.dossier);
    }
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/draft$/)) && method === "POST") {
      this.draftStarted = true;
      return this.json(route, { status: "started" });
    }
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/files\/([^/]+)\/pages\/(\d+)$/)) && method === "GET") {
      return route.fulfill({ status: 200, headers: CORS, contentType: "image/png", body: PNG_1X1 });
    }

    // ---- upload
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/(upload|audio)$/)) && method === "POST") {
      this.uploadCalls.push({ path: p, contentType: req.headers()["content-type"] ?? "", bytes: req.postDataBuffer()?.length ?? 0 });
      // flow 5: the dictated audio is transcribed on the laptop; Munshi answers with a read-back of the dates and sections it heard
      if (this.options.scenario === "dictation" && m[2] === "audio") {
        this.dictationHeard = true;
        return this.json(route, { ...fx.dictationReadback(), case_id: this.caseId });
      }
      // flow 4: counsel uploads the new order; Peshkar re-extracts the touched field and diffs it, so Gate 1 must be re-approved
      if (this.options.scenario === "change" && m[2] === "upload") {
        if (!this.options.duplicateUpload) {
          this.dossier = { ...fx.dossierAfterChange(), case_id: this.caseId };
          this.gate1Approved = false;
          this.pendingChange = true;
          this.eventLog.push(fx.changeEvents()[0]);
        }
        return this.json(route, { case_id: this.caseId, accepted: ["order_sheet_2.pdf"], questions: [] });
      }
      this.ingested = true;
      this.ingestion = { ...fx.ingestionBundle(), case_id: this.caseId };
      const fields = fx.dossier().fields;
      this.dossier = {
        ...fx.dossier(), case_id: this.caseId,
        // a second red field so Gate 1 needs an acknowledgement as well as an edit
        fields: { ...fields, trial_stage: { value: null, source: null, status: "UNSUPPORTED" } as TrackedFieldAny },
      };
      return this.json(route, { case_id: this.caseId, accepted: ["bundle_14pp.pdf"], questions: this.ingestion.questions });
    }

    // ---- chat
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/chat$/))) {
      if (method === "GET") return this.json(route, [] as ChatMessage[]);
      if (method === "POST") {
        const body = req.postDataJSON() as { text: string };
        this.chatCalls.push(body.text);
        // flow 5: counsel's confirmation of the read-back files the dictated facts as USER_STATED
        if (this.options.scenario === "dictation" && this.dictationHeard && /confirm/i.test(body.text)) {
          this.dictationConfirmed = true;
          this.ingested = true;
          this.dossier = { ...fx.dossierDictated(), case_id: this.caseId };
          return this.json(route, {
            ...fx.munshiQuestion(), case_id: this.caseId, message_id: `m-${this.chatCalls.length + 100}`,
            text: "Filed as stated by counsel: the arrest on 20.08.2024 and section 318(4) BNS.",
          });
        }
        return this.json(route, { ...fx.chatMessage(), message_id: `m-${this.chatCalls.length + 100}` });
      }
    }

    // ---- gates
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/gates\/(GATE_1_DOSSIER|GATE_2_EXPORT)(\/approve)?$/))) {
      const gate = m[2];
      const status = gate === "GATE_1_DOSSIER" ? this.gate1Status() : this.gate2;
      if (!m[3] && method === "GET") return this.json(route, status);
      if (m[3] && method === "POST") {
        const body = req.postDataJSON() as { acknowledged_fields: string[] };
        this.approveCalls.push({ gate, body });
        const stillOpen =
          status.unresolved_unsupported.filter((f) => !body.acknowledged_fields.includes(f)).length +
          status.unresolved_needs_review.length + status.unresolved_unanswered.length;
        if (stillOpen > 0) return this.json(route, { detail: "Checklist not cleared" }, 409);
        if (gate === "GATE_1_DOSSIER") {
          this.gate1Approved = true;
          if (this.pendingChange) {
            // flow 4: the approved change set stales G2 only; Sutradhar re-plans one factor, Vakeel redrafts G2, G1 and G3 stay word for word
            this.pendingChange = false;
            this.eventLog.push(...fx.changeEvents().slice(1));
            this.brief = fx.briefAfterChange();
          }
        } else this.gate2 = fx.gate2Open();
        return this.json(route, gate === "GATE_1_DOSSIER" ? fx.gate1Open() : this.gate2);
      }
    }

    // ---- export (403 unless Gate 2 approved, plan §16)
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/export$/)) && method === "POST") {
      if (!this.gate2.open) {
        this.exportResults.push({ status: 403 });
        return this.json(route, { detail: "Gate 2 not approved for this case" }, 403);
      }
      this.exportResults.push({ status: 200 });
      return this.json(route, [
        `${new URL(req.url()).origin}/files/${this.caseId}/application.docx`,
        `${new URL(req.url()).origin}/files/${this.caseId}/hearing_card.docx`,
      ]);
    }

    // ---- SSE (plan §13.1): finite bodies; EventSource reconnects (retry 300 ms) with Last-Event-ID.
    if ((m = p.match(/^\/api\/cases\/([^/]+)\/events$/)) && method === "GET") {
      const last = req.headers()["last-event-id"] ?? url.searchParams.get("last_event_id") ?? url.searchParams.get("lastEventId");
      const startAt = last ? this.eventLog.findIndex((e) => e.event_id === last) + 1 : 0;
      const frames = this.draftStarted ? this.eventLog.slice(startAt).map(sse) : [];
      this.eventsServed += frames.length;
      return route.fulfill({
        status: 200,
        headers: { ...CORS, "cache-control": "no-cache" },
        contentType: "text/event-stream",
        body: `retry: 300\n\n${frames.join("")}`,
      });
    }

    // ---- desk
    if (p === "/api/desk/upload" && method === "POST") {
      this.uploadCalls.push({ path: p, contentType: req.headers()["content-type"] ?? "", bytes: req.postDataBuffer()?.length ?? 0 });
      this.deskUploaded = true;
      return this.json(route, fx.triageCards().map((c) => c.case_id));
    }
    if (p === "/api/desk/board" && method === "GET") {
      return this.json(route, { cards: this.deskUploaded ? fx.triageCards() : [] });
    }
    if ((m = p.match(/^\/api\/desk\/([^/]+)\/open$/)) && method === "POST") {
      return this.json(route, { ...this.summary(), case_id: decodeURIComponent(m[1]) });
    }

    // ---- library (not exercised by the specs beyond smoke)
    if (p === "/api/library/search") return this.json(route, []);
    if (p.startsWith("/api/library/")) return this.json(route, {});

    this.unmatched.push(`${method} ${p}`);
    return this.json(route, { detail: `mock: no endpoint for ${method} ${p}` }, 404);
  }
}

function sse(e: AgentEvent): string {
  return `id: ${e.event_id}\ndata: ${JSON.stringify(e)}\n\n`;
}
