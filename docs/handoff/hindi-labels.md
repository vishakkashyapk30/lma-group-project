# Hindi interface labels (handoff)

Written 13 Nov 2026. Task: translate the interface strings and wire them in with `lang="hi"` (team to-do, Harshita). Done with a free model, not Sarvam: Gemma (`gemma-4-31b-it`) through the Gemini free tier and the repo's own client. The strings are public interface text, so the free tier's public-data-only rule holds, nothing is paid and the Sarvam lock was not touched. No translation was edited or reviewed by hand (`hi.meta.json` records `reviewed_by_hand: false`).

## How it works
- `frontend/lib/i18n/index.tsx`: `I18nProvider`, `useT()` (`t("English")` returns the Hindi when the language is Hindi and a translation exists, else the English), `useLang()`. The choice is saved in `localStorage` (`vs-lang`) and sets `<html lang>`. The first render is always English, so server and client agree.
- A toggle in the top bar (`data-testid="lang-toggle"`, shows `हिन्दी` / `English`).
- `frontend/lib/i18n/hi.json` is **generated**; do not edit it. `hi.meta.json` says which model made it and when.
- English text is the key. Components call `t("...")`; the central label tables (`lib/labels.ts`, `lib/status.ts`, `lib/stages.ts`, `components/shell/nav.ts`) are translated where they are rendered (stepper, status badge, sidebar, command palette).
- `StepFrame`, `StepFooter` and `GateFooter` translate their own `title`, `intro`, `hint` and `label` props, so every step's heading, intro line and footer button switch without touching each step.

## Regenerate
```bash
cd frontend && npx vite-node --config vitest.config.ts scripts/extract-ui-strings.ts   # source.en.json: tables + every t("...") + step props
cd .. && set -a; . ./.env; set +a
VS_MODELS=auto VS_GEMINI=public .venv/bin/python scripts/translate_ui_hi.py --batch 10   # only strings not yet in hi.json; --force redoes all; --limit N for a trial
```
Needs `GEMINI_API_KEY` in the untracked `.env`. The script stops cleanly on a quota error or timeout and resumes from what is saved.

## Checks
`tests/unit/i18n.test.tsx` (fallback, switch, saved choice, `<html lang>`, every string translated with its placeholders, `source.en.json` lists every `t("...")` literal); `e2e/hindi.spec.ts` (toggle in the browser, reload keeps it). Adding a `t("...")` without regenerating fails the unit test on purpose.

## Measured on the free tier
Gemma thinks on every call and the free tier allows about 16K tokens per minute, so it translated about 5 strings a minute and timed out (`ReadTimeout`) on batches of 20; batches of 10 are used. `gemini-3.1-flash-lite` (15 requests a minute, 250K tokens) is the faster fallback if Gemma keeps timing out; pass `--model gemini-3.1-flash-lite`. Do not mix the two in one table without noting it in `hi.meta.json`.

## Not done (next steps)
- **First pass only.** The shell (sidebar, top bar, command palette, drawer), the stepper, status badges, every step's title, intro and footer button, and the gate list are translated. Text inside the tabs (field labels in a row, button captions such as "Edit" and "Check", the likely-objections and rights panels, the cases list, library, desk, settings, help and about pages) is still English. To extend: wrap the string in `t("...")`, run the extractor and the translator.
- **Dynamic strings** (counts and names inside a sentence, for example "3 items above need you before you can confirm") stay English; they need a `{placeholder}` template helper.
- **Quality is unchecked** by design (no review by hand); legal terms follow the glossary in the prompt of `scripts/translate_ui_hi.py`. A lawyer reading it will find wording to improve; fix it in the glossary and regenerate, not in `hi.json`.
- **The case's own text** (facts, grounds, quotes) is not translated: only the interface.
