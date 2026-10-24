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
/case/[id]   Case workspace: stage stepper + three panes
/desk        Batch desk
/library     Precedent library
/help        Help: start a case, shortcuts, limits (links to /about)
/about       How it works and its limits (reached from Help)
```

App shell (every route except `/`):

- Left sidebar: Cases, Batch desk, Precedent library, Help. Icons plus labels, active state (tint, maroon text, thin left mark), collapsible to an icon rail (remembered in localStorage, tooltips carry the labels). Inside a case it stays an icon rail so the three panes get the width. Below `lg` it becomes a drawer opened from the top bar.
- Top bar: breadcrumb (page title, or `Cases > case title` with `Stage: <name>` inside a case), search field that opens the command palette (Ctrl/Cmd+K), mode chip, primary New case button, settings and help menu.
- Mode chip: `Local · Sample data` when no server is connected (built-in sample cases, changes stay in the browser) and `Local · Connected` when the API answers. It reflects `getApiMode()` and never claims more.
- Command palette: Actions (New case, Reduce motion, Collapse sidebar), Pages, and Cases (fetched when opened). Combobox plus listbox semantics, arrows, Enter, Esc.
- Help menu: Help and shortcuts, How it works and its limits, Product overview, Reduce motion, NALSA 15100.
- Case stepper: Intake, Dossier, Rights, Brief, Spar, Hearing prep, File, with the two approval gates (Gate 1, Gate 2) as small buttons. Each step has an indicator (check, ring, empty ring, lock) and its state is read out as a word.

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
| saffron | `#E8A33D` | rules, the offset block behind the hero loop; never text | ink on it 7.8 |
| saffron-tint | `#FBEBCB` | "How it works" band | ink 14.3, ink-soft 8.6, maroon 9.1 |
| saffron-wash | `#FDF5E6` | "needs your check" row highlight | saffron-ink 7.3 |
| saffron-ink | `#764706` | "Needs your check" text | 7.9 on white, 6.7 on tint |
| indigo-deep | `#1E2650` | sources band | white 14.5, parchment 13.3 |
| indigo-pale | `#C9D0F0` | text on indigo-deep; source highlight on white | 9.5 on indigo-deep, ink on it above 12 |
| indigo-tint | `#E7EAF6` | source chip fill | indigo 9.1 |
| neem-tint | `#E4F0E1` | "control" band | ink 14.3, neem 5.4, neem-deep 8.5 |
| neem-deep | `#1E4B2A` | "Approved for export" text, fill behind white | 8.5 on tint, 10.0 with white text |

Landing band order: hero parchment, saffron-tint (how it works), indigo-deep (sources example), neem-tint (control), maroon with a faint white lattice at 7% opacity (Preamble line, gold-pale text), parchment-deep footer. Maroon and cream stay dominant (hero, buttons, close).

White text on maroon is 10.7:1. Status colours always travel with an icon and a word.

## Logo and icons

Mark: a V whose arms carry a balance beam, so the letter and the scales are one stroke, white on a maroon square (6/32 radius). Two strokes, no fill shapes, no dots, no gradient. It holds at 16 px (checked at 16, 32, 64, 128 and 256 px) and in one colour.

Files (hand-authored SVG) in `public/brand/`: `mark.svg` (maroon tile, white glyph), `mark-mono.svg` (maroon with the glyph cut out, one colour, for print and stamps), `mark-reversed.svg` (cream tile, glyph cut out, for dark backgrounds), `mark-square.svg` (full-bleed, source for the app icons), `lockup.svg` and `lockup-reversed.svg` (mark plus the wordmark). The lockup SVGs name Newsreader in `font-family`; they render correctly where the font is installed and fall back to Georgia elsewhere. In the app the `Logo` component draws the same geometry inline and sets the wordmark in the self-hosted Newsreader, so use the component, not the lockup files, inside the product.

Rules:
- Clear space: at least half the mark's height on every side. Gap between mark and wordmark: 0.35 of the mark's height (10 px at 28 px).
- Minimum size: mark 16 px; lockup 24 px high. Below 24 px use the mark alone.
- Colour: maroon `#7A1626` with white or cream. One-colour use is `mark-mono.svg`. On dark backgrounds use `mark-reversed.svg`. Never recolour, outline, rotate, add effects, or place on busy imagery.
- No Devanagari line under the wordmark: at the sizes the product uses it was not legible beside the Latin. The motto appears only in the landing footer.
- Icons: `app/icon.svg` (the mark), `app/favicon.ico` (16, 32 and 48 px, rasterised from the mark), `app/apple-icon.png` (180 px, full-bleed), `public/icon-192.png` and `public/icon-512.png` (full-bleed, used by `app/manifest.ts`; theme `#7A1626`, background `#F7F5F0`).

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
| `--dur-slow` | 250 ms | entrance, reveal, drawers (the ceiling) |

Motion budget:

- Landing first paint (hero text): one fade and 6 px rise on the hero, 250 ms, no delay, no stagger. Total intro: 250 ms.
- Landing sections: one fade and 6 px rise, 250 ms, once, only for sections that start below the fold. Content is visible without JavaScript and under reduced motion.
- App: dialogs, menus, toasts and drawers 180 to 250 ms. No page transitions.
Landing motion (styles/landing.css; every element rests in its final state, so reduced motion, no-JS and the end of a run look identical):

- Band reveal: children marked `data-rv` rise 8 px and fade in, 250 ms (`--dur-slow`), 40 ms stagger, once, via IntersectionObserver; bands already on screen are left alone.
- Highlight sweep behind the cited date (scaleX, 250 ms), animated check (stroke draw, 250 ms), underline draw on text links (180 ms), 1 px lift on buttons and a 3 px arrow nudge (120 to 180 ms).
- Hero loop, one run of 8.55 s then rest (all 180 to 250 ms beats, `--ease`, opacity and transform only): FIR card slides in 0.4 s, remand order 0.75 s, dossier rows 2.1 / 2.4 / 2.7 / 3.0 s, source highlight sweeps over the quoted arrest date 3.4 s, "Needs your check" resolves to "Confirmed by you" 5.3 to 5.45 s, draft sentences 6.2 and 6.7 s with numbered sources, source list 7.2 s, status strip reads "Reading the papers", "Checking each fact against its source", "Drafting the application", then "Approved for export" with a drawn check at 8.3 s. Replay is a quiet text button that remounts the panel. The run pauses while the tab is hidden. With reduced motion (system or in-app) all animation is removed, the final frame shows, and Replay is hidden.
- Loops: skeleton opacity pulse and the small glyph that breathes beside a running agent (1.2 s), nothing else.
- Transform and opacity only. `prefers-reduced-motion` and the in-app "Reduce motion" setting collapse every duration to near zero.

## Components

`components/ui`: Button, Card, Badge, Tabs, Dialog, Tooltip, Input, Textarea, Skeleton, ScrollArea, Separator, plus Toast, DropdownMenu, Breadcrumb, EmptyState, Stepper (list, indicator, step).
`components/shell`: AppShell, Sidebar, MobileDrawer, TopBar (with ModeChip and help menu), CommandPalette, ShellProvider (palette, new-case, drawer, collapsed state, Ctrl/Cmd+K), `meta.ts` (case title and stage published to the top bar), `nav.ts` (single list of destinations).
`components/common`: Logo (mark, mark only, reversed), PageHeader, StatusBadge (icon and word, no pill), SourceChip, AgentGlyph.
`components/agents/AgentSignature`: a quiet one-line status with a small glyph that breathes while the agent runs.
`components/landing`: LandingPage, WorkspacePreview (static, composed from the real status component), Reveal.

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
- No State Emblem, flag, court logos or gavel.

Do instead: plain, specific, short copy a lawyer would write (Cases, New case, Review facts, Draft, Export); type hierarchy and spacing for structure; tabular numerals for dates and counts; one accent colour, for actions.

## Known follow-ups for later tasks

The workspace panes, tabs, chat and gate modal were not redesigned here. They inherit the new tokens, radius and flat shadow, but still contain older habits to clean up: numbered circles in the hearing-prep card, "Part"-style labels in a few headings, `font-display text-maroon` headings, bordered chips for some tags, and the Sutradhar status line wrapping beside its buttons in the chat header.
