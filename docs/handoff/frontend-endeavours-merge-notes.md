# Merge notes: frontend-endeavours and SA-06 (feat/frontend-flow)

Satvik's `feat/frontend-flow` was not pushed when this branch was built, so the overlap below is from what this branch touches, not a diff against his. The workspace data flow (`lib/workspace/*`, `lib/api.ts`, `lib/mock/server.ts`, every API call) is unchanged here; workspace changes are presentation only.

## Files most likely to conflict (both branches probably touch them)
| File | What this branch changed | Advice |
|---|---|---|
| `components/workspace/tabs/DossierTab.tsx` | Gate 1 footer now `<GateFooter gate="GATE_1_DOSSIER" ...>`; removed the local `blocked` and the `plural` import | Keep his flow; replace his StepFooter for the unconfirmed state with GateFooter (same test id `confirm-facts-button`, same `onApprove` opening GateModal). |
| `components/workspace/tabs/ExportTab.tsx` | Gate 2 footer is `<GateFooter gate="GATE_2_EXPORT" ...>` | Same as above (`approve-export-button`). |
| `components/workspace/tabs/RightsTab.tsx` | "On the calendar" section (RightsTimeline) before "Worth checking now" | Additive block; reads `data.rights`, `data.dossier`, `data.dates` only. |
| `components/workspace/StepFrame.tsx` | StepFooter: `control` and `above` props, `data-step-footer`, stronger top edge, safe-area padding | Additive props. |
| `components/workspace/SidePanel.tsx` | Drag-to-close, sheet rises from the bottom, header is the handle (`panel-handle`) | If he changed the panel's markup, keep his content and re-add `panelRef`, `handleRef` and `useDragToClose`. |
| `components/workspace/TraceDrawer.tsx` | Drag-to-close; `ref` on Content; header ref and `panel-handle` | Small, mechanical. |
| `components/workspace/StepView.tsx` | Keyed wrapper with `data-step-enter` for the step slide | Wrap whatever his StepView returns. |
| `components/workspace/WorkspaceShell.tsx` | One class (`scroll-pb-24`) on `pane-main` | Trivial. |
| `components/workspace/WorkspaceShellLazy.tsx` | Skeleton markup | Take this branch's skeleton. |
| `components/shell/meta.ts`, `TopBar.tsx` | `primeCaseMeta`, `writeLastCase`; breadcrumb uses meta only for the same case id; crumb `share` name | Additive. |
| `components/cases/CaseCard.tsx`, `CauseList.tsx` | Step n of 6, step names, title prime and morph | If he reworked the card, keep `onClick` (prime + startMorph) and the `data-title` span. |
| `components/shell/Sidebar.tsx`, `MobileDrawer.tsx`, `CommandPalette.tsx`, `AppShell.tsx` | Logo to `/`, `markRouteFocus`, `useRouteFocus`, PageTransition around `main`'s children | Additive. |
| `components/ui/button.tsx`, `tabs.tsx`, `breadcrumb.tsx` | `.press`; sliding tab bar; MorphTarget in the last crumb | Shared primitives: take this branch's versions. |
| `e2e/testids.ts`, `e2e/landing.spec.ts`, `e2e/a11y.spec.ts`, `e2e/reduced-motion.spec.ts` | Landing contract, RECONCILED notes, tests added | If his flow specs click a gate while it is held, use `{ force: true }` or resolve first: held gates are `aria-disabled` (Playwright's `toBeDisabled` still passes). |
| `next.config.mjs`, `playwright.config.ts` | `experimental.viewTransition`, `distDir` from `NEXT_DIST_DIR`; `E2E_PORT` | Additive. |

## Behaviour he should know about
- Gate buttons are no longer `disabled` while items are open; they are `aria-disabled`, pressable, and open the hold list instead of the dialog. Any code that relied on a native `disabled` attribute must check `aria-disabled` or `data-held`.
- The phone source sheet now enters from the bottom (`animate-slide-in-up`) and has `data-panel-mode="sheet"`.
- After sidebar or palette navigation focus goes to the page `h1`; the workspace's `h1` is `sr-only`.
- New dependency: `motion` (14.6). Import `m` from `motion/react-m` and wrap in `MotionProvider` (keeps the library out of first load).

## Order to merge
Merge SA-06 first (it owns the case flow), then rebase this branch on it and resolve the table above, then run the full Playwright suite once with `E2E_PORT` set.
