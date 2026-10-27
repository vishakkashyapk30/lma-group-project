# Frontend endeavours: build (phase 2)

Branch `frontend-endeavours` (from main 4c9f6ad; not merged). Direction B "Walk the file" from `frontend-endeavours-ideation.md`, with the owner's decisions (later also: no route transitions, the close band names the four members, sample-case links go to /cases in a strict live build): physics on the landing demos, drag-to-close panels and sheets, and the gate hold (no list reorder, no attach-source-to-claim, no swipe-to-commit); the `motion` library; the new close band; the refined logo; the logo to `/` and "Continue: <last case>". Only `frontend/` and this folder changed; no Python, no API calls, no URLs.

## What was built, per commit

| Step | Commit | What |
|---|---|---|
| 0 (plan step 4) | b61fc25 | DESIGN.md motion amendment: drag springs settle within 450 ms, time-based motion 150 to 300 ms, rubber band `(1 - 1/(x*0.55/d + 1)) * d`, spring table, keyboard and button parity, no scroll hijacking, reduced motion = instant or 100 ms fade, press 0.97. Tokens `--ease-spring`, `--dur-gesture-max`. `motion` in package.json. The ideation note. |
| 1 | ce0b9ed | Logo goes to `/` from the sidebar and the mobile drawer (`brand-home`, name "Vakeel-Sahayak home"). `E2E_PORT` in the Playwright config. |
| 2 | 8843d86 | `lib/lastCase.ts` (localStorage `vs:last-case`), written by `usePublishCaseMeta`; landing header "Continue: <title>" + "All cases", fixed min width (no shift). |
| 3 | 0f4834c | Audit fixes: "Step n of 6" and step names on case cards and the stage filter (SPAR reads "Draft grounds"); sticky step footer edge and safe-area padding, `scroll-pb-24` on the step pane; `.hl-mark`/`.sweep` no longer wrap into slivers; header "Safeguards", Help, Try the sample case; stale FOUNDATION_NOTES.md and tokens.css notes. |
| 5 | ab0371f | `lib/motion`: `fromPerceptual`, `SPRINGS`, `ALLOWANCE`, `rubberband`, `rubberClamp`, `project`, `simulate`, `runSpring`, `SpringValue` (interruptible, writes to the element, jumps under reduced motion), `VelocityTracker`, `useDrag`. Vitest of the maths. Corrected two rubber-band values in the ideation note (23 and 17 px). |
| 6 | 4720f16 | `.press` (scale 0.97 on press, spring curve back) on every Button; sliding tab indicator in `ui/tabs.tsx` (transform only, 275 ms). |
| 7 | e4fd2a1 | Step changes slide 12 px by direction (CSS) and `NEXT_DIST_DIR`. The route crossfade added here (`experimental.viewTransition`) was removed later by the owner's decision, see the last row. |
| 8 | afe468d | `loading.tsx` skeletons for /cases, /desk, /library and a workspace skeleton that matches the stepper row and the 48 rem column; shown after 150 ms. Focus to the page h1 after sidebar, drawer, palette or logo navigation (`components/shell/routeFocus.ts`). |
| 9 | a659232 | Drag to close: source and chat panel (right), its phone sheet (now rises from the bottom, down to close, grabber), Details drawer. `lib/motion/useDragToClose.ts`. |
| 10 | ad4be16 | Gate hold: `components/common/HoldButton.tsx`, `components/workspace/GateFooter.tsx`. Held gates are `aria-disabled`, show a lock and "(n open)", move at most 12 px, and list the open items (Mark as unknown, Go to it). First use of `motion` (presence, LazyMotion + domAnimation on demand). |
| 11 | 478da40 | Case title carries over: card click primes the top bar (`primeCaseMeta`) and records the title's box (`components/motion/Morph.tsx`); the breadcrumb plays a 250 ms FLIP. |
| 12 | ff569b5 | Hero demo "put the FIR on the file" (`demos/FileDemo.tsx`, 2D drag `lib/motion/useDrag2D.ts`), replacing HeroLoop. `components/landing/sample.ts` takes every value from `lib/mock`. |
| 13 | f1fd7d7 | Read demo (indigo band): facts of the Hindi FIR open on their sentence, value marked; pointer pull with resistance opens a row. |
| 14 | 56248c0 | Check demo (saffron band): `components/rights/RightsTimeline.tsx` + `lib/rightsTimeline.ts`; hearing-date slider (drag with rubber band and momentum, magnet to thresholds, keyboard, buttons). |
| 15 | d1c9891 | Hold demo: the sample's Gate 1 item and Gate 2 items from the workspace's own checklist code. |
| 16 | 3e1a10a | Draft demo (numbered authorities open the judgment paragraph, "Needs your check" ground kept) and Spar demo (unanswered first, "Write a reply"). |
| 17 | d33ef1a | Privacy (VS_EXTERNAL modes), Batch desk band, flat maroon close (Open the sample case, who built it, how tested), Preamble and motto in the footer, walk links (#walk), header How it works / Privacy / Batch desk / Help. DESIGN.md landing sections. |
| 18 | 052f64c | Rights timeline at the top of the workspace's Check rights step; falls back to dossier dates and the Radar's own day counts when the report has no `dates`. |
| 19 | 2f2b0f5 | `e2e/timing-budget.spec.ts`; reduced-motion checks for demos, panels, gates; presence instant under reduced motion; leaving panels close within 6 px of off screen. |
| 20 | 76d6784 | Logo: V meets the beam, short hangers and pans from 24 px, V and beam only below; all brand SVGs, icon.svg, favicon.ico (16/32/48), apple-icon, icon-192/512; DESIGN.md "Logo and icons". |
| - | 99e667b | Bundle: `m` from `motion/react-m`; `lib/sampleCase` no longer imports `lib/api` (which carries the demo server). |
| - | (this commit) | Owner decisions: `experimental.viewTransition` and the route crossfade removed (Next back on the stable React channel); route changes are instant; the step slide (CSS) and the case-title FLIP stay, as neither needs the flag. The close band names the four members. |

## How to run and test

```bash
cd frontend
npx vitest run                         # 16 files, 299 tests
npx tsc --noEmit -p . && npx next lint
NEXT_DIST_DIR=.next-build npx next build   # beside a running dev server; delete .next-build after
npx playwright install chromium        # once; only chromium
E2E_PORT=3100 npx playwright test      # starts `next dev -p 3100` if nothing listens there
rm -rf test-results
```
Last full run (2026-10-27, after the owner's decisions): vitest 299 passed; tsc and lint clean; `next build` passes; Playwright 167 passed, 1 skipped (`live_flow.spec.ts`, needs `E2E_LIVE_API=1`), chromium and reduced-motion projects.

New specs: `navigation`, `transitions`, `gestures` (panels, sheet by finger through CDP, gate hold, workspace timeline), `landing-demo` (each demo by pointer and by keyboard alone, both motion modes, 390 px), `timing-budget`. Changed specs (each change is in its commit message and marked RECONCILED): `transitions.spec.ts` and `timing-budget.spec.ts` (route changes are instant: they assert no view transition starts and the sidebar and top bar do not move), `landing.spec.ts` (hero loop tests became "rests until touched", band order, #walk, hero action is the sample case), `testids.ts` (landing contract), `a11y.spec.ts` and `reduced-motion.spec.ts` (tests added only).

Bundle (`next build`, route `/`): 3.63 kB route / 122 kB first load before; 38.6 kB / 183 kB now (shared first-load JS 104 kB before, 103 kB now). The growth is the five demos and their sample data; the animation features of `motion` load on demand (not in first load).

## Screenshots (`docs/handoff/frontend-endeavours-shots/`, dev server, reduced motion so frames are at rest; the round "N" is Next's dev indicator)
1. `1-landing-hero-1440.png` hero after filing the FIR. 2. `2-landing-hero-390.png`. 3. `3-landing-check-1440.png` rights timeline. 4. `4-landing-hold-1440.png` gate held with its list. 5. `5-workspace-rights-timeline-1440.png` Check rights step. 6. `6-workspace-source-sheet-390.png` the source sheet with its grabber. Before/after shots of every step were taken in the session scratchpad only.

## Deliberately not built
- List reorder, attach-a-source-to-a-claim, swipe-to-commit: owner decision (and the API has no field for an order or a counsel-attached source).
- Pull-to-open on touch in the Read demo: a vertical pull would take over page scrolling; a finger taps instead.
- J/K navigation in the landing's batch-desk band: the band is a static ranking with a link to the real desk, which has the keyboard path.
- Privacy "swap names" toggle from the ideation: the sample case is already pseudonymised and inventing real-looking names would be made-up data, so the demo shows the four VS_EXTERNAL settings and the FIR line as it would be sent.
- Route transitions: instant by the owner's decision. A crossfade needs Next's `experimental.viewTransition`, which runs the app on the experimental React channel and added about 12 kB to every route.
- React's shared `<ViewTransition name>` for the title: it did not pair between the top bar and the page in Next 15's experimental React, so the morph is a measured FLIP (`components/motion/Morph.tsx`).

## Known issues
- `loading.tsx` skeletons rarely show: the static pages are prefetched whole in production; they exist for slow first navigations. The workspace skeleton (dynamic import) is the one users see; the a11y spec measures it against the real layout.
- Specs that open the landing with a `#hash` wait 500 ms for hydration and the band reveal before pointer work; without it Tab or drag can land before handlers attach.
- In a strict live build (`NEXT_PUBLIC_API_MODE=live`, the product default) case-0007 may not exist on the server, so "Try the sample case" and the close go to `/cases` (and "Resolve them in the sample case" to the walk); the demos themselves always work.
- main moved to 42c2f0f (Rights API `verification` field, optional `VS_API_TOKEN`): not merged here; the UI does not send a token, as asked.

## Merge notes
See `frontend-endeavours-merge-notes.md`.
