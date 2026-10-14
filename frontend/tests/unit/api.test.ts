/**
 * Typed API client (plan §13.1, §13.5; mirrors src/vakeel_sahayak/api/routers/). fetch is mocked; no network.
 * ASSUMPTIONs: JSON bodies are sent with a JSON content-type; multipart uploads let the browser set the boundary (no manual
 * Content-Type); non-2xx responses reject with an exported `ApiError` carrying `status`; the export 403 (Gate 2 not
 * approved, plan §16) is surfaced as ApiError with status 403, never as a resolved value.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Api = typeof import("@/lib/api");

async function loadApi(env?: string): Promise<Api> {
  vi.resetModules();
  if (env === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", env);
  return import("@/lib/api");
}

const BASE = "http://localhost:8000";
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  fetchMock = vi.fn(async () => json({}));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => { vi.unstubAllEnvs(); });

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string | URL | Request, RequestInit | undefined];
  const href = typeof url === "string" ? url : url instanceof URL ? url.href : url.url;
  return {
    url: href,
    method: (init?.method ?? "GET").toUpperCase(),
    headers: new Headers(init?.headers),
    body: init?.body,
    json: () => JSON.parse(String(init?.body)),
  };
}

describe("API_BASE", () => {
  it("defaults to http://localhost:8000", async () => {
    const m = await loadApi();
    expect(m.API_BASE).toBe(BASE);
  });
  it("is overridden by NEXT_PUBLIC_API_BASE_URL", async () => {
    const m = await loadApi("http://tunnel.example:9000");
    expect(m.API_BASE).toBe("http://tunnel.example:9000");
  });
});

describe("api client endpoints (fail until implemented)", () => {
  it("listCases -> GET /api/cases", async () => {
    fetchMock.mockResolvedValueOnce(json([{ case_id: "case-0007", title: "t", stage: "INTAKE", rights_chips: [], needs_attention: 0 }]));
    const { api } = await loadApi();
    const out = await api.listCases();
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/cases`, method: "GET" });
    expect(out[0].case_id).toBe("case-0007");
  });

  it("createCase -> POST /api/cases with {title}", async () => {
    fetchMock.mockResolvedValueOnce(json({ case_id: "case-9", title: "New", stage: "INTAKE", rights_chips: [], needs_attention: 0 }));
    const { api } = await loadApi();
    await api.createCase("New");
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases`, method: "POST" });
    expect(c.json()).toEqual({ title: "New" });
    expect(c.headers.get("content-type")).toMatch(/json/);
  });

  it.each([
    ["getIngestion", "/ingestion"], ["getDossier", "/dossier"], ["getDates", "/dates"], ["getRights", "/rights"],
    ["getBrief", "/brief"], ["getSpar", "/spar"], ["getPrep", "/prep"],
  ] as const)("%s -> GET /api/cases/{id}%s", async (fn, suffix) => {
    const { api } = await loadApi();
    await (api[fn] as (id: string) => Promise<unknown>)("case-0007");
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/cases/case-0007${suffix}`, method: "GET" });
  });

  it("editField -> PATCH /api/cases/{id}/dossier/{field} with {value}", async () => {
    const { api } = await loadApi();
    await api.editField("case-0007", "antecedents", "none known");
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases/case-0007/dossier/antecedents`, method: "PATCH" });
    expect(c.json()).toEqual({ value: "none known" });
  });

  it("startDraft -> POST /api/cases/{id}/draft", async () => {
    const { api } = await loadApi();
    await api.startDraft("case-0007");
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/cases/case-0007/draft`, method: "POST" });
  });

  it("getGate -> GET /api/cases/{id}/gates/GATE_1_DOSSIER", async () => {
    fetchMock.mockResolvedValueOnce(json({ gate: "GATE_1_DOSSIER", open: false, unresolved_unsupported: ["antecedents"], unresolved_needs_review: [], unresolved_unanswered: [] }));
    const { api } = await loadApi();
    const g = await api.getGate("case-0007", "GATE_1_DOSSIER");
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/cases/case-0007/gates/GATE_1_DOSSIER`, method: "GET" });
    expect(g.unresolved_unsupported).toEqual(["antecedents"]);
  });

  it("approveGate -> POST .../gates/{gate}/approve with acknowledged_fields", async () => {
    const { api } = await loadApi();
    await api.approveGate("case-0007", "GATE_1_DOSSIER", ["antecedents"]);
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases/case-0007/gates/GATE_1_DOSSIER/approve`, method: "POST" });
    expect(c.json()).toEqual({ acknowledged_fields: ["antecedents"] });
  });

  it("exportCase -> POST /api/cases/{id}/export with {format} and returns the file links", async () => {
    fetchMock.mockResolvedValueOnce(json(["/files/case-0007/application.docx"]));
    const { api } = await loadApi();
    const links = await api.exportCase("case-0007", "DOCX");
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases/case-0007/export`, method: "POST" });
    expect(c.json()).toEqual({ format: "DOCX" });
    expect(links).toEqual(["/files/case-0007/application.docx"]);
  });

  it("exportCase surfaces 403 (Gate 2 not approved) as a typed ApiError with status 403", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "Gate 2 not approved" }, 403));
    const mod = await loadApi();
    const ApiError = (mod as unknown as { ApiError?: new (...a: never[]) => Error & { status: number } }).ApiError;
    expect(ApiError, "lib/api.ts must export class ApiError").toBeTypeOf("function");
    const err = await mod.api.exportCase("case-0007", "DOCX").then(
      () => { throw new Error("expected rejection"); },
      (e: unknown) => e,
    );
    expect(err).toBeInstanceOf(ApiError!);
    expect((err as { status: number }).status).toBe(403);
    expect((err as Error).message).toMatch(/Gate 2/);
  });

  it("any other non-2xx response also rejects with ApiError carrying its status", async () => {
    fetchMock.mockResolvedValueOnce(json({ detail: "boom" }, 500));
    const mod = await loadApi();
    const err = await mod.api.listCases().then(() => null, (e: unknown) => e);
    expect(err).toBeInstanceOf(Error);
    expect((err as { status?: number }).status).toBe(500);
  });

  it("chat -> POST /api/cases/{id}/chat with {text}", async () => {
    fetchMock.mockResolvedValueOnce(json({ message_id: "m1", case_id: "case-0007", role: "agent", text: "167 days", chips: [], refused: false }));
    const { api } = await loadApi();
    const msg = await api.chat("case-0007", "Days in custody?");
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases/case-0007/chat`, method: "POST" });
    expect(c.json()).toEqual({ text: "Days in custody?" });
    expect(msg.text).toBe("167 days");
  });

  it("uploadFiles -> multipart POST /api/cases/{id}/upload with one 'files' part per file and no manual Content-Type", async () => {
    fetchMock.mockResolvedValueOnce(json({ case_id: "case-0007", accepted: ["a.pdf", "b.pdf"], questions: [] }));
    const { api } = await loadApi();
    const files = [new File(["%PDF-1"], "a.pdf", { type: "application/pdf" }), new File(["%PDF-1"], "b.pdf", { type: "application/pdf" })];
    const out = await api.uploadFiles("case-0007", files);
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases/case-0007/upload`, method: "POST" });
    expect(c.body).toBeInstanceOf(FormData);
    expect((c.body as FormData).getAll("files").map((f) => (f as File).name)).toEqual(["a.pdf", "b.pdf"]);
    expect(c.headers.get("content-type")).toBeNull(); // the browser must add the multipart boundary
    expect(out.accepted).toEqual(["a.pdf", "b.pdf"]);
  });

  it("uploadAudio -> multipart POST /api/cases/{id}/audio with a 'file' part", async () => {
    const { api } = await loadApi();
    await api.uploadAudio("case-0007", new Blob(["x"], { type: "audio/webm" }));
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/cases/case-0007/audio`, method: "POST" });
    expect((c.body as FormData).get("file")).toBeTruthy();
  });

  it("deskUpload -> multipart POST /api/desk/upload with a 'file' part", async () => {
    fetchMock.mockResolvedValueOnce(json(["case-0101", "case-0102"]));
    const { api } = await loadApi();
    const ids = await api.deskUpload(new File(["PK"], "bundle.zip", { type: "application/zip" }));
    const c = lastCall();
    expect(c).toMatchObject({ url: `${BASE}/api/desk/upload`, method: "POST" });
    expect(((c.body as FormData).get("file") as File).name).toBe("bundle.zip");
    expect(ids).toEqual(["case-0101", "case-0102"]);
  });

  it("deskBoard -> GET /api/desk/board", async () => {
    fetchMock.mockResolvedValueOnce(json({ cards: [] }));
    const { api } = await loadApi();
    expect(await api.deskBoard()).toEqual({ cards: [] });
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/desk/board`, method: "GET" });
  });

  it("librarySearch -> GET /api/library/search?q=<encoded>", async () => {
    const { api } = await loadApi();
    await api.librarySearch("default bail & parity");
    const c = lastCall();
    expect(c.method).toBe("GET");
    expect(new URL(c.url).pathname).toBe("/api/library/search");
    expect(new URL(c.url).searchParams.get("q")).toBe("default bail & parity");
  });

  it("libraryCitations -> GET /api/library/citations/{doc_id}", async () => {
    const { api } = await loadApi();
    await api.libraryCitations("SC-2022-0001");
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/library/citations/SC-2022-0001`, method: "GET" });
  });

  it("libraryBridge -> GET /api/library/bridge/{code}/{section}", async () => {
    const { api } = await loadApi();
    await api.libraryBridge("IPC", "420");
    expect(lastCall()).toMatchObject({ url: `${BASE}/api/library/bridge/IPC/420`, method: "GET" });
  });

  it("path segments are URL-encoded (case ids are untrusted input)", async () => {
    const { api } = await loadApi();
    await api.getDossier("a/b c");
    expect(lastCall().url).toBe(`${BASE}/api/cases/a%2Fb%20c/dossier`);
  });
});
