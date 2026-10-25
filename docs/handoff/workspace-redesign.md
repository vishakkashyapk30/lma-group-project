# Workspace redesign handoff

## Done
- One step at a time: stepper (Add documents, Review facts, Check rights, Draft grounds, Prepare for the hearing, Export); Likely objections sit inside Draft grounds (stage id SPAR kept, folded via stepOf in lib/stages.ts).
- "Needs your attention" list opens each step (lib/workspace/needs.ts, components/workspace/NeedsYou.tsx), one jump button per item; one primary button per step (StepFrame/StepFooter).
- Review facts: label, value, one plain status word per row; source panel (SourcePanel) shows quote (Hindi beside English), page, route, language, conflicts, with the page viewer. List of dates is a plain timeline with a single Check action on conflicts.
- Check rights: plain list, "Why" expander, other checks collapsed.
- Draft grounds: document style, numbered footnote citations opening the panel, single "Needs check" mark, per-ground Details, objections as accordion (unanswered open).
- Prepare for the hearing and Export steps; GateModal is now the confirm dialog ("Confirm these facts" / "Approve this draft for export") listing what is locked.
- Chat is a right drawer (ChatPane in SidePanel); Details drawer = TraceDrawer + BudgetMeter + raw statuses; Documents popover; Saved note; toasts with Undo (toast.tsx gained an optional action).
- Plain-language status labels (lib/status.ts); raw enums stay in data-status and Details.
- Privacy: landing trust line, Help "Privacy" section, mode chip tooltip, About privacy rule made exactly true.
- tsc, lint and build pass.

## Not done
- DESIGN.md not yet updated (needs a "Workspace principles" section; the IA and Components lines still describe three panes and Gate buttons, and the "Known follow-ups" section is obsolete).
- Visual critique pass was only done once on desktop initial screen; mobile screenshots and the source panel, chat, details and gate dialog shots were taken but not reviewed or iterated.
- Field-edit undo is not offered (only dates, grounds, resolutions, mark-unknown) because the API cannot restore a previous status.
- CaseCard still says "Stage n of 7" (outside scope).
- Dead tokens: TONE_CLASSES.dot in lib/status.ts may be unused; check.

## Next steps
1. Review after screenshots, fix issues, rerun tsc, lint, build.
2. Write the DESIGN.md section.
3. Reconcile tests (separate task).

## Files touched
components/workspace/** (WorkspaceShell, StageRail, StepView, StepFrame, NeedsYou, ProgressLine, SidePanel, SourcePanel, Popover, DocumentsMenu, SavedNote, DocumentList, DropZone, ChatPane, GateModal, ChangeBanner, TraceDrawer, BudgetMeter, PdfViewer, PdfPages, ToolChips, tabs/*; CaseFilePane and RightPane deleted), lib/stages.ts, lib/status.ts, lib/workspace/{WorkspaceProvider,checklist,needs,conflicts,progress,index}.ts, components/ui/toast.tsx, components/shell/TopBar.tsx, components/landing/LandingPage.tsx, components/help/HelpPage.tsx, components/about/AboutPage.tsx.

## Screenshots
Before: /tmp/claude-1000/-home-vishak-IIITH-IV-I-lma-lma-group-project/08aeab79-2d73-4020-bf77-919d9359b8b0/scratchpad/workspace/before/  After: /tmp/claude-1000/-home-vishak-IIITH-IV-I-lma-lma-group-project/08aeab79-2d73-4020-bf77-919d9359b8b0/scratchpad/workspace/after/

## Old test expectations that will fail
- Stage rail labels (Intake, Dossier, Rights, Brief, Spar, Hearing prep, File) and stage-VI/stage-V (Spar has no stepper button).
- gate-diamond-1/2 (removed); gate modal copy and the export button inside it; Gate 1/Gate 2 names.
- pane-case-file (now inside the Documents popover), pane-chat/pane-right (chat is a drawer; no right tabs), right-tab-* except dossier/dates.
- show-plan-button (now details-button); draft-brief-button now lives on the Draft grounds step.
- Status labels in lib/status.ts (Verified, Computed, Unsupported, Stated by counsel, etc.).
- Dossier field cards: source quote, route and badges are no longer on the row; dossier-field-edit is visible on hover or focus only on wide screens.
- ArgumentText chips (F:field), AuthorityList, needs-review underline; spar cards are accordions.
- Route badges and per-page routes are under Reading details.
- Landing trust text; TopBar mode tooltip text; Help page now has a Privacy block.
