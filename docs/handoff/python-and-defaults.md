# Python 3.11 minimum and the offline default

## Done
- **Python minimum is 3.11.** Reason: fixture and record timestamps ending in `Z` fail `datetime.fromisoformat` before 3.11 (about 40 API and record tests errored on 3.10). Changed: `pyproject.toml` (`requires-python`, ruff `target-version` py311, mypy 3.11), `scripts/setup_dev.sh` (minimum, candidate order 3.13, 3.12, 3.11, python3, python; messages), `Makefile` help, `README.md`, `AGENTS.md`, and the two message assertions in `tests/unit/scripts/test_fresh_clone.py` (RECONCILED: minimum moved to 3.11). The Docker image already uses 3.12. There is no CI config in `.github` (only the PR template).
- Ruff rules `UP017` and `UP042` are ignored in `pyproject.toml`: the py311 target would otherwise flag existing `timezone.utc` and `(str, Enum)` code (`StrEnum` changes `str()`). Nothing else changed in lint counts.
- **Tolerant timestamps.** `schemas/ids.py: parse_iso_datetime` accepts a trailing `Z`; used by `check_iso_datetime`, the JSON-schema `date-time` check (`models/json_schema.py`) and the rights rule `production_24h`. Someone who already has a 3.10 venv no longer trips over `Z` in those paths; other `fromisoformat` calls parse plain dates only. Still, 3.10 is unsupported: delete `.venv` and run `make setup`.
- **`models_mode()` defaults to `offline`** when `VS_MODELS` is unset (before: `auto`). Order: environment, then a top-level `mode` in `configs/models.yaml` (there is none today), then `offline`. `auto` and `real` still work when set explicitly. `.env` is still never read by the code, so the documented default is now true on a fresh clone.
- The ad-hoc `os.environ.get("VS_MODELS", "auto")` checks (`factory._pick`, `_sarvam_active`, `_openai_active`, `models/labeler.py`, `models/teacher.py`) now call `models_mode()`, so a configs/models.yaml `mode` is honoured everywhere.
- `VS_LLM_BACKEND` unset still returns `None` (each role follows its yaml runtime), but with `VS_MODELS=offline` every LLM role is the offline client anyway.
- `scripts/live_smoke.py` sets `VS_MODELS=auto` unless the environment already sets it. Driver smoke commands already set offline; hosted commands in `docs/handoff/pilot-hosted-model.md` and `eval-jobs.md` already export `VS_MODELS=auto`.

## Behaviour someone could trip over
- Anything that relied on an unset `VS_MODELS` meaning `auto` (real DeBERTa NLI, Sarvam/OpenAI clients, heavy OCR/vision/ASR clients) now needs `VS_MODELS=auto` exported. `/healthz` reports `models: offline` by default.
- `VS_MODELS` is also the tier for `make models` (`OFFLINE` maps to T0); unchanged.

## Not done
- Python 3.10 and `Z` timestamps in test fixtures read with a raw `datetime.fromisoformat` inside tests (e.g. `tests/unit/record/test_event_log.py` already replaces `Z`).

## Checked
- `tests/unit/{models,agents,eval,scripts,orchestration}` (without `eval/test_metrics.py`, `eval/test_stats.py`): 1,387 passed, 21 failed on the first run. 17 were tests that relied on an unset `VS_MODELS` meaning `auto` (`models/test_factory.py`, `test_openai.py`, `test_sarvam.py`): their fixtures now set `VS_MODELS=auto` (`# RECONCILED`), and these three files then pass (157 passed with `test_fresh_clone.py`). Remaining known failures not from this change: 3 in `eval/test_ingestion_pipelines.py` (stubs), and `test_fresh_clone.py::test_no_stale_dataset_repo_id_in_the_tree` (a stale repo id in `docs/handoff/fresh-clone-fixes.md`, untouched here).
- `make smoke`: SMOKE OK.
