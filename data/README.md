# data/

Everything here except this README and the `.gitkeep` files is gitignored.

| Dir | Contents | Plan |
|---|---|---|
| `raw/` | Open India Law bail subset and statutes, IPC2BNS-Verify, Kathbath Hindi test subset (HLDC and e-SCR Hindi: see below), `MANIFEST.json`. Public data only. | §2 |
| `interim/` | `orders.jsonl`, `statutes.jsonl`, `concordance_edges.jsonl`, `splits.json`, `feasibility_report.{json,md}`, `ingest_report.json`; later split orders (facts / defense / prosecution / reasoning / operative), gold labels G1-G7, teacher dossiers, SFT data. | §5.2, §12, §15.1 |
| `stores/` | The seven shared stores (SQLite, LanceDB, networkx files). | §5 |
| `testsets/` | Constructed test sets T1-T9. | §15.2 |
| `cases/` | Per-case private data (laptop only): uploaded files, `case.docs`, `case.timeline`, `case.facts`, event log. | §3.3, §16 |

Rule: raw client files never leave the laptop. Only pseudonymised text may be copied to Ada. No manual annotation: every label comes from court text, official tables, existing datasets, construction or non-Qwen labeler consensus.

## Get the data from the team bundle (fastest)

The owner shares a compressed, checksummed copy of everything that is slow to rebuild (`interim`, `stores`, `testsets`, `gaps`, `eval`, `raw/MANIFEST.json`;
about 1.5 to 2 GB; also `interim/hindi_native.jsonl`, the Kathbath transcripts and audio index, and `bundle_manifest.json`). It is a PRIVATE Hugging Face dataset, `Vakeel-Sahayak/vakeel-sahayak-data`
(https://huggingface.co/datasets/Vakeel-Sahayak/vakeel-sahayak-data); ask the owner for read access, then log in once with `hf auth login` or put
`HF_TOKEN=...` in the untracked `.env`, and from the repository root:

```bash
make data                                                       # all in one: skip if `make data-check` passes, else install with an HF token, else explain
make data-check                                                 # present/missing table; non-zero when required items are missing (REQUIRE_MODELS=1 also requires the T1 models)
make data-install SRC=hf:Vakeel-Sahayak/vakeel-sahayak-data     # or SRC=<a folder or URL the owner gave you>
make data-install SRC=~/vakeel-data-bundle FORCE=1             # FORCE=1 overwrites what is already in data/
```

It verifies `SHA256SUMS`, refuses to overwrite `data/` without `FORCE=1`, unpacks, and checks row and file counts against `bundle_manifest.json`.
Kathbath audio (3.6 GB) is not bundled: refetch with `python -m vakeel_sahayak.pipelines.kathbath_fetch --out data/raw/kathbath --limit 3130` (or `make datasets`). Not in the bundle: model weights (`MODELS.txt` lists names and sizes; `make models`), `data/cases` (private client files), `data/openai`, `data/raw` (except
`MANIFEST.json` and the Kathbath transcripts) and HLDC. Owner side: `make data-bundle` (writes `~/vakeel-data-bundle`, no upload) and `make data-publish` (uploads it with `hf upload`; token
from the environment or `.env`, never printed). If you have no access, rebuild with the commands below.

## Reproduce the data (week 0)

```bash
pip install -e '.[data]'          # pyarrow, requests
make datasets                     # scripts/download_datasets.sh: raw files + data/raw/MANIFEST.json (resumable; 1-3 h on a 5 MB/s link)
make interim                      # scripts/build_interim.sh: orders.jsonl, statutes.jsonl, concordance_edges.jsonl, splits, feasibility report
SAMPLE=2000 make stores           # prove the store build on 2,000 court-balanced orders (data/stores_sample, about 1 minute)
make stores                       # all orders in data/interim/orders.jsonl
```

`OIL_COURTS="delhi sikkim" make datasets` fetches a subset of High Courts (a pilot). `data/interim/orders.jsonl` is the input marker the Docker `data`
profile checks. Provenance, licence, revision, size and SHA-256 of every raw file are in `data/raw/MANIFEST.json`; counts and the week-0 verdict are in
`data/interim/feasibility_report.md`.

## Dataset versions and status

| # | Dataset | Revision | Licence | In `data/raw/` | Notes |
|---|---|---|---|---|---|
| 1 | Open India Law (Vaquill AI) | release `v2026.08.1` (HF repo sha `58ea6d8b6859f8039ee68dff5af636f787b02463`) | CC BY 4.0 (compilation; the judgments and statutes are Government works) | `open_india_law/` | Judgment files (26, 53.6 GB, 32.6M chunks) are streamed from the mirror named in the dataset README (`https://oss-data-in.vaquill.ai`, no login) and only the chunks of bail-candidate cases are kept: High Courts, decisions 2019-2025; Supreme Court, 4+ mentions of bail. The legislation file is downloaded whole and checked against the published SHA-256. The Hugging Face repo itself is gated (login and accept terms). Judgment files carry no per-file SHA-256 in the release (only multipart ETags). Attribution: "Structured Indian primary-law data from the Open India Law corpus by Vaquill AI (https://github.com/Vaquill-AI/open-india-law), used under CC BY 4.0." |
| 2 | IPC2BNS-Verify (MS-406) | commit `8d3e77024b3693d21ccae39bffb81641329a4900` | MIT per the README badge; the repository has no LICENSE file at that commit | `ipc2bns_verify/` | `concordance_v1.csv` (563 IPC rows), section labels, the 1,140-query benchmark. Real layout: see the docstring of `pipelines/concordance/ipc2bns.py`. |
| 3 | HLDC (Kapoor et al., 2022) | not downloaded | CC BY-NC 4.0 (HLDC README); IL-TUR card: CC BY-NC-SA 4.0 | none | Released as the `bail` config (176k Hindi UP district-court documents) of the gated Hugging Face dataset `Exploration-Lab/IL-TUR` (gating mode: manual approval). A teammate must request access there. Fallback in plan §2: construct Hindi text from source 1 with NLLB-200. |
| 4 | e-SCR / SUVAS Hindi judgments | not attempted | Government publication | none | Optional; no bulk download. |
| 5 | Kathbath (AI4Bharat) | `clean/testkn_audio.tar` and `clean/transcripts_n2w.tar` on the official object store (linked from the IndicSUPERB repository) | CC0 packaging (IndicSUPERB page); Hugging Face metadata says cc-by-4.0 | `kathbath/hindi/test_known/` | The Hugging Face repo is gated and has no test split. The official test tarballs are ungated, 3.6 GB for all languages; `pipelines/kathbath_fetch.py` range-reads only the first N Hindi utterances (default 1,000; m4a) and the Hindi transcript file (tab-separated `<file>.m4a<TAB><text>`). |
| 6 | Public form layouts | none | Government forms | none | A state police site hosts the FIR form IF-1 PDF (https://police.py.gov.in/Police%20manual/Forms%20pdf/FORM%20IF%201.pdf); no national template was found for the IIF-1; no official template for the remand order or custody certificate (court-specific). |

Known gaps in Open India Law `v2026.08.1` (checked on the files): the Code of Criminal Procedure 1973 is not in the central legislation file (only the BNSS is), and
NDPS Act s.37 (among other NDPS sections) is missing, so `statutes.jsonl` has no CrPC rows and no NDPS s.37 row. UAPA s.43D and PMLA s.45 are present. The
CrPC/BNSS First Schedule (bailable, cognisable) is not in the release, so `bailable` and `cognisable` stay unset. Take CrPC and NDPS s.37 from India Code
(https://www.indiacode.nic.in/) if the Statute Store needs them.

## Week-0 result (run on 2026-10-19; details in `interim/feasibility_report.md`)

1,483,143 High Court bail orders (2019-2025, sexual-offence / POCSO / juvenile matters removed) and 662 Supreme Court judgments that discuss bail were selected
from the release; `orders.jsonl` holds a sample of 115,988 (at most 800 per court and year, 120 Supreme Court judgments per year from 1990, plus every
cleanly split dev/test-window order). 88,121 orders (5.9%) split cleanly; 56,285 are BNS-era (6,211 of them cleanly split). Both plan targets are met
(250 cleanly split dev + test orders; 94 BNS-era orders in the test set against the 60 required). Only 12.9% of orders carry a FIR number that `leakage.fir_key`
finds and 4.8% an offence date, so the same-FIR leakage rule and the BNS-era test lean on the charged sections in the text.

## Gap-filling status (2026-10-26)

* **Statutes (2026-10-26): CrPC and NDPS rows now built from official PDFs.** Retrieved 2026-10-26 (a text PDF each, no OCR needed):
  CrPC 1973 consolidated text, https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf (saved as
  `data/gaps/raw/crpc_candidate.pdf`, 261 pages), and NDPS Act 1985 from the Department of Revenue, https://dor.gov.in/files/acts_files/NDPS_1985.pdf
  ("Last Update 3-1-2022", saved as `data/gaps/raw/ndps_dor_clean.pdf`; the older `ndps_candidate.pdf` is a bad OCR scan and is not used). The
  India Code REST API (`https://indiacode.gov.in/server/api/core/items`) answers 401 without a login, so it was not used. `python scripts/extract_gap_statutes.py`
  (its docstring lists every mechanical edit) writes `data/gaps/statutes/crpc.jsonl` (s.41, 41A, 50, 57, 167, 436, 436A, 437, 438, 439),
  `ndps.jsonl` (s.19, 24, 27A, 31A, 37; `cognisable` and `bailable` read from the s.37 text) and `first_schedule_ipc.jsonl` (382 IPC rows with empty
  text that add `bailable`/`cognisable` from the CrPC First Schedule Part I to the existing IPC rows; `_merge_gap_rows` keeps the text). Rebuild
  only the statutes store in place: `.venv/bin/python -c "from vakeel_sahayak.stores.law_statutes import StatuteStore as S; S().build('data/interim', 'data/stores/law')"`.
  **Still missing:** BNS/BNSS First Schedule flags (only the CrPC schedule is parsed, so BNS rows have no bailable/cognisable), the rest of the CrPC
  sections (only the ten the bail pipeline needs), First Schedule Part II (offences under other laws, a generic three-class table, not mapped to
  sections), conditional IPC cells ("according as the offence abetted is cognizable", a few dozen sections) which stay `None`, and UAPA 43D(5) / PMLA 45 /
  BNS 318(4) statute text. The CrPC text is the consolidated Act as published in that PDF; later amendments are not tracked.
* **Kathbath Hindi test_known:** `kathbath_fetch --limit 3130` finished: 3,130 of 3,130 utterances with transcripts (about 300 MB).
* **e-SCR / SUVAS Hindi judgments: not attempted.** The translations (about 36,000 Hindi judgments) are on the e-SCR portal, but we found no
  published bulk download, reuse licence or terms page, so nothing was fetched. Ask the Supreme Court Registry / NIC for written permission,
  or use per-judgment manual downloads for a small sample. Fallback: translate with IndicTrans2/NLLB.
* **HLDC / IL-TUR `bail` config: blocked.** No Hugging Face login or `HF_TOKEN` on this machine. **Team step:** with a Hugging Face account, open
  https://huggingface.co/datasets/Exploration-Lab/IL-TUR , accept the access terms (non-commercial, CC BY-NC-SA 4.0), run `huggingface-cli login`
  (or export `HF_TOKEN`), then `load_dataset("Exploration-Lab/IL-TUR", "bail")` into `data/raw/hldc/` and update `raw/MANIFEST.json`. Until then
  the fallback in use is `data/interim/hindi_native.jsonl` (below); NLLB English to Hindi translation of constructed orders remains the second option.
* **Native Hindi fallback (2026-10-26): `data/interim/hindi_native.jsonl`.** `python -m vakeel_sahayak.pipelines.hindi_native` (about 4 minutes, reads the 1,641 raw shards one at a time) keeps
  native Hindi High Court bail orders (first chunk over 30% Devanagari, full text at least 50% Devanagari and 800 characters, no T1 dev/test/blind or `splits.json` dev/test case, deduplicated):
  6,889 orders, 62 MB (Allahabad 6,881, Rajasthan 4, "High Court of Allahabad" 4; mostly 2023 and 2025), report in `hindi_native.report.json`. T2 draws 200 by seed into
  `data/testsets/t2_hindi_native/` (`python -m vakeel_sahayak.testsets.t2_messy_bundles --hindi-native data/interim/hindi_native.jsonl --native-only --out data/testsets/t2_hindi_native`,
  origin `native_hc`). **Caveat:** High Court Hindi, not Uttar Pradesh district-court Hindi like HLDC, so make no "district-court Hindi" claim; HLDC still replaces it when access arrives.
* **Models:** `scripts/download_models.sh` (tiers in `configs/models.yaml`, `make models-dry-run`); T1 helpers go to `models/hf`, listed in `models/MANIFEST.json`.
* **Stores:** full build log and result in `docs/handoff/data-and-models.md`; `data/stores/MANIFEST.json` is written when it finishes.
* Supreme Court metadata is wired into the citation index (VI-05, 2026-10-25). `interim/oil_metadata.jsonl` (152,413 records: the 37,014 Supreme Court judgments of `raw/open_india_law/sc_metadata.jsonl` plus the orders' own fields) is built by `python -m vakeel_sahayak.pipelines.citation_graph.oil_metadata`; its schema is in that module's docstring and in `docs/handoff/citation-sc-metadata.md`. Candidate stores built with it live in `stores_candidate/` (see `stores_candidate/SWAP.md`); `stores/` is unchanged until someone swaps.
