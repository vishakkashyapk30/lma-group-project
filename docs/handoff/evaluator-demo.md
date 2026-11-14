# Evaluator demo (guided tours)

An evaluator of the project opens the site, finds several recorded demo cases on the Cases page, picks one and presses Next after every step. Every field is already filled; the walk goes from the papers to the exported application. The demos differ by offence and law, custody and rights, record quality, and parity and history.

The backend half (recorded cases, the `/api/demo/tours` routes, pre-loading at startup) is described in its own section of this note. This section covers the tour interface.

## Tour interface (frontend)

### What the evaluator sees
- **Cases page** (`/cases`): a "Guided demos" section above the matters, one row per tour with its title, its story and the four facets as plain text ("Offence and law: ...", "Custody and rights: ...", "Record quality: ...", "Parity and history: ..."), and a "Start the guided demo" button. It opens `/case/<case_id>?tour=<slug>`. With no tours (the server answers 404 or `[]`, or the request fails) the section is not rendered at all.
- **Tour bar** in the workspace: docked under the step (above nothing else, never over it), white panel with a hairline top border. It shows "Guided demo · Step k of n · Done by <agent>, <subtitle>", the step's title (serif) and caption (read out through `aria-live="polite"`), and the step's `filled` list as read-only filled fields (label above, value in a field-like box). The Gate 1 and Gate 2 steps add the gate's status ("Gate 1 is approved.", "Gate 2 is open. Next approves the draft for export.") and the gate's note from `GATE_LABELS`. The first step shows the recording line (date, backend, model). Buttons: Exit the demo, Back, Next (the primary). On the Gate 2 step Next reads "Approve and continue"; on the last step it reads "Finish" and leaves tour mode, staying on Export.
- **Next** moves the workspace with its own navigation (`ws.setStage`), so the stepper, the step slide and the breadcrumb behave as for counsel. GATE_1 opens Review facts, GATE_2 and FILE open Export, SPAR opens Draft grounds and scrolls to "Likely objections". The case is past Gate 1, so no step is locked; if a tour ever points at a locked step the bar says "This step is not open in this case yet..." instead of failing.
- **Gate 2**: Next on the GATE_2 step calls `POST /api/cases/{id}/gates/GATE_2_EXPORT/approve` once, sending every item on the Gate 2 checklist as reviewed (field names for UNSUPPORTED, `NEEDS_REVIEW:<id>` and `UNANSWERED:<id>` keys otherwise, the same shape the confirm dialog sends), then refreshes the summary and gates. If the gate is already approved (a second evaluator) it just moves on; if the approve call fails it asks `GET /gates/GATE_2_EXPORT` again and moves on when the gate turned out approved, else it stays on the step and shows the server's message, and Next tries again. A double press never sends two approvals.
- **Keyboard**: the bar is a labelled region, focus starts on Next, Right arrow or Enter = Next, Left arrow = Back, Escape = leave the demo. The keys act only when focus is on the page or inside the bar, never while typing in a field or with a dialog open; Enter on a focused button presses that button.
- **Language**: every interface string of the bar and the list is wrapped in `t()` and translated in `hi.json` (28 new strings, Gemma on the Gemini free tier with `scripts/translate_ui_hi.py`, as for the rest of the interface). Titles, stories, captions and filled values from the tour file are shown as written.
- Toasts sit above the bar (`--tour-bar-h`, read by `components/ui/toast.tsx`), so "Exported 4 files" does not cover the buttons.

### Files
- `frontend/lib/tour.ts`: types, the parser for `GET /api/demo/tours[/slug]` (steps sorted into INTAKE ... FILE order, unknown stages dropped, the approve action allowed on GATE_2 only), the stage map, and the step machine (`createTourMachine`: bounds, the single-flight Gate 2 action).
- `frontend/lib/api.ts`: `listTours()` (404 -> `[]`) and `getTour(slug)` (404 -> `null`).
- `frontend/components/tour/GuidedDemos.tsx` (in `components/cases/CauseList.tsx`) and `frontend/components/tour/TourBar.tsx` (in `components/workspace/WorkspaceShell.tsx` when `?tour=` is present).
- Demo build (`NEXT_PUBLIC_API_MODE=demo`, or `auto` with the API unreachable): `frontend/lib/mock/tours.ts` serves one tour, `00-sample-cheating-parity`, over the sample case-0007 through `lib/mock/server.ts` (`listTours`, `getTour`). The sample case is at Gate 1 approved and Gate 2 open, so the tour's Gate 2 step really approves it in the browser's demo state (sessionStorage; a new tab starts fresh).
- `frontend/e2e/mockBackend.ts` answers `/api/demo/tours` with `[]` (and 404 for a slug), so the other specs see a server with demos off.

### Tests
- Vitest: `tests/unit/tour.test.ts` (parser, order, bounds, Gate 2 once, already approved, approval refused then retried, approved by someone else meanwhile), `tests/unit/tourApi.test.ts` (routes, 404 handling, the demo build's tour), `tests/unit/tourUi.test.tsx` (the list, the bar walking all nine steps, Gate 2 once with the right keys, unknown slug, wrong case, keyboard).
- Playwright: `e2e/tour.spec.ts`, offline (aborts `localhost:8000`, so the client falls back to the demo backend): starts from the cases page, presses only Next through all nine steps, checks the stepper at each, ends at Export with the draft approved and downloads the Word file link; axe on the cases page, the Review facts step and Export; keyboard and Escape; unknown slug.
- Run: `cd frontend && E2E_PORT=3030 npx playwright test e2e/tour.spec.ts --project=chromium` (any free port; Playwright reuses whatever answers on it).

### Also changed here
- `ink-muted` darkened from `#675D54` to `#615850` (6.4:1 on canvas, 6.9:1 on white, 5.85:1 on parchment-deep, 5.2:1 on the hairline colour), DESIGN.md table updated. The reported 4.32:1 failure (6 muted nodes and the Gaps tab count on Review facts) did not reproduce here (dev and production demo builds, 1x to 8x CPU throttling, Hindi on); the measurement looks like a frame of the 200 ms step fade, so `e2e/helpers.ts` `seriousAxeViolations` now waits (up to 2 s) for running finite animations to end before axe runs, and the darker token gives the muted text more headroom.

### Not done / next steps
- In tour mode the workspace stays fully interactive: an evaluator can still edit a fact or answer a question in the shared recorded case, which on a live server changes it for the next evaluator (an edit reopens Gate 1). A read-only tour mode for the workspace's own controls would need a flag through the step components.
- The Next button and the step's own footer button are both maroon while the tour runs (two primaries on screen); acceptable for a demo, but the step footer could turn secondary in tour mode.
- Not checked against the backend agent's real tour files yet; the parser is defensive (unknown stages and agents ignored, missing tabs defaulted) but the field names must match the API described above.
