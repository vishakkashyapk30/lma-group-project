# Mid-submission split, 30 October 2026 (Vishak and Shravani)

Deadline: the status report is submitted today by 23:59. Target: all work done by **18:00**, worst case; the last hour before 23:59 is for the final read and the push. Harshita and Satvik are not part of today's split; their items stay "pending" in the report with their names (Rights rule verification 6 of 7 and BNSS s.58 text: Harshita; frontend merge: Satvik).

## State at about 15:30
- Code tag `dev-sweep-v3` (commit 7ad6ed4), pushed. Report and scripts are on the branch `midsub-report` (not merged to `main`; the mid-submission does not need `main`).
- Runs finished (Vishak, OpenAI gpt-6-luna hosted, and Gemini free tier hosted): Full, B0 to B4, B5, A1, A2, A3, A6, A7, A8, A9, S1 to S6, S8 to S12, S15, S18 (OpenAI); Full, B0 to B3, B0L, A1 (Gemini 3.5 flash-lite); Full, A2, A8 (Gemini 3.1 flash-lite). Offline studies S4/S5 (hashed and BGE), S14, S16 finished.
- Scoring is running on Vishak's laptop (MiniCheck on CPU, slow: about 2.5 hours for the OpenAI block). Results tables are built from the scorer's `per_case_agreed.csv` by `docs/report/tools/make_result_tables.py`.
- Not yet run on any model: A4, A5, A10, S7, S11b, S11c, S12b, S15b, S17, P5 to P8 (S13 needs the Ada GPU nodes and is dropped for today, reported as not run).
- Spend: OpenAI ledger about 4.1 of the 4.50 cap (code maximum 5.00). Paid providers stay locked. Do not ask for the OpenAI or Sarvam keys.

## Vishak (this laptop)
1. Finish scoring (OpenAI v3, Gemini block A, A7 on its own), build tables and plots, write the results text, fill every remaining `\todo` (results, abstract, appendix), final PDF, push. Report finished by 21:00, final read and push by 23:00.
2. Merge Shravani's CSVs into the tables as they arrive (cut-off 17:30).

## Shravani (her machine, her own Gemini key)
Priority order. Stop at 17:00 whatever is done; push what exists.
1. **Gemini 3.1 flash-lite arms with her own key** (public court text only): A4, A5, S11b, S11c, S12b, S15b, plus Full on the same cases (her own Full, same model, so comparisons are paired), 5 dev cases each (the first five of `data/testsets/t1/dev.jsonl`). Template: `scripts/midsub/sweep-v3-midsub-B.sh` (change the arm list and paths).
2. **Offline phase 1** (no key, CPU, about 85 s of CPU per case): A10 knock-outs, S7, S17, P5, P6, P7, P8 at 10 dev cases each, `VS_MODELS=offline` for the language model, real stores (needs `make data`, `make models`).
3. **Score her own runs** and push only the small `per_case_agreed.csv` files (see her prompt). If scoring is too slow, push the raw `t1dev-*.json` outputs instead and say so; Vishak scores them.
4. If time remains: proofread `docs/report/sections/{challenges,data,limitations,threats,ethics}.tex` against the facts in `docs/handoff/*.md`; list wrong or stale statements in a file `docs/handoff/shravani-proofread-2026-10-30.md`, do not edit those sections (Vishak is editing the report; avoid merge conflicts).

## Decisions and assumptions (do not change without asking Vishak)
- Results are compared only inside one code tag and one model family; the scorer refuses mixed code stamps. Use the tag `dev-sweep-v3` in a worktree: `git fetch --tags && git worktree add ../sweep-v3 dev-sweep-v3`, link or copy `data/` and `models/` into it.
- No manual labels, no LLM-judge scores. Gold is the agreed gold (`--gold-source agreed`). The unsupported-fact rate uses MiniCheck, never the system's own checker.
- Free tiers take public data only: dev cases are public court text, so Gemini is allowed (`VS_GEMINI=pseudonymised`); never feed client text.
- Never commit `.env`, keys, `data/`, `models/`. No AI attribution in commits or any document (the commit hook strips it; `make hooks` once).
- Gemini quota resets at 12:30 IST (Pacific day); each project key has 500 requests a day on the flash-lite models, a Full case takes about 49 requests, so at most about 10 Full-equivalent cases per key per day. Five cases per arm is the plan; cut cases, never arms.
- A crashed or privacy-refused case is saved with an `error` field and scored as an empty brief; the report also gives the comparison on the cases an arm answered, so do not rerun those.
- Report claims: "work in progress", small dev samples, intervals wide; negative or null results are written as such.
