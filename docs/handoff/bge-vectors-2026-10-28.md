# Opt-in BGE-M3 side vectors for the vector stores (2026-10-28)

Why: the design review (`design-review-2026-10-27.md`) found that the shared stores were built with the hashed n-gram embedder while the report says BM25 + BGE-M3. Owner decision (Option A): keep the stores and the default exactly as they are, and add a separate, opt-in BGE-M3 vector set.

## What it is
- One side file per vector store, next to it: `data/stores/caselaw/reasoning.bge.sqlite`, `caselaw/similar.bge.sqlite`, `advocacy/arguments.bge.sqlite`, `advocacy/objections.bge.sqlite`. Tables `vectors (id INTEGER PRIMARY KEY, vec BLOB)` (fp16, 1024 values) and `meta` (`embedder=bge-m3`, `model_id`, `model_revision`, `max_length=512`, `pooling=cls`, `text_sha256` of the exported corpus, `store_rows`, `store_embedder`, `job_id`). The main sqlite files are never written.
- Switch: `VS_STORES=bge` (environment only; never inferred from torch being installed). Unset, nothing reads the side files and every result is byte-identical (tested). Set, `ReasoningStore`, `ArgumentStore`, `ObjectionStore` and `SimilarStore` open their `HybridIndex` with `side_vectors="bge"`: BM25, filters, payloads and fusion come from the main file, the dense ranking from the side vectors (fp16 widened to float32 at load, cached per process), and queries are embedded with BGE-M3 from `models/hf/BAAI--bge-m3` with the same 512-token limit as the documents. `case.docs` (client files) never uses side vectors.
- Failures are loud: no side file, a side file whose row count or ids do not match the store, a wrong `embedder` in its meta, missing weights or missing sentence-transformers raise `SideVectorsError` with the fix (build with `bge_vectors apply`, `BGE=1 make data`, `make models`, or unset VS_STORES). Writing to a store opened this way is refused. The existing rule in `HybridIndex._resolve_embedder` (an index keeps the embedder that built it) is unchanged.
- Manifest: `driver.write_run_manifest` adds `store_embedder` (`hashed-ngram` by default, `bge-m3` with the opt-in) and `store_vectors` (mode, and per store the side file's revision, rows and text hash). `docs/evaluation-plan.md` (2.2 and under Table 2) says B2, B3, Table 2 and the retrieval metrics are reported under both embedders, never pooled.
- Memory with the opt-in: about 1.65 GB of float32 for the four matrices (reasoning alone 0.66 GB).

## Tooling: `src/vakeel_sahayak/pipelines/store_builders/bge_vectors.py`
1. `export` (laptop, done): the exact embedded text per row, id order, `data/bge_work/texts/<store>.texts.jsonl.gz` plus `texts_manifest.json`. Paragraph stores: `ParagraphRecord.text` from the payload. `caselaw.similar`: the FTS table is contentless and the payload has no facts text, so `orders.jsonl` is re-normalised and re-split exactly as `corpus._process_order` does and `parts[FACTS]` is taken per doc_id. Proof: 500 seeded rows per store re-embedded with the hashed embedder reproduce the stored blobs byte for byte: 500/500 for all four stores. Timings: reasoning 5 s, similar 210 s (re-splitting 116K orders), arguments 2 s, objections 2 s. Sizes: 22.9, 37.4, 10.2, 6.5 MB (77 MB in all). Rows: 161,708 / 114,692 / 70,880 / 55,161.
2. `embed` (Ada GPU node): transformers AutoModel, CLS pooling, L2 norm, fp16, length-sorted batches (16,384 tokens per batch), max_length 512; shards of 20,000 rows (`<store>.<k>.npy` fp16, `.ids.npy`, `.json` with sha256 as the completion marker); resumable (skips shards in `~/vs_bge/received.txt`). Before the first shard it compares 32 texts against sentence-transformers on CPU and stops below cosine 0.999. Imports only stdlib at module level, so the single file runs on the node without the package. A CPU dry run on the laptop (45 rows, 3 shards) gave min cosine 0.99999 against sentence-transformers.
3. `apply` (laptop): checks shard sha256 and contiguity, that the ids equal the store ids, norms in [0.99, 1.01]; writes the side file (temp name, then rename); self-rank check on 200 seeded rows (own text as the query, embedded with the local BGE-M3 on CPU at 512 tokens, must rank itself first; an identical-text duplicate ranking first is counted apart; more than 2 failures stops); a wiring check through `HybridIndex(side_vectors="bge")`; writes `data/stores/BGE_MANIFEST.json`. `--delete-shards` removes each store's shards once its side file is checked.

## Ada job
- Scripts: `scripts/ada/stage_bge_m3.sh` (copies only the texts, `bge_vectors.py` and the sbatch file to `~/vs_bge`; never `.env` or keys), `scripts/ada/embed_bge_m3.sbatch` (1 x 2080 Ti, `-A research --qos=medium -p u22 --constraint=2080ti -N 1 -n 1 -c 4 --mem=12G --gres=gpu:1 -x gnode069 --time=03:00:00`; venv, pip cache, temp files and weights on `/scratch/$USER/vs_bge_<job>`, removed by a trap; torch from the cu128 index; transformers 5.20.2 and sentence-transformers 6.2.0 as on the laptop; weights from the public BAAI/bge-m3 repo at revision `5617a9f61b028005a4858fdac845db406aefb181` (the revision of our `models/hf` copy), LFS sha256 checked, no token), `scripts/ada/pull_bge_shards.sh <job>` (laptop loop: scp each finished shard, check sha256, delete it on Ada and add it to `received.txt`; the job waits while the outbox holds 4 shards, about 160 MB, because /home2 has about 670 MB free).
- Submitted: job **44761** at 14:46. STATUS: see "State when I stopped" below.
- Pull loop: started with `setsid nohup bash scripts/ada/pull_bge_shards.sh 44761 > /tmp/claude-1000/bge_pull.log 2>&1 &`; it ends by itself when `EMBED_DONE.json` arrives and the outbox is empty, or when the job leaves the queue without it.

## How to check
- `ssh ada 'squeue -u $USER'`; job log `ssh ada 'tail -30 ~/vs_bge/logs/embed_44761.log'`; outbox `ssh ada 'ls ~/vs_bge/outbox; cat ~/vs_bge/received.txt'`.
- Laptop: `tail /tmp/claude-1000/bge_pull.log`, `ls data/bge_work/shards`; the loop's PID: `ps aux | grep pull_bge_shards` (stop it with `kill <pid>`, never `pkill -f`).
- Expected shards: reasoning 9, similar 6, arguments 4, objections 3 (22 in all, about 0.82 GB).

## How to continue
1. If the job died: read its log, fix, `bash scripts/ada/stage_bge_m3.sh` only if the texts or the script changed, `ssh ada 'sbatch ~/vs_bge/embed_bge_m3.sbatch'` (it resumes from `received.txt`), and restart the pull loop with the new job id.
2. When the pull loop says finished: `df -h /home` (the side files need about 0.85 GB), then
   `.venv/bin/python -m vakeel_sahayak.pipelines.store_builders.bge_vectors apply --delete-shards` (about 5 to 10 minutes; the self-rank check embeds 800 texts on CPU).
3. Check: `VS_STORES=bge .venv/bin/python -c "from vakeel_sahayak.stores.caselaw_reasoning import ReasoningStore as S; s=S(); s.open(); print(s._index.store_embedder, s._search('parity with co-accused', None, None, '2026-01-01', None, None, None, 3))"`, and `.venv/bin/pytest tests/unit/stores tests/unit/pipelines -q`.
4. Clean up on Ada: `ssh ada 'rm -rf ~/vs_bge/outbox ~/vs_bge/texts'` (keep the logs if wanted). Laptop: `rm -rf data/bge_work/shards` once `apply` passed (`data/bge_work/texts`, 77 MB, can stay or go).
5. Bundle: `make data-bundle` now ships the side files as `bge.tar.part-*` (never inside the data archive); teammates install them with `BGE=1 make data` or `scripts/data_install.sh --only-bge hf:...`. Nothing was uploaded; `make data-publish` is the owner's step.
6. Evaluation: run the retrieval-only rows, B2 and B3 once with `VS_STORES` unset and once with `VS_STORES=bge`; the manifest's `store_embedder` separates them.

## Not done
- No literature-to-code-map row: this is a store option, not a Switches variant.
- `scripts/_data_check.py` does not list the side files (they are optional).

## State when I stopped
- Job 44761: PENDING (`QOSMaxGRESPerUser`) at 15:19: the account's 4-GPU cap is held by job 44756 (`qwen_smoke_lean`, 4 GPUs on gnode058, started 14:41, time limit 4 h, not part of this work). 44761 starts by itself when 44756 ends; expected run time about 1 hour (10 to 15 minutes of install and download, then about 400K texts).
- Pull loop: running (log `/tmp/claude-1000/bge_pull.log`). If the laptop rebooted, restart it: `setsid nohup bash scripts/ada/pull_bge_shards.sh 44761 > /tmp/claude-1000/bge_pull.log 2>&1 < /dev/null &`.
- No side file exists yet; `VS_STORES=bge` therefore fails with the "no BGE-M3 side file" message until `apply` has run.
