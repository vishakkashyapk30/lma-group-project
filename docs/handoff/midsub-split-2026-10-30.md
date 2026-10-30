# Mid-submission plan, 30 October 2026 (revised 15:15): Vishak is unavailable after 17:30

The status report is due **today, 23:59 IST**. Vishak works until 17:30 and cannot do anything after. From 17:30, Shravani (with her coding agent) owns everything, including the final PDF, the push and the submission. Harshita and Satvik are not part of today's work; their items stay "pending" with their names in the report (Rights rule verification 6 of 7 and BNSS s.58 text: Harshita; frontend merge: Satvik).

## Timeline (IST)
| Time | Who | What |
|---|---|---|
| now to 17:30 | Vishak | Keep scoring, fill what can be filled, push everything, leave the unattended pusher running (below) |
| now to 17:00 | Shravani's agent | Tasks 1 to 3: her Gemini arms, offline phase 1, scoring her runs; push branch `midsub-shravani` |
| 17:30 to 19:30 | Shravani's agent | Task 5 part A: pull `midsub-report`, check the generated tables, merge her CSVs, write the results text |
| 19:30 to 21:30 | Shravani's agent | Task 5 part B: fill all `\todo`, abstract numbers, appendix arm-state table, rebuild, check layout |
| 21:30 to 23:00 | Shravani and her agent | Final read, push, submit the PDF and the GitHub link. Submit by 23:00; 23:59 is the hard limit |

## State at 15:15
- Code tag `dev-sweep-v3` (commit 7ad6ed4), pushed. Report, scripts and tools are on branch `midsub-report` (not merged to `main`; the mid-submission does not need `main`).
- Runs finished (OpenAI gpt-6-luna hosted; Gemini free tier hosted): Full, B0 to B5, A1, A2, A3, A6, A7 (28 of 30 cases when last counted), A8, A9, S1 to S6, S8 to S12, S15, S18 (OpenAI); Full, B0 to B3, B0L, A1 (Gemini 3.5 flash-lite); Full, A2, A8 (Gemini 3.1 flash-lite). Offline studies S4/S5 (hashed and BGE), S14, S16 finished.
- **Scoring runs on Vishak's laptop** (MiniCheck on CPU, slow; OpenAI block expected about 17:20, Gemini block A earlier). An unattended job (`autopush.sh`, systemd unit `vs-autopush`) waits for each scorer, scores A7 in full, builds the report tables with `docs/report/tools/make_result_tables.py` into `docs/report/generated/`, copies the small per-case CSVs into `docs/results/midsub/<block>/`, and pushes both to `midsub-report`. At the end it pushes the raw run outputs to the branch `midsub-raw` (`docs/results/raw/*.tar.gz`). If the laptop sleeps or the job dies, the tables stop updating; the last pushed state is what you have. If `docs/results/midsub/openai_v3b/` is missing at 17:30, rescore from `midsub-raw` yourself (command below) or, if that is also missing, report the OpenAI block as "run, scoring not finished" and use the 50-case v1 results.
- Not run on any model: A4, A5, A10, S7, S11b, S11c, S12b, S15b, S17, P5 to P8 (Shravani's tasks); S13 needs the Ada GPU nodes and is reported as not run.
- First scored numbers (agreed gold, dev; many cells are blank because most cases have no scorable gold, so the n in brackets matters): Full wins objection recall (1.00 on 11 cases against 0.00 for B0 to B3) and answerable coverage (0.58 on 8 cases against 0.00); Full has no fabricated citations on 20 cases and citation precision 0.77; Full is worse on unsupported-fact rate (about 0.91 against about 0.84 for B0 to B3; adverse grounds are rebuttals by design, plan 6.2, so part of this is the metric); factor recall is defined on only 2 to 8 dev cases and is not resolved. On the 50-case v1 run (older code) Full's factor recall (0.25 on 8 cases) is below B6's (0.88): report it as it is. recall@10 is undefined on dev (no G2 gold in dev); retrieval evidence comes from the offline studies S4/S5, S16, S14.
- Spend: OpenAI ledger about 4.1 of the 4.50 cap (code maximum 5.00). Paid providers stay locked; do not ask for the OpenAI or Sarvam keys. No more OpenAI runs.
- The GitHub repository `https://github.com/vishakkashyapk30/lma-group-project` is **private**. The submission asks for an updated GitHub link; decide with Vishak before 17:30 whether to add the graders as collaborators or make it public. The agent must not change repository visibility on its own.

## Shravani's tasks (her machine, her own Gemini key)
1. **Gemini 3.1 flash-lite arms with her own key** (public court text only): A4, A5, S11b, S11c, S12b, S15b plus her own Full on the same cases (so comparisons are paired), 5 dev cases each (the first five of `data/testsets/t1/dev.jsonl`). Template: `scripts/midsub/sweep-v3-midsub-B.sh`.
2. **Offline phase 1** (no key, CPU, about 85 s per case): A10, S7, S17, P5, P6, P7, P8 at 10 dev cases each, `VS_MODELS=offline`, real stores. Start these first, in the background.
3. **Score her runs** and push only the per-case CSVs to `docs/results/shravani/<block>/per_case_agreed.csv` on branch `midsub-shravani`.
4. **Task 5, the report (from 17:30).** Pull `midsub-report`. Merge `midsub-shravani` into it. Then:
   - Run `python3 docs/report/tools/make_result_tables.py docs/report/generated openai=<csv list> gemini=<csv> v1=<csv> [shravani=<csv list>]` (CSVs under `docs/results/midsub/` and `docs/results/shravani/`); it writes `main_<family>.tex`, `ablate_<family>.tex`, `fig_<family>.tex`. The results section already includes them through `\gentable{...}`.
   - Replace every `\todo{...}` in `docs/report/sections/{results,abstract,appendix}.tex` with text built from the tables (each `\todo` says what to write). Add the Shravani family as a new paragraph. In the appendix arm-state table, set each arm to run, scored or not run.
   - Update `docs/report/sections/status.tex` (work-left table) and the timeline text if anything changed. Remove "[TODO" markers only by filling them; a final `grep -n "todo{" docs/report/sections/*.tex` must be empty.
   - Build with `cd docs/report && ./build.sh`; fix any LaTeX error; check pages for large white gaps and for table or figure overflow; commit the PDF.
   - Submit: the PDF `docs/report/main.pdf` and the GitHub link.

## Decisions and assumptions (do not change without asking Vishak before 17:30)
- Results are compared only inside one code tag and one model family; the scorer refuses mixed code stamps. Use the tag `dev-sweep-v3` in a worktree: `git fetch --tags && git worktree add ../sweep-v3 dev-sweep-v3`, link or copy `data/` and `models/` into it.
- No manual labels, no LLM-judge scores. Gold is the agreed gold (`--gold-source agreed`). The unsupported-fact rate uses MiniCheck, never the system's own checker.
- Free tiers take public data only; dev cases are public court text, so Gemini is allowed (`VS_GEMINI=pseudonymised`).
- Never commit `.env`, keys, `data/`, `models/`. No AI attribution in commits or any document (the commit hook strips it; run `make hooks` once). Pushes go to branches (`midsub-report`, `midsub-shravani`), not `main`.
- Gemini quota resets at 12:30 IST; each project key has 500 requests a day on the flash-lite models; a Full case takes about 49 requests, so about 10 Full-equivalent cases per key a day. Five cases per arm is the plan; cut cases, never arms.
- A crashed or privacy-refused case is saved with an `error` field and scored as an empty brief; the tables use only cases answered without error for the paired comparisons. Do not rerun them.
- The report presents the project as work in progress: small dev samples, wide intervals, null or negative results stated plainly, and every unmeasured arm listed as not run.
- Formatting rules for the report (the owner's): ACL style, no colours in text or tables, plots may use colour (pgfplots style `vsplot`), black-and-white architecture diagram, no page limit, no demo video. The timeline in the report ends on 10 November (all work finished by then).
- Rescoring from raw outputs, if needed: `tar xzf docs/results/raw/openai_block_v3.tar.gz -C /tmp/oa` then `python -m vakeel_sahayak.eval.scoring score --runs /tmp/oa/outputs --slice dev --gold-source agreed --out /tmp/oa_scores` (needs `make data` and `make models`; slow on CPU, score the arms Full, B0 to B4 first).
