# Frontend (Next.js App Router, TypeScript)

The app is built (shell, landing, guided workspace, desk, library, settings; real-API mode with a `demo` fallback, see `lib/api.ts`). Design rules: `DESIGN.md`; history: `docs/handoff/workspace-redesign.md`. The older placeholder-skeleton wording of this file was outdated (checked 2026-10-27). Plan §13.

- Palette and fonts: `styles/tokens.css` ("Manuscript", plan §13.2).
- Routes: `/`, `/cases`, `/case/[id]`, `/desk`, `/library`, `/about`.
- All artwork is our own SVG line art in `public/art/`. No State Emblem, national flag or court logos.
- Animate only transform and opacity; honour `prefers-reduced-motion` (plan §13.7).
- `lib/types.ts` mirrors `src/vakeel_sahayak/schemas/`; keep them in sync.
