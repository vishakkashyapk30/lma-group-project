# Fresh-clone fixes (2026-10-26)

> Checked by Vishak 2026-10-27: the Python minimum is now 3.11, not 3.10+ (`python-and-defaults.md`), and the unit test count in this note (4,678 collected) is now 4,944 collected.

Walked the "First day" block of `AGENTS.md` in a fresh `git clone` (scratch folder, deleted afterwards), as a new teammate would.

## Found and fixed
1. `scripts/data_install.sh` refused a fresh clone: the clash check counted `.gitkeep` files in `data/interim`, `stores`, `testsets`, `gaps`, `eval`. Now dotfiles and `README*` are placeholders (`has_data`). The same placeholders made the post-install sanity check fail (`7 files, manifest says 6`); `scripts/_data_bundle.py` counts real files (`real()`), and `check` accepts either count so manifests of already published bundles still pass.
2. Repository id: no the old personal-namespace dataset id or other stale id is left (scripts, Makefile, docs, README, docker, configs, `.github`); a test (`test_no_stale_dataset_repo_id_in_the_tree`) keeps it that way. `BUNDLE_REPO`, `HF_REPO` defaults are `Vakeel-Sahayak/vakeel-sahayak-data`.
3. Slow or failing `hf download`: timeouts (60 s, 30 s), three tries with resume, `--max-workers 2`, visible progress, a preflight (`hf auth whoami`, then the tiny `SHA256SUMS`) before the large download, one clear message for 401, 403 and 404 (token, organisation membership, "Org permissions" read scope). `scripts/_hf_lib.sh` holds the helpers. `make data` previously ignored a login from `hf auth login` (it only looked for `HF_TOKEN`); fixed. Empty `HF_TOKEN=` lines (as in a copied `.env.example`) count as unset. Knobs: `HF_TRIES`, `HF_MAX_WORKERS`, `HF_HUB_*_TIMEOUT`, `TMPDIR`, `VS_DOWNLOAD_DIR`.
4. `make setup` was a stub (`TODO`, exit 1). Now `scripts/setup_dev.sh`: Python 3.10+ (tries 3.12, 3.11, 3.10, python3; skips an interpreter whose `venv` has no pip, as one here did), upgrades pip, `pip install -e '.[dev,data,testsets]'`, copies `.env.example` to `.env`, then `make hooks`. `make setup-full` or `EXTRAS=...` for heavy extras. The `hf` command was not installed by anything; `huggingface_hub` is now in the `data` extra. Tested in a fresh clone: 6 minutes on a slow link, `.venv` 604 MB, `pytest tests/unit/scripts` 10 passed (now 28 with the new file), `make test-collect` 4,678 collected, `make smoke` OK, with no data.
5. Makefile: Python targets without `.venv` died with `No such file` or a stack trace; they now stop with "run make setup" (`needs-venv`). Added `make help`. `make api` and `make frontend` were stubs; now they start uvicorn and `npm run dev` (with `npm ci` when `node_modules` is missing). `test-frontend` and `test-e2e` check `node_modules`. `make hooks` explains a non-git checkout and a missing perl.
6. `.env.example`: existed; added the missing variable names the code reads (commented, so a copy never sets an empty value that overrides a default) and the data-script knobs. `.env` is gitignored (tested). The test checks no `*KEY`/`*TOKEN` variable has a value.
7. `scripts/data_publish.sh` and the installer used `"${arr[@]}"` on possibly empty arrays (fails on bash 3.2, macOS); fixed.
8. README "Getting started (skeleton)" said nothing runs and used `npm install`; replaced by the real quick start (`npm ci`, Node 20 as in the Docker image).

## Checked, nothing to fix
- `docker compose config -q` passes. Scripts all have the exec bit (tested). No `/home/vishak` or `/tmp/claude` path in `scripts`, `src`, `configs`, `docker`, `tests`, Makefile or compose (tested; only handoff notes mention scratch paths). `~/vakeel-data-bundle` is only the owner-side default of `make data-bundle` and `make data-publish` (overridable with `BUNDLE`/`BUNDLE_DIR`).
- `make data` without a token and with a bad token: clear messages (real `hf` 2.3 was used for the bad token). `make data-check` on a fresh clone prints "nothing is installed yet: run make data". `make models-dry-run`, `make eval-plan`, `make openai-spend`, `make smoke` work without data. `make eval-smoke` needs `data/testsets/t1/dev.jsonl` and says so.

## Left (needs the owner or a machine with access)
- The real `hf:` download was not run (no token with organisation access in this session); the retry, resume, preflight and error paths are tested with a stub `hf` command. First teammate to run `make data` should report the result here.
- `huggingface_hub` 2.x was installed by pip; the scripts use only `hf download`, `hf auth whoami`, `--max-workers`, `--exclude`, `--local-dir`, which exist in 0.36 and 2.3. The `data` extra pins `>=0.34`.
- `make lint` is still a stub (`ruff check` reports existing findings, e.g. `scripts/live_smoke.py` E702). Decide whether to clean those up and wire `make lint`.
- `make frontend` and the vitest/e2e tests were not run here (no Node install in the scratch clone); `frontend/tests` and `frontend/e2e` still describe the earlier design (known).
- `.env.example` sets `VS_LOCAL_LLM_DEVICE=cuda:0` and `NEXT_PUBLIC_API_BASE_URL` plus `NEXT_PUBLIC_API_BASE`: harmless offline, but the owner may want to tidy the duplicate names.
- `pyproject.toml` ruff `target-version` is py310 and the code was developed on 3.12/3.13; Python 3.10 and 3.11 were not tried.
- `pip install` of the `eval` extra pulls `minicheck`, which may bring torch: use `make setup-full` only where disk allows (not tried).
