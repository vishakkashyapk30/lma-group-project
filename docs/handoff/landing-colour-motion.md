# Landing colour and motion

Done: secondary palette (saffron, indigo, neem tokens plus tints, contrast pairs in frontend/DESIGN.md), band layout, hero product loop (8.55 s, runs once, Replay, pauses when hidden, static final frame under reduced motion), staggered scroll reveal, highlight sweep, animated checks, link underline draw, button lift.

Files: frontend/styles/tokens.css, frontend/tailwind.config.ts, frontend/styles/landing.css, frontend/components/landing/{LandingPage,HeroLoop,Reveal}.tsx (WorkspacePreview.tsx removed), frontend/DESIGN.md.

Screenshots: /tmp/claude-1000/-home-vishak-IIITH-IV-I-lma-lma-group-project/08aeab79-2d73-4020-bf77-919d9359b8b0/scratchpad/landing/{before,after}/ (full-page at 360 to 1920 before; 1440 and 390 after; f00..f25 are loop frames every 400 ms).

Not done / next: old e2e and unit tests still reference the earlier landing (testids.ts); a later task updates them. Landing keeps data-testid "site-footer" and "open-case-button". Judge by eye: saffron offset block behind the hero loop, jaali opacity.
