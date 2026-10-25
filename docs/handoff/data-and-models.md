# Data and models handoff (2026-10-24)

## Background jobs
- Full store build (started 18:26 local, hashed-ngram embedder, stores: concordance citations reasoning arguments objections similar; statutes is rebuilt separately after the statutes gap).
  - Log: /tmp/claude-1000/-home-vishak-IIITH-IV-I-lma-lma-group-project/08aeab79-2d73-4020-bf77-919d9359b8b0/scratchpad/store_build.log
  - Check: `ps aux | grep build_all`; `tail /tmp/claude-1000/-home-vishak-IIITH-IV-I-lma-lma-group-project/08aeab79-2d73-4020-bf77-919d9359b8b0/scratchpad/store_build.log`; done when data/stores/build_report.json exists.
  - Command used: `EMBEDDER=hashed-ngram setsid nohup scripts/build_stores.sh --only concordance citations reasoning arguments objections similar`
  - TODO after finish: build statutes (`scripts/build_stores.sh --only statutes` would overwrite build_report.json, so call build_statutes directly) and write data/stores/MANIFEST.json.
- Kathbath remainder: DONE (3130 utterances).

## Update (restart)
- The first build (PID 103563) was stuck in fuzzy case-name citation resolution (scores every title per name). Killed. Fix: pipelines/store_builders/fast_index.py (word-blocked, memoised resolver; test tests/unit/pipelines/test_fast_index.py) and progress logging in corpus.py. Rebuild started 23:55 IST, log /tmp/claude-1000/-home-vishak-IIITH-IV-I-lma-lma-group-project/08aeab79-2d73-4020-bf77-919d9359b8b0/scratchpad/store_build.log (progress lines every 5000 orders).
- T1 models DONE: BGE-M3 2.31 GB, DeBERTa NLI 0.88 GB, MiniCheck-RoBERTa-Large 1.42 GB in models/hf, models/MANIFEST.json (SHA-256 verified). `make models-dry-run` works.
- Statutes: all Indian government hosts timed out or refused from this network; manual steps are in data/README.md.

## Items
1. Statutes gap: BLOCKED on data, wiring DONE (StatuteStore.build merges <data>/gaps/statutes/*.jsonl; test tests/unit/stores/test_statutes_gap_rows.py). indiacode.nic.in returns 403 (Akamai) to curl and WebFetch, legislative.gov.in direct PDFs 404, mha.gov.in 404. Team must download the CrPC 1973 PDF and NDPS Act PDF in a browser from indiacode.nic.in (handle 123456789/15247, Act ID 197402) and put them in data/gaps/raw/.
2. Kathbath remainder: DONE, 3130/3130.
3. e-SCR/SUVAS: not attempted, no permitted bulk path found (see data/README.md).
4. HLDC: HF_TOKEN not set and no ~/.cache/huggingface/token, so blocked; team must request access to Exploration-Lab/IL-TUR on Hugging Face and run huggingface-cli login.
5. Model script: DONE (scripts/download_models.sh, scripts/_download_models.py, configs/models.yaml weights:, make models/models-dry-run, DOCKER.md). T1 download (BGE-M3, DeBERTa NLI, MiniCheck; no Whisper) running, log in scratchpad models.log, result in models/MANIFEST.json.
6. NOTICE: DONE (NOTICE at repo root; entries marked to verify need a licence check).
7. Full store build: DONE (see Final state).
8. data/README.md and raw/MANIFEST.json: DONE.

## Final state (2026-10-25)
- Full store build DONE in about 35 min (log in scratchpad store_build.log). Rows: concordance 554, citations 3,492 (plan 100-300K: low, citation resolution rate 0.19; Supreme Court metadata wiring deferred), reasoning 161,247, arguments 70,691 (plan 100K), objections 55,024 (plan 80K), similar 114,544, statutes 1,411. 612 orders excluded, 115,376 used. data/stores/MANIFEST.json written (1.76 GB).
- Tests: 690 passed (pipelines, stores, tools_law_case, config); ruff clean.
- Open: statutes gap (manual download), HLDC access, e-SCR permission.

## Update 2026-10-26: full rebuild, swap, team bundle
- **Full store rebuild** into `data/stores_candidate` (all seven stores, current `splits.json`, SC metadata, name-linked SCC), `EMBEDDER=hashed-ngram`, started 00:35, finished 01:08 to 01:10 IST (about 35 min, log in the session scratch `/tmp/claude-1000/run/stores_full_build.log`). Rows: concordance 554, citations 5,842 (was 3,492), reasoning 161,708 (161,247), arguments 70,880 (70,691), objections 55,161 (55,024), similar 114,692 (114,544), statutes 1,411. 115,524 orders used, 464 excluded. Citation resolution rate 37.3% (was 19.3%; SCC occurrences 1,394 of 8,244 now resolve through the case name, but that adds only 32 edges, see `citation-sc-metadata.md`). Check: none of the 464 excluded orders is in reasoning, similar, arguments or objections (the old stores held 228 of them in reasoning). Tests: stores and pipelines 585 passed.
- **Swap done**: `data/stores` is the new build; the old one is `data/stores_prev` (1.7 GB). `make smoke` printed SMOKE OK. `data/stores_prev` was NOT deleted: the disk is at 96 to 97% (not below 90%). Delete it with `rm -rf data/stores_prev` when you are satisfied, or move it elsewhere. Two API processes (uvicorn on port 8000) were running during the swap; restart them so they open the new stores.
- **Statutes hosts retried (once)**: reachable now but moved, see data/README.md (India Code is `indiacode.gov.in`, DSpace REST API at `/server/api`). Nothing fetched; the CrPC and NDPS rows are still missing. HLDC is gated and needs a person (request access to Exploration-Lab/IL-TUR, `hf auth login`).
- **Team data bundle**: `make data-bundle` (`scripts/data_bundle.sh`, helpers `scripts/_data_bundle.py`) wrote `~/vakeel-data-bundle` (one 979 MB part, `SHA256SUMS`, `bundle_manifest.json`, `MODELS.txt` listing names and sizes only, `README.md` = dataset card with attributions, HLDC noted as not included). `make data-install SRC=<dir | URL | hf:repo> [FORCE=1]` (`scripts/data_install.sh`) verifies the checksums, refuses to overwrite without FORCE, unpacks and checks row and file counts; tested on a scratch folder: checksums ok, sanity ok, 2.9 GB unpacked. `make data-publish` (`scripts/data_publish.sh`) uploads the folder to the private dataset `vishakkashyapk/vakeel-sahayak-data` with `hf upload` (token from the environment or untracked `.env`, never printed). NOT run. The hf: path of the installer was not run end to end (no download was made). Documented in data/README.md and AGENTS.md. The bundle holds stores built 2026-10-26; rebuild the bundle after any later store change.
