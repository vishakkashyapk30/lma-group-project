# Vakeel-Sahayak frontend design

A calm tool for a legal-aid lawyer who uses it daily. Dense where it should be, fast, legible. It should read like mature case-management software, not a showcase.

## Principles

1. Product first. Structure comes from type hierarchy, spacing and hairline dividers, not decoration.
2. One dominant accent. Maroon marks the primary action, the active place and links. Saffron, indigo and neem are secondary colours with fixed meanings (see Colour) and appear mainly as landing bands and status text.
3. Honest labels. "AI-generated draft. Not legal advice.", the sensitive-matters decline and the privacy statements stay exactly where the law and ethics need them.
4. Nothing delays the user. No intro sequence, no scroll scenes, no smooth-scroll library. Motion confirms a change and gets out of the way.
5. No layout shift. Skeletons match the size of what replaces them; the sidebar width is a token.

## Information architecture

```
/            Landing (marketing, own header and footer, outside the app shell)
/cases       Cases (home of the app)
/case/[id]   Case workspace: a stepper and one step at a time
/desk        Batch desk
/library     Precedent library
/help        Help: start a case, shortcuts, limits (links to /about)
/about       How it works and its limits (reached from Help)
/settings    The server, its model and privacy settings and the data folder (read from GET /healthz)
```

App shell (every route except `/`):

- Left sidebar: Cases, Batch desk, Precedent library, Help, Settings. Icons plus labels, active state (tint, maroon text, thin left mark), collapsible to an icon rail (remembered in localStorage, tooltips carry the labels). Inside a case it stays an icon rail so the step gets the width. Below `lg` it becomes a drawer opened from the top bar. The logo at its top (and in the drawer) goes to the landing page `/` from every route; Cases stays the first item, one click away.
- Top bar: breadcrumb (page title, or `Cases > case title` with `Stage: <name>` inside a case), search field that opens the command palette (Ctrl/Cmd+K), mode chip, primary New case button, settings and help menu.
- Mode chip: `Local · Sample data` in demo mode (built-in sample cases, changes stay in the browser), `Local · Connected` when the API answers, and `Local · Not connected` when a live server stops answering. It links to Settings and never claims more. Product builds are live: an unreachable server is an error on the page, never the sample case (`NEXT_PUBLIC_API_MODE`).
- Command palette: Actions (New case, Reduce motion, Collapse sidebar), Pages, and Cases (fetched when opened). Combobox plus listbox semantics, arrows, Enter, Esc.
- Help menu: Help and shortcuts, How it works and its limits, Product overview, Reduce motion, NALSA 15100.
- Case stepper: Add documents, Review facts, Check rights, Draft grounds, Prepare for the hearing, Export. Each step has an indicator (check, ring, empty ring, lock) and its state is read out as a word. Likely objections live inside Draft grounds; the gates live inside their steps (see Workspace principles).

## Workspace principles

The case workspace (`components/workspace`) is built for a lawyer working through one bail file, often on a laptop between hearings.

1. One step at a time. The stepper shows where the file is; the page shows one step with one primary button at its foot ("Confirm facts and continue", "Continue to Export"). Locked steps say why ("Opens once you confirm the facts").
2. What needs counsel comes first. Every step opens with "Needs your attention": unreadable pages, Munshi's questions, facts not found, conflicting documents, grounds to review, unanswered objections. Each item has one jump button. An empty list says so in a sentence.
3. Gates are decisions inside the steps. Review facts ends in "Confirm facts and continue" (Gate 1) and Export in "Approve this draft for export" (Gate 2). The button stays disabled while the list above is not clear, and opens a confirm dialog that says what the approval locks. The export buttons do not exist before Gate 2. Counsel's resolutions are sent with the approval and recorded on the server.
4. Sources on demand, never a permanent pane. A fact or a numbered citation opens the source panel (quote, Hindi beside English, page with the highlighted box, route, language). Chat is a drawer, the case file a popover (Documents), the agent trace the Details drawer. At most two columns at once.
5. Plain status words. Badges read "Confirmed from the documents", "Calculated", "Not found", "Entered by you", "Corrected by you", "Needs your review"; the raw enum stays in `data-status` and under Details. Different meanings never share a word.
6. Nothing is dropped silently. A ground that failed its check stays in the draft with a "Needs check" mark; a fact the papers do not give stays "Not found" until counsel adds it or marks it unknown.
7. Layout by width. From `xl` the stepper and the case controls (Documents, Details, Ask) share one row; below `xl` the stepper takes its own row and scrolls sideways, keeping the current step in view. Below `2xl` Documents and Ask show a count and a short word (their full names stay for screen readers). Below `lg` the source panel and the chat are full-screen sheets that take focus when they open and close with Escape. No page scrolls sideways at any width.
8. Agent work is a quiet line. While an agent works, one progress line with a small breathing glyph says what is happening ("Reading the papers"); there is no dashboard of agents. Long work runs on the server without freezing the page, and the line updates from the event stream.

## Typography

| Role | Family | Why |
| --- | --- | --- |
| Headings, document text | Newsreader (variable, optical size) | A sober text serif drawn for reading on screen; the optical-size axis gives sturdy headings and an open 17 px body. Legible, not a default. |
| Interface | Schibsted Grotesk (variable) | A neutral grotesque with a slightly humanist build and clear numerals; reads well at 13 to 15 px and is not one of the usual generated-site faces. |
| Citations, ids, sources | Spline Sans Mono (variable) | A restrained mono that sits beside the grotesque without shouting. |
| Hindi beside the serif | Noto Serif Devanagari (variable) | Matches Newsreader's stroke contrast. |
| Hindi beside the grotesque | Hind | Built as the Devanagari companion to a Latin sans; even colour in tables and chips. |

Rejected after rendering a specimen with Hindi, dates and ids: Literata (wider, heavier, headings wrap early), Albert Sans and Onest (fine but closer to common defaults than Schibsted), Young Serif (too personal for a legal tool; no variable package). Banned by the brief and not considered: Inter, Roboto, DM Sans, Fraunces, IBM Plex, and the rest of the list.

Settings: body 15 px / 1.5, document text 17 px / 1.6 (`.doc-text`), `font-feature-settings: "kern" 1, "liga" 1, "calt" 1`, `font-variant-numeric: tabular-nums` on tables, `time`, `.tabular`, `.cite`. Hindi gets 1.7 line height and the matching Devanagari family through `:lang(hi)`. All fonts are self-hosted through `@fontsource` (`styles/fonts.css`), so builds need no network.

## Colour

Tokens live in `styles/tokens.css`; names are kept from the earlier palette so existing classes keep working. Contrast figures are WCAG 2.1 ratios.

| Token | Hex | Use | on canvas `#F7F5F0` | on white |
| --- | --- | --- | --- | --- |
| parchment | `#F7F5F0` | app canvas | | |
| cream | `#FFFFFF` | panels, inputs, tables | | |
| parchment-deep | `#EFEBE3` | sidebar, hover, subtle fill | | |
| ink | `#211C19` | text | 15.5 | 16.9 |
| ink-soft | `#484039` | secondary text | 9.3 | 10.2 |
| ink-muted | `#675D54` | captions, placeholders | 5.9 | 6.4 |
| line | `#E4DED2` | hairlines | decoration | |
| line-strong | `#8C8277` | control borders | 3.5 | 3.8 |
| maroon | `#7A1626` | primary action, active, links | 9.8 | 10.7 |
| maroon-deep | `#5E101D` | hover on maroon | | |
| oxblood | `#4A0E17` | rare dark areas | | |
| gold-leaf | `#B08D57` | thin accent line, never text | | |
| neem | `#2F6B3A` | verified, supported | 5.9 | 6.4 |
| indigo | `#2E3A6B` | computed | 10.0 | 10.9 |
| sindoor | `#B3261E` | unsupported, flag | 6.0 | 6.5 |
| haldi | `#8C5A0B` | ambiguous, needs review | 5.4 | 5.9 |
| clay | `#6B5E55` | stated or edited by counsel | 5.7 | 6.3 |

### Secondary colours and landing bands

Flat fills only: no gradients, no glow. Meaning: maroon acts, indigo informs (sources, links in the product mock), neem confirms, saffron asks for a check.

| Token | Hex | Use | Contrast |
| --- | --- | --- | --- |
| saffron | `#E8A33D` | rules, outlined "Check" ranges, the margin rule on a ground that needs a check; never text | ink on it 7.8 |
| saffron-tint | `#FBEBCB` | "How it works" band | ink 14.3, ink-soft 8.6, maroon 9.1 |
| saffron-wash | `#FDF5E6` | "needs your check" row highlight | saffron-ink 7.3 |
| saffron-ink | `#764706` | "Needs your check" text | 7.9 on white, 6.7 on tint |
| indigo-deep | `#1E2650` | sources band | white 14.5, parchment 13.3 |
| indigo-pale | `#C9D0F0` | text on indigo-deep; source highlight on white | 9.5 on indigo-deep, ink on it above 12 |
| indigo-tint | `#E7EAF6` | source chip fill | indigo 9.1 |
| neem-tint | `#E4F0E1` | "control" band | ink 14.3, neem 5.4, neem-deep 8.5 |
| neem-deep | `#1E4B2A` | "Approved for export" text, fill behind white | 8.5 on tint, 10.0 with white text |

Landing band order ("Walk the file"): hero parchment (headline and the FIR demo), the walk links, indigo-deep (Read: sources), saffron-tint (Check: rights against the dates), cream (Hold: the two gates), parchment (Draft), cream (Spar), neem-tint (Privacy), parchment-deep (Batch desk), flat maroon (close: open the sample case, who built it, how it is tested), parchment-deep footer (disclaimer, NALSA 15100, the Preamble line in English and Hindi, the motto). Every demo runs on the sample case-0007 data through `components/landing/sample.ts` and the product's own components, with no sign-in and no backend. Maroon and cream stay dominant (hero, buttons, close).

White text on maroon is 10.7:1. Status colours always travel with an icon and a word.

## Logo and icons

Mark: a V whose arms meet a balance beam that carries two short hangers and pans, so the letter and the scales are one figure, white on a maroon square (6/32 radius). Strokes for the V, beam and hangers, two small half-round pans; no dots, no gradient. From 24 px the full mark is used (checked at 24, 28, 64, 128 and 512 px: it reads as scales at the 28 px of the sidebar); below 24 px (the 16 px favicon) the hangers and pans would blur, so the small mark keeps only the V and the beam, joined. One colour throughout. The previous mark (a beam floating above the V) read as a V with a macron at 28 px.

Files (hand-authored SVG) in `public/brand/`: `mark.svg` (maroon tile, white glyph), `mark-mono.svg` (maroon with the glyph cut out, one colour, for print and stamps), `mark-reversed.svg` (cream tile, glyph cut out, for dark backgrounds), `mark-square.svg` (full-bleed, source for the app icons), `lockup.svg` and `lockup-reversed.svg` (mark plus the wordmark). The lockup SVGs name Newsreader in `font-family`; they render correctly where the font is installed and fall back to Georgia elsewhere. In the app the `Logo` component draws the same geometry inline and sets the wordmark in the self-hosted Newsreader, so use the component, not the lockup files, inside the product.

Rules:
- Clear space: at least half the mark's height on every side. Gap between mark and wordmark: 0.35 of the mark's height (10 px at 28 px).
- Minimum size: mark 16 px; lockup 24 px high. Below 24 px use the mark alone.
- Colour: maroon `#7A1626` with white or cream. One-colour use is `mark-mono.svg`. On dark backgrounds use `mark-reversed.svg`. Never recolour, outline, rotate, add effects, or place on busy imagery.
- No Devanagari line under the wordmark: at the sizes the product uses it was not legible beside the Latin. The motto appears only in the landing footer.
- Icons: `app/icon.svg` (the mark), `app/favicon.ico` (16, 32 and 48 px PNGs; the 16 px one from the small mark), `app/apple-icon.png` (180 px, full-bleed), `public/icon-192.png` and `public/icon-512.png` (full-bleed, used by `app/manifest.ts`; theme `#7A1626`, background `#F7F5F0`).

## Spacing, radius, elevation

- Spacing: 4 and 8 px scale (`--space-1` to `--space-24`).
- Radius: 4 px (small), 6 px (controls), 8 px (panels and dialogs). `--radius-pill` is set to 6 px on purpose, so any leftover `rounded-pill` renders as an ordinary small radius.
- Borders: 1 px hairlines. Shadow is `none` except floating layers (menus, dialogs, toasts, the landing preview).
- Layout tokens: sidebar 14.5 rem (3.75 rem collapsed), top bar 3.25 rem, stepper 3 rem, content max 76 rem.

## Motion

One easing: `--ease: cubic-bezier(0.2, 0, 0, 1)`. The older `--ease-*` names are aliases of it.

| Token | Value | Use |
| --- | --- | --- |
| `--dur-fast` | 120 ms | hover, press, colour |
| `--dur-base` | 180 ms | menus, dialogs, sidebar width |
| `--dur-slow` | 250 ms | entrance, reveal, drawers (the ceiling for time-based motion) |
| `--dur-gesture-max` | 450 ms | longest settle of a spring released from a drag |
| `--ease-spring` | `linear(...)` | time-based curve that looks like a critically damped spring (tab indicator, step slide) |

Motion budget:

- Landing first paint (hero text): one fade and 6 px rise on the hero, 250 ms, no delay, no stagger. Total intro: 250 ms.
- Landing sections: one fade and 6 px rise, 250 ms, once, only for sections that start below the fold. Content is visible without JavaScript and under reduced motion.
- App: dialogs, menus, toasts and drawers 180 to 250 ms. Route changes are instant (see "Route transitions" below).

### Direct manipulation and springs

Two kinds of motion, with different budgets:

- **Time-based motion** (anything that plays without the user's hand: reveals, crossfades, menus, the tab indicator, the step slide) stays at 150 to 300 ms with `--ease` or `--ease-spring` (a `linear()` sampling of a critically damped spring). Decorative motion never exceeds 300 ms.
- **Gesture-driven motion** (the user drags a panel, a sheet, a landing demo card, the gate button): the element follows the pointer 1:1 and is released into a spring that carries the gesture's velocity. These springs are critically damped or nearly so (bounce at most 0.15 in the app, 0.2 on the landing demos) and settle within 450 ms (`--dur-gesture-max`). Past a limit, a dragged element resists with the rubber-band curve `offset = (1 - 1 / (x * 0.55 / d + 1)) * d` (x = distance past the limit, d = the element's allowance) and springs back on release. Gestures can be interrupted: grabbing a moving element stops it where it is.

Spring parameters (mass 1, stiffness `(2π/T)²`, damping `4π(1-b)/T` from a perceptual duration T and bounce b; helpers in `lib/motion`):

| Use | T | bounce | Rubber-band allowance d | Release rule |
| --- | --- | --- | --- | --- |
| Button press | 0.15 s | 0 | none | scale 0.97 in 100 ms, back on release |
| Tab and step indicator | time-based, 275 ms `--ease-spring` | | none | |
| Side panel drag to close | 0.40 s | 0 | 48 px past fully open | closes past 50 % of its width or above 500 px/s |
| Sheet drag to dismiss (below `lg`) | 0.35 s | 0.10 | 64 px upward | dismisses past 25 % of its height or above 800 px/s |
| Gate that holds | 0.30 s | 0 | 12 px | always springs back and lists the open items |
| Landing demo cards | 0.45 s | 0.15 | 80 px | snaps to the drop target when released over it or projected into it |

Rules:

- **Never** hijack or smooth the page scroll, rubber-band anything the user is not dragging (`overscroll-behavior` stays native, no scroll-linked scenes), glow, gradient, blur, or motion that delays input. `touch-action: none` only on drag handles, so page scroll stays native.
- **Parity.** Every drag has a button and a keyboard path that does the same thing (Escape or a Close button closes a panel; a button adds the FIR in the landing demo; Enter opens a source). Dragging is an enhancement, never the only way. Focus stays visible on every handle.
- **Reduced motion** (system or in-app): springs are replaced by an instant jump or a 100 ms opacity fade; rubber-banding is off (the element stops at its limit); route transitions do not animate.
- **Press feedback.** Buttons and drag handles scale to 0.97 on press (100 ms) and come back on release; no lift on touch.
- **Route transitions.** Instant, by decision: a crossfade needed Next's `experimental.viewTransition`, which runs the app on the experimental React channel and adds about 12 kB to every route. The sidebar, the top bar and the case stepper never move. Inside a case a step change slides 12 px by direction (CSS, 200 ms), and the case title still moves from its card into the top bar (a measured FLIP, `components/motion/Morph.tsx`), neither of which needs the flag.

Landing motion (styles/landing.css; every element rests in its final state, so reduced motion, no-JS and the end of a run look identical):

- Band reveal: children marked `data-rv` rise 8 px and fade in, 250 ms (`--dur-slow`), 40 ms stagger, once, via IntersectionObserver; bands already on screen are left alone.
- Underline draw on text links (180 ms), 1 px lift on buttons and a 3 px arrow nudge (120 to 180 ms).
- Demos move only under the visitor's hand (springs from the table above): the FIR card follows the pointer and snaps into the dossier or springs home; a fact row resists a pull and opens; the hearing date coasts on a flick and settles on a day; a held gate moves at most 12 px. Each has a button and keyboard path, and under reduced motion each change is instant. Rows that appear use the motion library's presence (220 ms, opacity and a 6 px rise).
- Loops: skeleton opacity pulse and the small glyph that breathes beside a running agent (1.2 s), nothing else.
- Transform and opacity only. `prefers-reduced-motion` and the in-app "Reduce motion" setting collapse every duration to near zero.

## Components

`components/ui`: Button, Card, Badge, Tabs, Dialog, Tooltip, Input, Textarea, Skeleton, ScrollArea, Separator, plus Toast, DropdownMenu, Breadcrumb, EmptyState, Stepper (list, indicator, step).
`components/shell`: AppShell, Sidebar, MobileDrawer, TopBar (with ModeChip and help menu), CommandPalette, ShellProvider (palette, new-case, drawer, collapsed state, Ctrl/Cmd+K), `meta.ts` (case title and stage published to the top bar), `nav.ts` (single list of destinations).
`components/common`: Logo (mark, mark only, reversed), PageHeader, StatusBadge (icon and word, no pill), SourceChip, AgentGlyph.
`components/agents/AgentSignature`: a quiet one-line status with a small glyph that breathes while the agent runs.
`components/landing`: LandingPage, `demos/` (FileDemo, ReadDemo, CheckDemo, HoldDemo, DraftDemo, SparDemo, PrivacyDemo), DeskBand, CloseBand, ContinueCase, Footer, Reveal, `sample.ts`. `components/rights/RightsTimeline` (shared with the Check rights step), `components/common/HoldButton`, `components/motion` (Morph, MotionProvider).
`components/workspace`: WorkspaceShell (stepper row, step, side panel, drawers), StageRail, StepView and `tabs/*` (one view per step), StepFrame and StepFooter, NeedsYou, SidePanel and SourcePanel, ChatPane, TraceDrawer, GateModal (confirm dialog), DocumentsMenu, ProgressLine, ChangeBanner.
`components/settings`: SettingsPage (server address, live/demo mode, connection, the server's model, privacy and data settings).

## Things we do not do

Keep these out of every screen, including future ones.

- No small dots before labels, no pulsing dots, no dot-in-pill badges. Status is an icon (only when it carries meaning) and a short word in normal type.
- No stylised numbers: no big numerals in a display serif or mono, no "01 / 02 / 03" step labels, no Constitution-style stage numerals, no hero stat counters. If a number matters (days in custody, days left) it sits inline in ordinary type beside its label.
- No eyebrow labels (small letter-spaced uppercase above a heading), no all-caps tracking labels as decoration.
- No gradient text, glows, glassmorphism, blurred blobs, sparkle or "magic" icons, emoji, confetti.
- No grids of icon tiles, and no three identical cards in a row with icons.
- No pill badges everywhere. Plain text, one quiet status word, or an icon.
- No em dashes or rhetorical triplets in copy. No "seamless", "effortless", "powerful", "supercharge". No taglines that explain the metaphor. No copy that describes the interface to the user, and no cinematic narration ("your journey", scene captions).
- No rounded-everything cards with soft tinted shadows or tinted borders. Use neutral dividers and hairline borders, and avoid cards inside cards.
- No mock-browser chrome with traffic-light dots in visuals.
- No scroll-jacking, pinned or scrubbed scenes, smooth-scroll libraries, or intros over 600 ms.
- No drag that is the only way to do something, and no physics on things the user is not touching.
- No State Emblem, flag, court logos or gavel.

Do instead: plain, specific, short copy a lawyer would write (Cases, New case, Review facts, Draft, Export); type hierarchy and spacing for structure; tabular numerals for dates and counts; one accent colour, for actions.

## Known follow-ups for later tasks

- The hearing-prep card shows concerns quoted from orders; a quote that is only a paragraph number falls back to "The bench may ask about <factor>" in the client, but the backend should pick a better sentence (`agents/vakeel/hearing.first_sentence`).
- Page images in the source panel come from `GET /api/cases/{id}/files/{doc}/pages/{n}`; the demo backend serves placeholders.
