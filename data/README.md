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
about 1.5 to 2 GB). It is a PRIVATE Hugging Face dataset, `vishakkashyapk/vakeel-sahayak-data`
(https://huggingface.co/datasets/vishakkashyapk/vakeel-sahayak-data); ask the owner for read access, then log in once with `hf auth login` or put
`HF_TOKEN=...` in the untracked `.env`, and from the repository root:

```bash
make data-install SRC=hf:vishakkashyapk/vakeel-sahayak-data     # or SRC=<a folder or URL the owner gave you>
make data-install SRC=~/vakeel-data-bundle FORCE=1             # FORCE=1 overwrites what is already in data/
```

It verifies `SHA256SUMS`, refuses to overwrite `data/` without `FORCE=1`, unpacks, and checks row and file counts against `bundle_manifest.json`.
Not in the bundle: model weights (`MODELS.txt` lists names and sizes; `make models`), `data/cases` (private client files), `data/openai`, `data/raw` (except
`MANIFEST.json`) and HLDC. Owner side: `make data-bundle` (writes `~/vakeel-data-bundle`, no upload) and `make data-publish` (uploads it with `hf upload`; token
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

## Gap-filling status (2026-10-24)

* **Statutes retry (2026-10-26):** `indiacode.nic.in` now answers (302) and `www.indiacode.nic.in` returns a "Site Migration" page pointing to
  `https://indiacode.gov.in`, a DSpace 9 site whose REST API (`https://indiacode.gov.in/server/api`) answers without a login (it also redirects
  `legislative.gov.in` to `www.legislative.gov.in`). The old handle URLs (`/handle/123456789/15247`) and `upload.indiacode.nic.in` do not work. Nothing was
  downloaded: the files in `data/gaps/raw/` are HTML error pages saved with a `.pdf` name (not statutes), and no `data/gaps/statutes/*.jsonl` exists. Next
  step for a person: find the CrPC 1973 and NDPS Act items on the new site (search "Code of Criminal Procedure, 1973" in the browser or via
  `/server/api/discover/search/objects?query=...`), save the official PDF, then follow the team step below. Do not type statute text from memory.
* **Statutes gap (CrPC 1973, NDPS s.37, First Schedule bailable/cognisable columns): not fetched.** On 2026-10-24 later retries from this machine timed out or were refused for indiacode.nic.in, upload.indiacode.nic.in, legislative.gov.in, lddashboard.legislative.gov.in and egazette.gov.in (Indian government hosts are unreachable from this network). `indiacode.nic.in` answers
  automated requests with HTTP 403 (Akamai), `legislative.gov.in` and `mha.gov.in` direct PDF paths return 404, and nothing may be typed
  from memory. The loader is ready: `StatuteStore.build` merges every `data/gaps/statutes/*.jsonl` (one `StatuteRow` per line, optional extra
  keys such as `source_url` are ignored). **Team step:** in a browser open https://indiacode.nic.in/handle/123456789/15247 (CrPC 1973, Act ID 197402)
  and the NDPS Act 1985 page, save the PDFs to `data/gaps/raw/`, extract s.41, 41A, 50, 57, 167, 436, 436A, 437, 438, 439, the First Schedule
  and NDPS s.37 (and s.19, 24, 27A, 31A that its bar names) into `data/gaps/statutes/crpc.jsonl` / `ndps.jsonl`, with the URL and retrieval
  date in each row's `source_url`, then `scripts/build_stores.sh --only statutes`. No official bailable/cognisable table for BNS offences
  was found; the BNSS/BNS First Schedule is in the same Legislative Department publication (bnss 2023, Act 46) and has to be added the same way.
* **Kathbath Hindi test_known:** `kathbath_fetch --limit 3130` finished: 3,130 of 3,130 utterances with transcripts (about 300 MB).
* **e-SCR / SUVAS Hindi judgments: not attempted.** The translations (about 36,000 Hindi judgments) are on the e-SCR portal, but we found no
  published bulk download, reuse licence or terms page, so nothing was fetched. Ask the Supreme Court Registry / NIC for written permission,
  or use per-judgment manual downloads for a small sample. Fallback: translate with IndicTrans2/NLLB.
* **HLDC / IL-TUR `bail` config: blocked.** No Hugging Face login or `HF_TOKEN` on this machine. **Team step:** with a Hugging Face account, open
  https://huggingface.co/datasets/Exploration-Lab/IL-TUR , accept the access terms (non-commercial, CC BY-NC-SA 4.0), run `huggingface-cli login`
  (or export `HF_TOKEN`), then `load_dataset("Exploration-Lab/IL-TUR", "bail")` into `data/raw/hldc/` and update `raw/MANIFEST.json`. Until then
  the documented fallback is NLLB English to Hindi translation of constructed orders.
* **Models:** `scripts/download_models.sh` (tiers in `configs/models.yaml`, `make models-dry-run`); T1 helpers go to `models/hf`, listed in `models/MANIFEST.json`.
* **Stores:** full build log and result in `docs/handoff/data-and-models.md`; `data/stores/MANIFEST.json` is written when it finishes.
* Supreme Court metadata is wired into the citation index (VI-05, 2026-10-25). `interim/oil_metadata.jsonl` (152,413 records: the 37,014 Supreme Court judgments of `raw/open_india_law/sc_metadata.jsonl` plus the orders' own fields) is built by `python -m vakeel_sahayak.pipelines.citation_graph.oil_metadata`; its schema is in that module's docstring and in `docs/handoff/citation-sc-metadata.md`. Candidate stores built with it live in `stores_candidate/` (see `stores_candidate/SWAP.md`); `stores/` is unchanged until someone swaps.
