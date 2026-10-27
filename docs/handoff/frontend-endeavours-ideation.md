# Frontend endeavours: ideation (phase 1, no code)

Branch `frontend-endeavours` (worktree from main 4c9f6ad). Nothing in `frontend/` was changed. Screenshots of the current build (dev server, headless Chrome, reduced motion so the hero loop shows its final frame) were taken at 1440 and 390 px of `/`, `/cases` and `/case/case-0007`; they lived in the session scratchpad and are not in the repo.

How to read this: section 1 is the audit, 2 the motion rules (with the DESIGN.md amendment the owner asked for), 3 the user journey with a UI idea per stage, 4 the three landing directions, 5 signature interactions to build and not to build, 6 transitions and navigation, 7 usability testing without participants, 8 recommendation and questions, 9 the build plan, 10 sources.

---

## 1. Audit of the current landing page and navigation

What works
- The headline says what the product does and the primary action is clear (`components/landing/LandingPage.tsx`). The disclaimer and NALSA 15100 sit in the footer (`Footer.tsx`).
- The band colours mean something (maroon acts, indigo informs, neem confirms, saffron asks for a check), and the motion budget is disciplined: CSS keyframes, transform and opacity only, the final frame is the resting state, reduced motion shows it with no animation (`styles/landing.css`).
- In the app, one list (`components/shell/nav.ts`) drives the sidebar, the drawer and the palette; Ctrl/Cmd+K works; the mode chip is honest; the stepper tells you where the file stands.

What feels off (concrete)
1. **The hero is a film, not the product.** `HeroLoop.tsx` is `role="img"` with `aria-hidden` content: an 8.55 s run that plays while the visitor reads the headline, then rests. Nothing can be touched. The product's best feature (open a fact, see the words behind it) cannot be tried.
2. **The saffron offset block** behind the loop (`HeroLoop.tsx`, `bg-saffron translate-x-3`) reads as a neo-brutalist drop shadow. It is the one element with no meaning.
3. **Bug at 390 px:** the highlight `.hl-mark::before` sits on an inline span that wraps, so the absolute box breaks into slivers ("on |14.08.2024", "a|d" in the screenshot). Fix with `box-decoration-break: clone` on a background, or keep the phrase on one line.
4. **The bands tell instead of show.** "How it works" is four text columns with saffron rules, "What you stay in control of" is four ticks. Only the indigo sources band demonstrates something. The differentiators (two gates only counsel opens, honest "Not found" and CHECK, Hindi beside English, files stay on the machine, the batch desk with deadlines, the precedent library, dictation) are claimed or absent.
5. **The close band** (Preamble quote on a maroon lattice, `jaali-dark`) is the most cinematic moment on the page and the lattice is decoration. It is the part most likely to read as "made by a generator".
6. **Header:** the anchor "Control" is vague, there is no Help or About link, no "Try the sample case", the header is not sticky, and "Open workspace" appears three times with the same words.
7. **No continuity between landing and app.** The logo in `Sidebar.tsx` and in `MobileDrawer.tsx` goes to `/cases`; the only way back to `/` is "Product overview" in the help menu or the palette. The landing button always goes to `/cases`; the last open case is not remembered.
8. **Hard cuts and a shifting skeleton.** No `loading.tsx` or `template.tsx` exists. The workspace skeleton in `WorkspaceShellLazy.tsx` (`h-10 w-72`, `h-12`, `h-[60dvh]`) does not match the stepper row and centred column it turns into, which breaks DESIGN.md principle 5 (no layout shift).
9. **Inconsistent counts and names.** `CaseCard.tsx:61` says "Stage 4 of 7" while the stepper has six steps; case-0007 is "Likely objections" in the cause list and "Draft grounds" in the workspace.
10. **Sticky step footer** on `/case/case-0007` cuts the "Rights to check" row with no edge or separation.
11. **Logo:** at 28 px the beam over the V reads as a macron (V with an overline). Without pans the scales are not legible, and a mark tile plus a serif wordmark is generic.
12. **Stale notes that mislead agents:** `frontend/FOUNDATION_NOTES.md` lists Fraunces, DM Sans, IBM Plex and `lib/motion` with gsap and Lenis, none of which exist; the comment at the top of `styles/tokens.css` still names next/font and Fraunces.
13. At 1440 px the headline wraps to four lines (`max-w-[16ch]`) and pushes the buttons to about 530 px. This is acceptable but heavy; three lines would let the demo sit higher.

Installed motion and gesture libraries: none (no framer-motion, motion, @use-gesture, react-spring, dnd-kit, vaul, gsap or lenis in `package.json` or `node_modules`). React 19.3.0 exports `ViewTransition` and `Activity`; Next is 15.5.27, where route view transitions need `experimental.viewTransition: true`.

---

## 2. Motion rules: physics where the hand drives it, short time-based motion elsewhere

### 2a. Proposed amendment to DESIGN.md "Motion" (replace the bullet "App: ... No page transitions." and add a subsection)

> **Direct manipulation.** When the user drags something (a panel, a sheet, a card, the demo on the landing page, the List of Dates timeline), it follows the pointer 1:1 and is released into a spring that carries the gesture's velocity. Such springs are critically damped or nearly so (bounce at most 0.15 in the app, 0.2 on the landing demo) and settle within 450 ms. Past a limit, a dragged element resists with the rubber-band curve `offset = (1 - 1 / (x * 0.55 / d + 1)) * d` (x = distance past the limit, d = the element's allowance, see the table) and springs back on release. Gestures can be interrupted: grabbing a moving element stops it where it is.
> **Time-based motion** (anything that plays without the user's hand: reveals, crossfades, route transitions, menus, the tab indicator) stays at 150 to 300 ms with `--ease` or `--ease-spring` (a `linear()` approximation of a critically damped spring).
> **Route transitions.** Content crossfades with a 6 px rise in at most 250 ms; the sidebar, the top bar and the case stepper do not move. Within a case, a step change slides content 12 px in the direction of the step.
> **Never:** hijack or smooth the page scroll, rubber-band anything the user is not dragging (`overscroll-behavior` stays native, no scroll-linked scenes), glow, gradient, blur, or motion that delays input.
> **Parity.** Every drag has a button and a keyboard path that does the same thing (Escape or a Close button closes a panel; Alt+Arrow moves an item; Enter opens a source). Dragging is an enhancement, never the only way.
> **Reduced motion** (system or in-app): springs are replaced by an instant jump or a 100 ms opacity fade; rubber-banding is off (the element stops at its limit); route transitions do not animate.
> **Press feedback.** Buttons and draggable handles scale to 0.97 on press (100 ms) and spring back on release; no lift on touch.

### 2b. Parameters (perceptual duration T and bounce b mapped to mass 1, stiffness k = (2π/T)², damping c = 4π(1-b)/T, from Apple's WWDC23 talk)

| Use | Where in our app | T | b | k | c | Rubber-band allowance d | Release rule |
|---|---|---|---|---|---|---|---|
| Button press | `components/ui/button.tsx`, handles | 0.15 s | 0 | 1755 | 83.8 | none | scale 0.97 down in 100 ms, spring back |
| Tab or step indicator | `ui/tabs.tsx` (Library, Dossier), `StageRail` current-step tint | 0.25 s | 0 | 632 | 50.3 | none | time-based: `--ease-spring` over 275 ms |
| Panel drag (side panel: source, chat, Details; Documents popover on touch) | `workspace/SidePanel.tsx`, `TraceDrawer.tsx` | 0.40 s | 0 | 247 | 31.4 | 48 px past fully open (max visible about 40 px) | closes if projected position > 50 % of width or velocity > 500 px/s |
| Sheet dismiss (below `lg`: source sheet, chat sheet, Gate checklist sheet, palette on touch) | `SidePanel` sheet mode, `GateModal`, `CommandPalette` | 0.35 s | 0.10 | 322 | 32.3 | 64 px upward | dismisses past 25 % of height or velocity > 800 px/s |
| Gate that holds | Gate buttons while items are open | 0.30 s | 0 | 439 | 41.9 | 12 px | always springs back; opens the list of open items |
| Timeline scrub with momentum | List of Dates, Rights timeline | 0.30 s | 0 | 439 | 41.9 | 32 px at both ends | momentum `project(v, 0.99)`, then snap to nearest date |
| Landing demo cards | hero specimen | 0.45 s | 0.15 (C: 0.2) | 195 | 23.7 (C: 22.3) | 80 px | snap to the drop target if within 120 px or projected inside it |
| Route transition | `app/**/page.tsx` | not physics | | | | | 200 ms crossfade + 6 px rise, `--ease-spring` |

Rubber band with d = 160 px gives 10, 24, 41, 65, 93 px for pulls of 20, 50, 100, 200, 400 px; with d = 48 px it gives 9, 18, 26, 33, 39 px. A critically damped spring is within 1.4 % of its target at t = T, so T = 0.45 s settles by about 450 ms, which is what the amendment allows.

CSS token for time-based spring-like motion (critically damped, sampled at 12 steps over 1.1 T):
```css
--ease-spring: linear(0, 0.114, 0.32, 0.515, 0.67, 0.782, 0.859, 0.911, 0.944, 0.965, 0.979, 0.987, 1);
/* use with 275 ms for the tab indicator, 220 ms for route content */
```

### 2c. Implementation choice

Recommendation: **zero dependencies for now.** Pointer events with `setPointerCapture`, `touch-action: none` only on the drag handle (so page scroll stays native), a velocity tracker over the last 80 ms, the solver below, CSS `linear()` for time-based curves and React 19.3 `<ViewTransition>` for routes and shared-element morphs. Cost about 3 to 4 KB, no peer-dependency risk with React 19, and every curve is ours to tune and test with vitest.

When to add a library (not installed now; the lead installs on the branch):
- `motion` (the current framer-motion, `motion/react`, supports React 19): only if we build list reorder or layout animations. With `LazyMotion` and `m` the first render costs about 4.6 KB, but drag and layout need `domMax` (+25 KB). Not worth it for panels and sheets.
- `@dnd-kit/sortable`: if the owner wants grounds reorder, because it ships a keyboard sensor and screen-reader announcements; check its React 19 peer range before installing.
- Not `vaul`: its README says it is unmaintained.

The solver (`lib/motion/spring.ts`, about 30 lines):
```ts
export interface SpringOpts { stiffness: number; damping: number; mass?: number; restDelta?: number; restSpeed?: number }

/** Mass 1 + stiffness + damping from Apple's perceptual duration T (s) and bounce b. */
export const fromPerceptual = (T: number, b = 0): SpringOpts => ({ stiffness: (2 * Math.PI / T) ** 2, damping: (4 * Math.PI * (1 - b)) / T, mass: 1 });

/** iOS rubber band: x past the limit, d the allowance; diminishing returns, never exceeds d. */
export const rubberband = (x: number, d: number, c = 0.55): number => Math.sign(x) * (1 - 1 / ((Math.abs(x) * c) / d + 1)) * d;

/** Where a flick would stop (WWDC18 "Designing Fluid Interfaces"): v in px/s, rate 0.998 normal, 0.99 fast. */
export const project = (v: number, rate = 0.998): number => ((v / 1000) * rate) / (1 - rate);

/** Runs a spring from `from` to `to` with initial velocity v0 (px/s). Returns a stop function; to interrupt, stop it and
 *  start a new spring from the last (x, v) passed to onUpdate, which keeps the motion continuous. */
export function spring(from: number, to: number, v0: number, o: SpringOpts, onUpdate: (x: number, v: number) => void, onRest?: () => void): () => void {
  const m = o.mass ?? 1, restDelta = o.restDelta ?? 0.5, restSpeed = o.restSpeed ?? 10, STEP = 1 / 240;
  let x = from, v = v0, last = performance.now(), acc = 0, raf = 0;
  const tick = (now: number) => {
    acc += Math.min((now - last) / 1000, 0.064);
    last = now;
    while (acc >= STEP) {
      const a = (-o.stiffness * (x - to) - o.damping * v) / m;
      v += a * STEP; // semi-implicit Euler, stable for k up to about 2000 at this step
      x += v * STEP;
      acc -= STEP;
    }
    if (Math.abs(v) < restSpeed && Math.abs(x - to) < restDelta) { onUpdate(to, 0); onRest?.(); return; }
    onUpdate(x, v);
    raf = requestAnimationFrame(tick);
  };
  raf = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(raf);
}
```
Write `transform` directly on the element inside `onUpdate` (no React state per frame). Under reduced motion `useDrag` skips the spring and sets the end state, or runs a 100 ms opacity fade.

---

## 3. The user journey, stage by stage

Persona: counsel at a legal-aid clinic or a District Legal Services Authority, tired and short of time, preparing bail for an undertrial on a laptop in a court corridor or office, sometimes facing a batch of 100+ files, reading Hindi and English. The table gives the goal and worry, the feature, the UI idea (physics only where it helps), what it saves, and how the landing page shows it. Every landing specimen runs on the real sample data in `lib/mock/case0007.ts` (FIR 112/2024, the Hindi quote "प्रथम सूचना रिपोर्ट सं. 112/2024 दिनांक 14.08.2024" with its English line), with no sign-in and no video.

| Stage | Goal and worry | Feature | UI idea | Saves or prevents | On the landing |
|---|---|---|---|---|---|
| Arrive | "What is this, can I trust it, can I try it without uploading a client's file?" | Landing, sample data mode | Hero = a live specimen of case-0007 that can be touched; "Try the sample case" opens `/case/case-0007` in demo mode. The trust facts (no predictions, counsel approves, files stay here) sit beside it as plain sentences, not badges. | Understanding in one screen, with no trust leap | The hero itself |
| Upload papers | "My papers are scanned, photographed sideways, half Hindi. Will it choke?" | Munshi intake, DropZone, MicButton | Dragging files over the window gives the drop zone a 1.02 scale and a maroon hairline (it is the target, not decoration). Each file becomes a row with a page strip. A photo taken on the phone can be dropped too. Dictation shows the transcript growing in place with an Edit control. | Fewer wrong uploads; dictation for the facts that are not in the papers | "Drop the FIR on the file": drag the FIR card (or press "Add this FIR") onto the dossier |
| Watch intake | "What did it read, and what did it miss?" | Ingestion report, per-page route, open questions | A page strip where each thumbnail fills as it is read, with one word under it (Read, Typed text, Unreadable). An unreadable page offers "Add a clearer copy". Munshi's questions become the first items of "Needs your attention". One progress line, no agent dashboard. | Missing pages found before drafting, not at the hearing | The specimen fills its page strip; one page says "Unreadable: add a clearer copy" |
| Dossier and List of Dates | "Is every fact right, and where did it come from?" | Peshkar dossier with sources, edit in place | Click a value to open the source; on touch, pull the row down to reveal the verbatim paragraph inline (rubber band past full height, snaps open or closed). Hindi and English sit side by side. Edit in place stamps "Corrected by you". The List of Dates is a horizontal timeline you can scrub (momentum, snaps to dates) with the vertical list below for keyboard and screen readers. | Checking a fact takes one click instead of a search through the PDF | "Pull a fact to see the words behind it": the arrest date row opens to the remand-order sentence with the date highlighted |
| Rights Radar | "Is she entitled to default bail today? I cannot afford to say yes wrongly." | Rights Radar with CHECK states (the false-ELIGIBLE safety) | A rights timeline from the arrest date: the 60 or 90 day default-bail window (BNSS 187) and the undertrial limit (BNSS 479) drawn as flat ranges. A range that depends on a missing fact (charge-sheet date not in the papers) is drawn as an outline in saffron with the word "Check", never as a filled "Eligible". Scrubbing "If the hearing is on..." shows which checks change state by that date; the label is a date, not a forecast. | Filing on the right day; never claims eligibility the papers do not support | "Move the hearing date": the default-bail range stays "Check: the charge sheet date is not in the papers" |
| Gate 1 | "Have I really looked at everything before it drafts?" | Gate 1, enforced in code | The "Confirm facts and continue" button shows the count of open items. While items are open, pressing or dragging it moves it at most 12 px with rubber-band resistance, it springs back, and the list of open items opens with a jump button each. At zero the lock icon opens (200 ms stroke change) and the button works normally, followed by the existing confirm dialog. | No accidental approval; the reason the button is locked is shown at the moment of trying | "Try to continue": the button holds and shows the two open items; resolve them (buttons) and it opens |
| Retrieval and drafting | "Are these authorities real and quoted correctly? Is any ground made up?" | Vakeel drafter, verbatim authorities, NEEDS_REVIEW, UNSUPPORTED | Grounds in document style with numbered sources. A number opens the verbatim paragraph of the judgment beside the claim. A ground that failed its check stays in place with "Needs check" and a saffron hairline in the margin. Grounds can be reordered by drag on a handle, with Move up and Move down buttons and Alt+Up/Down (see question 3). | Hallucinated or misquoted authority caught before filing | "Open a ground": one ground with [1] opening the paragraph from the judgment, one marked "Needs check" |
| Prosecution sparring | "What will the APP say, and do I have an answer?" | Abhiyojak objections and replies (ANSWERED, PARTLY, UNANSWERED) | Objections as a stack of cards; the unanswered ones on top, open. On touch, swipe reveals "Answer" and "Mark answered in court" (never commits on swipe, needs a tap). Each reply cites the ground it relies on. | Fewer surprises at the hearing | One objection card with an unanswered state and a "Write a reply" button |
| Gate 2 | "Once I approve, what is locked?" | Gate 2, export impossible before it | Same holding button as Gate 1. The confirm dialog lists exactly what the approval locks. Export buttons do not exist before approval (kept). | No export of an unchecked draft | "Try to export before approval": the export row is absent and the gate holds, with the sentence why |
| Export | "I need a Word file now, and the hearing card." | DOCX application, hearing card, List of Dates | One row per output with its format, page count and a Download button; the application preview at true page width. A short check-draw on download. | No reformatting before filing | Static row of the three outputs, with the disclaimer |
| Next hearing, changes | "New papers arrived. What changed and what must I redo?" | Change detection and redraft | A change banner leads to a two-column "Before / Now" for changed facts with a saffron wash on the words that changed. Affected grounds are marked and Gate 2 re-locks with a sentence explaining why. "Redraft only these" is the primary action. | Redraft limited to what changed; no stale ground filed | One changed date shown before and after, with "Gate 2 needs your approval again" |
| Batch desk | "100 files, which ones are urgent this week?" | Pairokar triage with deadlines | Drop a folder; cards ranked by days left, with the reason in a sentence ("Default bail window opens in 6 days"). Keyboard: J/K to move, Enter to open, P to pin. No manual reorder of the ranking (it would hide urgency); pinning is explicit. | Urgent cases are not missed in a pile | Six sample cards from `lib/mock/desk.ts`, ranked, with days left inline in ordinary type |
| Library and chat | "Find the judgment that says X; does the old IPC case still apply under BNS?" | Precedent search, citation graph, IPC to BNS bridge, chat with citations | Search results show the matched paragraph with the query terms marked; the bridge shows the IPC and BNS texts side by side with the difference marked (SAME_TEXT, CHANGED, NEW in words). The tab indicator slides between Search, Graph and Bridge. | Faster research with sources that can be checked | "IPC 420 now reads as BNS 318(4)": the two texts side by side |
| Privacy (across stages) | "Do my client's papers leave this computer?" | Local processing, `VS_EXTERNAL`, pseudonymisation, consent | Landing band "What leaves this computer": a plain diagram with This computer (papers, models, drafts) and External services drawn as an outline with "Off". A toggle "Show what an external service would see" swaps names for "Accused-1", "PS-1" in a real sentence. In the app the mode chip stays the single place that states the mode. | Trust based on a check the visitor can do | The band itself |

---

## 4. Three directions for the landing page

All three keep the Manuscript palette (maroon and cream dominant; saffron, indigo and neem with their fixed meanings), the fonts (Newsreader headings and document text, Schibsted Grotesk interface, Spline Sans Mono for sources, Noto Serif Devanagari and Hind), the disclaimer and NALSA in the footer, and the "Things we do not do" list. They differ in how much the visitor can touch and how strong the physics is.

### Direction A: "The file, opened" (subtle)
Idea: keep the band page, replace the film in the hero with a small panel of the real sample case that the visitor can click through.

```
+--------------------------------------------------------------------------------+
| [mark] Vakeel-Sahayak     How it works  Sources  Privacy  Help  [Open workspace] |
+--------------------------------------------------------------------------------+
| Prepare a bail application         | State v. Accused-1, FIR 112/2024          |
| from the case file. Every fact     | [Facts] [Rights] [Draft]   <- indicator   |
| traced to its source.              |-------------------------------------------|
|                                    | Date of arrest 14.08.2024  FIR p.1  Confirmed
| Upload the papers; it reads them,  |  > "प्रथम सूचना रिपोर्ट सं. 112/2024 ..."   |
| checks bail rights against the     |    "FIR No. 112/2024 dated 14.08.2024"    |
| dates and drafts for your review.  | Charge sheet date   Not found in the papers|
| [Try the sample case] [How it works]| Antecedents   Needs your check  [Resolve] |
+--------------------------------------------------------------------------------+
```
Sections: hero with the specimen (tabs Facts / Rights / Draft, real data); How it works (four steps, each with a 1-line specimen excerpt instead of text only); Sources (current indigo band, the quote opens on click); Control and privacy (neem, with the pseudonymised preview toggle); footer (motto, disclaimer, team line).
Colour and type: as today; the saffron offset block is removed; maroon only for actions.
Motions: tab indicator slide (275 ms `--ease-spring`); quote row opens (height via grid-rows, 200 ms); band reveal (existing 250 ms). Physics: press 0.97 only.
Borrows: Linear shows product UI as the hero rather than illustration (https://linear.app/); Stripe uses a live-looking UI fragment inside a product card (https://stripe.com/).
Effort: about 24 hours. Risks: low; the tabs must be real tabs (Radix) and the specimen must not look like a second app.

### Direction B: "Walk the file" (medium, recommended)
Idea: the landing page is the user journey in five touchable specimens on case-0007, each showing one differentiator, ending with the real case opening in the app.

```
+--------------------------------------------------------------------------------+
| [mark] Vakeel-Sahayak   How it works  Privacy  Batch desk  Help   [Continue: State v. Accused-1] |
+--------------------------------------------------------------------------------+
| Prepare a bail application from the case file.        +----------------------+ |
| Every fact traced to its source.                      | Dossier              | |
|                                                        |  FIR number   ...    | |
| [Try the sample case ->]  [See how it works]           |  Date of arrest ...  | |
|                                                        |  (drop the FIR here) | |
|  +-----------+  drag onto the dossier, or              +----------------------+ |
|  | FIR 112/  |  [Add this FIR]                          reading p.1 ... p.3     |
|  | 2024  हिं  |                                                                 |
|  +-----------+                                                                 |
+--------------------------------------------------------------------------------+
| Read   | Check   | Hold   | Draft   | Spar      <- in-page anchors, not numbered   |
+--------------------------------------------------------------------------------+
```
Section order and what each shows:
1. Hero: drag the FIR card onto the dossier (or press "Add this FIR"); rows appear with their source chips, one says "Not found in the papers", one "Needs your check". The page strip shows one unreadable page.
2. Read (saffron tint): pull the arrest-date row to reveal the verbatim Hindi and English sentence (rubber band, snaps open); keyboard Enter.
3. Check (indigo-deep): the rights timeline with "Move the hearing date"; default bail stays "Check" because the charge-sheet date is missing. One sentence: it reports the law and the dates and does not predict bail.
4. Hold (cream with maroon): "Try to continue": the gate button resists and lists two open items; resolve them with buttons; the lock opens. Then "Try to export": no export row until approval.
5. Draft (cream): one ground with a numbered authority that opens the judgment paragraph, one ground marked "Needs check", one objection unanswered with "Write a reply".
6. Privacy (neem tint): "What leaves this computer" diagram and the pseudonymised preview toggle.
7. Batch desk (parchment-deep): six ranked cards with days left in plain type; J/K hint.
8. Close (maroon, flat, no lattice): "Open the sample case" (a shared-element morph: the specimen's case title becomes the workspace breadcrumb) plus a line on who built it and a link to the method and limits (About). The Preamble quote moves to the footer beside the motto.
Colour and type: each band keeps its meaning (saffron for "check this", indigo for sources, neem for control). Headings in Newsreader at the current scale (no numerals); specimens use the product's own components (`StatusBadge`, `SourceChip`) so the landing cannot drift from the app.
Motions: specimen drag and snap (spring T 0.45 s, b 0.15, rubber band d 80 px); gate hold (12 px rubber band, T 0.3 s); route morph into the workspace (250 ms). Plus the existing 250 ms band reveal, which stays.
Borrows: the Next.js view-transitions guide for the shared-element morph and anchored header (https://nextjs.org/docs/app/guides/view-transitions); Apple's spring model and velocity hand-off (https://developer.apple.com/videos/play/wwdc2023/10158/); Nyaaya's plain, user-addressed copy and its Hindi and Kannada entry points (https://nyaaya.org/); Harvey's dedicated security and controls section, here made checkable (https://www.harvey.ai/).
Effort: about 56 hours (specimens 30, physics primitives 8, transitions and navigation 8, tests 10).
Risks vs DESIGN.md: needs the motion amendment (section 2a); drag must have button parity everywhere (planned); seven bands is long, so each specimen must stay one screen tall at most; the specimens must not drift from real components (use them directly).

### Direction C: "The desk" (expressive)
Idea: the hero is a desk with the real papers of case-0007 as sheets (FIR, remand order, bail order) that can be picked up, stacked and thrown into the case file; the whole landing reads like a paper file being assembled.

```
+--------------------------------------------------------------------------------+
| [mark] Vakeel-Sahayak                                         [Open workspace]  |
|                                                                                 |
|    +---------+                                                                  |
|    | FIR     |\   +--------+        Prepare a bail application from the        |
|    | 112/2024| \  | Remand |        case file. Every fact traced to its source. |
|    +---------+  \ | order  |                                                    |
|          +-------\+--------+        [Try the sample case]                       |
|          | Bail order (draft) |                                                 |
|          +--------------------+     [ Case file tray: drop papers here ]        |
+--------------------------------------------------------------------------------+
```
Sections: desk hero; then the same journey specimens as B, but each enters as a sheet sliding onto the desk (on scroll reveal, 250 ms, not scroll-linked); privacy shown as the tray never leaving the desk; batch desk as a stack you can fan out.
Colour and type: cream sheets on parchment-deep; depth by scale (1.02 when lifted) and one neutral shadow on the lifted sheet only (floating layer rule); no glow.
Motions: free drag with inertia (`project(v, 0.998)`) and bounce 0.2; lift and drop (scale 1 to 1.02, shadow on, 180 ms); fan-out of the batch stack (staggered springs, T 0.4 s).
Borrows: Apple's momentum projection and interruptible springs (WWDC18 Designing Fluid Interfaces, https://developer.apple.com/videos/play/wwdc2018/803/); Linear's product-first hero (https://linear.app/).
Effort: about 95 hours. Risks: the free desk is the most decorative idea (papers you move for fun), heavier on low-end laptops, hard to make fully keyboard-equivalent, and it pushes against "Product first" and the floating-shadow rule. I would not ship C as is.

| | A | B | C |
|---|---|---|---|
| Touchable demo | tabs and clicks | five specimens with drag | free desk plus specimens |
| Physics intensity | press only | drag, snap, rubber band, gate hold | inertia, bounce 0.2, stacks |
| Shows the differentiators | partly | all six | all six, less directly |
| Effort | 24 h | 56 h | 95 h |
| DESIGN.md risk | low | medium (amendment needed) | high |

---

## 5. Signature interactions: build, maybe, and not

Build (each helps a step of the journey and has a keyboard and button path):
1. **Gate that holds** (Gate 1 and 2, landing "Hold"): the reason a gate is closed appears at the moment of trying; resolves to the existing confirm dialog.
2. **Pull a fact to its words** (touch), click on desktop: the core differentiator, verbatim source in place.
3. **Rights timeline with "Check" ranges** and a hearing-date scrub: makes the false-ELIGIBLE safety visible and helps choose a filing date.
4. **Drag to close panels and sheets** with rubber band (SidePanel, sheets below `lg`, palette on touch): matches what touch users expect; Escape and Close stay.
5. **Shared-element morph** from a case card or the landing specimen to the workspace title: tells the user it is the same case.
6. **"What an external service would see"** toggle: privacy shown, not promised.

Maybe (needs an API change or an owner decision):
- **Drag a source passage onto a claim marked "Needs check"** to attach it as support: useful for repairing a ground, but the API needs a field for a counsel-attached source (today only resolutions are sent with Gate 2). Keyboard path: "Attach to ground..." menu in the source panel.
- **Grounds reorder by drag** (dnd-kit or Motion Reorder): counsel does decide the order of grounds; needs a persisted order in the brief.
- **Swipe to reveal actions** on Needs your attention and objections (touch only, never commits on swipe).

Not build:
- **Slide to approve** a gate: slower for daily use, poor keyboard parity, and it turns a legal approval into a toy; the holding button plus the confirm dialog is enough.
- **Free paper desk** (Direction C hero): decoration for its own sake.
- **Manual reorder of the batch-desk ranking**: it would hide urgency; pinning is explicit instead.
- **Scroll-linked storytelling, parallax, smooth scrolling**: banned and slow on low-end laptops.
- **Animated counters or agent avatars**: banned (stylised numerals, dashboard of agents).
- **Haptic or sound feedback**: unreliable on laptops, distracting in court corridors.

---

## 6. Transitions and navigation

Logo and re-entry
- The logo goes to `/` from every route: `Sidebar.tsx` and `MobileDrawer.tsx` change `href="/cases"` to `/` with `aria-label="Vakeel-Sahayak home"`. Cases stays the first sidebar item, so the app's home is one click away.
- Remember the last case: `usePublishCaseMeta` (`components/shell/meta.ts`) also writes `vs:last-case = {id, title, stageLabel, at}` to localStorage. The landing header button and the hero secondary button read it after mount: "Continue: State v. Accused-1" (stage in the tooltip and in the accessible name), else "Open workspace". To avoid layout shift, the button keeps a fixed minimum width and the title truncates. A "Not this case? All cases" link sits beside it.
- The command palette is also available on the landing page (Ctrl/Cmd+K) for returning users.

Page transitions (recommended approach)
- React 19.3 `<ViewTransition>` with `experimental: { viewTransition: true }` in `next.config.mjs` (Next 15.5). Each `app/*/page.tsx` wraps its content in `<ViewTransition enter="page" exit="page" default="none">`. CSS: old content fades out in 120 ms; new content fades in over 200 ms with a 6 px rise, `--ease-spring`; the whole transition stays under 250 ms. `::view-transition { pointer-events: none }` so clicks are not lost.
- Fixed during a transition: the sidebar (`view-transition-name: app-sidebar`), the top bar (`app-topbar`) and, inside a case, the stepper row (`case-stepper`), all with `animation: none`. On the landing page the logo carries `brand` so it stays put when entering the app.
- Within a case, a step change slides the step content 12 px left or right by step order, 200 ms (`addTransitionType('step-forward' | 'step-back')`).
- Shared element: the case title. The workspace is client-only (`WorkspaceShellLazy`, `ssr: false`), so the destination would suspend and no pair would form. Fix: when a case card is clicked, write `{caseId, title}` into the meta store before `router.push`, so the top bar breadcrumb renders the title in the same commit; give both the card title and the breadcrumb title `name={"case-title-" + id}`.
- Fallback: browsers without the API swap instantly (no JS fallback needed). Reduced motion: all `::view-transition-*` durations set to 0.
- Alternative rejected: a `template.tsx` fade remounts the whole subtree on every navigation (losing client state such as the open source panel) and cannot morph shared elements.

Loading and skeletons
- Add `loading.tsx` for `/cases`, `/desk`, `/library` with skeletons that match the final layout (title line, filter row, rows of card height). Fix the workspace skeleton to the real layout: stepper row of 3 rem, then a centred column of the step's width.
- Skeletons appear only after 150 ms (opacity animation delay), so fast navigations show no flash; the existing 1.2 s pulse stays the only loop.

Focus and accessibility
- After a navigation started from the sidebar, the palette or the logo, move focus to the page `h1` (`tabIndex={-1}`); Next's route announcer still reads the title. Step changes keep focus on the stepper (the arrow-key behaviour in `a11y.spec.ts` must keep working).
- View transition pseudo-elements are not in the DOM, so axe results do not change; the a11y spec audits after `document.getAnimations()` settle.
- Drag handles are buttons with a label ("Drag to close, or press Escape"); every drag has its button. The gate-hold popover is a labelled region whose first jump button takes focus.

---

## 7. Usability testing without participants

1. **Heuristic pass** (Nielsen's ten, adapted): visibility of status (progress line, gate counts), match with the court's words (FIR, remand, List of Dates), user control (Undo toasts, gates), consistency (fix "Stage n of 7"), error prevention (gates, CHECK), recognition over recall (Needs your attention), flexibility (shortcuts), minimal design, recovery (unreadable page path), help (Help page). One table per stage of section 3, pass or fail with a file reference.
2. **Cognitive walkthrough** for the persona per stage: at each step ask "will she know what to do, see the control, link it to her goal, see progress?"
3. **Keyboard-only run**: landing to Gate 2 on case-0007 with Tab, Enter, Escape, arrows and Ctrl+K only; count key presses and record any trap; becomes a Playwright spec.
4. **Playwright flows with timings**: measure, with the mock backend, time and clicks to the first verbatim source on the landing page, to Gate 1, and to export; set budgets (for example first source under 2 clicks, Gate 1 under 12 actions) so later changes cannot regress them.
5. **Reduced-motion pass**: the existing `reduced-motion` project extended to the landing demo, panels and gates; assert no running animations and that every result is reachable.
6. **Small-screen pass** at 360 x 740 and 390 x 844, plus 200 % zoom at 1280: no horizontal scroll, sheets full screen, drag handles at least 44 px.
7. **Hindi pass**: every Devanagari string has `lang="hi"` (existing test), line height 1.7, no clipped matras in chips.
8. **Low-end device pass**: Chrome DevTools CPU throttle 4x and Slow 4G; INP under 200 ms during a drag; the spring solver stays under 2 ms per frame.
9. **Axe** in both motion modes, after interactions (open panel, gate popover, sheet).

---

## 8. Recommendation and questions for the owner

Recommendation: **Direction B ("Walk the file")** with the build list of section 5, the zero-dependency physics of section 2c, the DESIGN.md amendment of section 2a, and the navigation and View Transitions plan of section 6. It is the one direction where every moving part shows a feature that changes what counsel does, and the landing page uses the same components as the app.

Questions (my pick first):
1. Direction: **B Walk the file** / A The file, opened / C The desk.
2. Physics scope: **landing specimens plus panels, sheets and the gate hold** / landing only / everything including grounds reorder.
3. Grounds reorder and "attach a source to a claim": **later, after the API supports order and counsel-attached sources** / now, client-only (lost on reload) / never.
4. Library: **zero dependencies now, revisit for reorder** / add `motion` now / add `@dnd-kit` now.
5. Logo: **refine the V and beam (short hangers and pans at 24 px and up, the current mark at 16 px)** / keep as is / explore a new mark (a case-file tab with a check).
6. Close of the landing page: **replace the Preamble band with "Open the sample case" and a line on who built it and how it is tested (motto and Preamble move to the footer)** / keep the Preamble band without the lattice / keep it as is.

---

## 9. Build plan for Direction B (one commit each)

1. Navigation: logo to `/` in `Sidebar.tsx` and `MobileDrawer.tsx`; new `e2e/navigation.spec.ts` (logo from `/cases`, `/case/case-0007`, `/library` lands on `/`).
2. Last case: `lib/lastCase.ts`, written from `usePublishCaseMeta`; the "Continue: ..." button on the landing; vitest for the store, e2e for the round trip (open case, go home, continue).
3. Consistency fixes from the audit: "Stage n of 6" in `CaseCard.tsx`, stage names, the sticky footer edge, the `.hl-mark` wrap bug; stale notes in `FOUNDATION_NOTES.md` and `tokens.css`.
4. DESIGN.md motion amendment and tokens (`--ease-spring`, `--dur-gesture-max: 450ms`).
5. Motion primitives `lib/motion/{spring,rubberband,useDrag,usePress}.ts` with vitest (settles within 1.2 T, rubber band below d and monotonic, projection, reduced motion skips the spring).
6. Press feedback on `Button` and the sliding tab indicator in `ui/tabs.tsx`.
7. View transitions: config flag, page wrappers, anchored shell, step direction, reduced motion; `e2e/transitions.spec.ts` (sidebar and top bar bounding boxes do not change during navigation, no animation after 300 ms, none under reduced motion).
8. Loading skeletons that match the layout, focus to `h1` after navigation; extend `a11y.spec.ts`.
9. Drag to close `SidePanel` and sheets; `e2e/gestures.spec.ts` (mouse drag past threshold closes, short drag springs back, Escape still closes, reduced motion closes without animation).
10. Gate hold on Gate 1 and Gate 2 buttons (keep test ids `confirm-facts-button` and the gate dialog flow); e2e: pressing a locked gate opens the list and does not approve.
11. Case-title shared-element morph from the cause list.
12. Landing hero specimen "Drop the FIR on the file" from `lib/mock/case0007.ts`, replacing `HeroLoop`; `e2e/landing-demo.spec.ts` (drag and the "Add this FIR" button both fill the dossier; one "Not found" row exists).
13. Landing "Read" specimen (pull to reveal the Hindi and English sentence).
14. Landing "Check" specimen (rights timeline, the default-bail range stays "Check").
15. Landing "Hold" specimen (gate holds, export absent before approval).
16. Landing "Draft" specimen (a ground with a numbered authority, one "Needs check", one unanswered objection).
17. Privacy band with the pseudonymised preview; batch desk band; new close and footer.
18. Rights timeline in the workspace (the Check rights step) with the list below it for keyboard and screen readers.
19. Update `landing.spec.ts` (band order, `# RECONCILED` notes where the plan changed), `reduced-motion.spec.ts`, `testids.ts`; add a timing budget spec (section 7, item 4).
20. Logo refinement if chosen: `public/brand/*.svg`, `Logo.tsx`, icons, DESIGN.md "Logo" section.

Each step: `npx tsc --noEmit -p .`, `npm run lint`, the touched vitest files and the touched Playwright specs (Chromium and the reduced-motion project). No `npm install`: steps 1 to 20 need no new package.

---

## 10. Sources

- Linear landing page: https://linear.app/
- Stripe landing page: https://stripe.com/
- Harvey landing page: https://www.harvey.ai/
- Nyaaya: https://nyaaya.org/
- Zerodha Varsity: https://zerodha.com/varsity/
- The Marshall Project (editorial structure: topic tag, date, headline, deck): https://www.themarshallproject.org/
- Next.js guide, designing view transitions (shared elements, anchored header, reduced motion, pointer events): https://nextjs.org/docs/app/guides/view-transitions
- Next.js 15 `viewTransition` config: https://nextjs.org/docs/15/app/api-reference/config/next-config-js/viewTransition
- Next.js 15.2 release notes: https://nextjs.org/blog/next-15-2
- Chrome, same-document view transitions: https://developer.chrome.com/docs/web-platform/view-transitions/same-document
- Chrome, CSS `linear()` easing (spring approximation): https://developer.chrome.com/docs/css-ui/css-linear-easing-function
- Apple WWDC23, Animate with springs (duration and bounce, mapping to stiffness and damping, velocity hand-off): https://developer.apple.com/videos/play/wwdc2023/10158/
- Apple WWDC18, Designing Fluid Interfaces (momentum projection, interruptible gestures): https://developer.apple.com/videos/play/wwdc2018/803/
- UIScrollView inertia, bouncing and rubber-banding: https://www.holko.pl/2014/07/06/inertia-bouncing-rubber-banding-uikit-dynamics/
- Kivy damped scroll (rubber-band coefficient 0.55): https://kivy.org/doc/master/_modules/kivy/effects/dampedscroll.html
- Motion bundle size (LazyMotion, domAnimation, domMax): https://motion.dev/docs/react-reduce-bundle-size
- Vaul (unmaintained notice): https://github.com/emilkowalski/vaul

Fetch notes: clio.com, sci.gov.in and one Apple design skill page returned 403 and are not used as sources. The rubber-band formula comes from the owner's brief; the 0.55 constant is backed by the Kivy and UIScrollView sources above.
