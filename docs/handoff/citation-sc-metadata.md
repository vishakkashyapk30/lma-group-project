# VI-05: Supreme Court metadata in the citation index (2026-10-25)

## Done
- `pipelines/citation_graph/oil_metadata.py`: builds `data/interim/oil_metadata.jsonl` (152,413 records) from `raw/open_india_law/sc_metadata.jsonl` (37,014 SC judgments; fields doc_id, title, date, court, citations = INSC + SCR, case_number empty) and the orders' own fields (115,988; 589 SC orders are in both). Schema in the module docstring: doc_id, court, court_level, date, year, title, case_name (docket prefix removed), neutral_citation, citations, case_number, bench_size, in_corpus, source. Command: `python -m vakeel_sahayak.pipelines.citation_graph.oil_metadata` (about 2 minutes).
- `extract.py`: new `scr` format ('[1979] 3 S.C.R. 453', 'SUPP.' volumes, '(1979) 3 SCR 453'), appended last so existing patterns are unchanged. `resolve.py`: SCR/INSC keys resolve exactly; docket prefixes ('BAIL/3506/2025 of X Vs Y') dropped before name matching; a judgment listed twice is not its own rival; `load_index` uses the word-blocked index above 5,000 records (G2 on 19,307 orders took 59 s). `store_builders/corpus.py`: reads `<interim>/oil_metadata.jsonl` when present (SC-only records, never excluded ids), describes cited SC graph nodes with court, level and date. No file, no change.
- `pipelines/citation_graph/measure.py`: seeded sample (seed 20261025, 40,000 orders, 8,103 occurrences; 2,000 uniform plus up to 250 per format) in `data/interim/citation_eval/` (sample.jsonl, before.json, after.json).
- Tests: `tests/unit/pipelines/citation_graph/test_sc_metadata.py` (12, synthetic fixtures). The pipelines, stores and testsets areas pass except the T7 stubs.

## Resolution rate (before = HEAD code and orders only; after = new code, orders + oil_metadata)
Uniform sample of 2,000 occurrences: 17.0% (340) -> 32.2% (643).

| format | uniform n | resolved before | resolved after | per-format sample (n) | rate before -> after |
|---|---|---|---|---|---|
| INSC | 11 | 0 | 11 | 37 | 0% -> 97% |
| SCR | 62 | 0 (not extracted) | 56 | 235 | 0% -> 93% |
| SCC | 672 | 0 | 0 | 250 | 0% -> 0% |
| AIR | 65 | 0 | 0 | 250 | 0% |
| SCC OnLine | 84 | 0 | 0 | 250 | 0% |
| Cri LJ | 8 | 0 | 0 | 24 | 0% |
| case name | 1,098 | 340 | 576 | 250 | 33% -> 52% |

SCC, AIR, SCC OnLine and Cri LJ stay at 0 because sc_metadata has no such numbers (T9 constructs them). Case-name gain is SC titles plus docket-prefix cleaning; of 576 resolved case names in the uniform sample 531 go to SC, 45 to HC.

## T1 gold G2 (candidate: `data/interim/t1_work_candidate/gold/g2.jsonl`, `data/testsets/t1_candidate/`, numbers in `t1_work_candidate/g2_coverage.json`; current T1 untouched; same 200 cases selected)
| set | extracted citations | resolved before -> after | orders with >=1 resolved | resolved that are inside the stores |
|---|---|---|---|---|
| test 200 | 80 | 0 -> 27 (26 SC) | 0 -> 14 | 17 (12 orders) |
| BNS-era 80 | 15 | 0 -> 6 | 0 -> 3 | 2 (1 order) |
| dev 50 | 13 | 0 -> 0 | 0 | 0 |
| all 19,307 candidates | 4,932 | 0 -> 1,214 | 639 | 724 (464 orders) |

Consequence for C5: only 3 BNS-era orders have a resolved citation (needs 30), so C5 stays a pilot statement. "Inside the stores" matters: only 589 SC judgments are corpus orders, so most resolved SC targets (e.g. 26 of 27) have no text in any store and recall@10 cannot reach them; report recall on the in-store subset next to the resolved count.

## Candidate stores (`data/stores_candidate/`, never swapped)
`build_all --only citations --splits data/interim/splits.json`, started 23:24 IST, finished 23:56 (about 33 min, log /tmp/claude-1000/run/citations_build.log). Edges 3,492 -> 5,810; nodes 115,376 -> 116,400; edges into SC nodes 3,175 -> 5,368; distinct cited judgments 389 -> 1,279; build-time resolution 19.3% -> 31.6%. `MANIFEST.json` and `SWAP.md` are in that folder.

## Not done / caveats
- `reasoning`, `arguments`, `objections`, `similar` were not rebuilt: their `cites`/`authority` are from the old resolution. Full `make stores` would fix it.
- Exclusion mismatch: `data/stores` used the pre-T1 splits (612 excluded); current `splits.json` excludes 464, and 282 of those are inside `data/stores` (T1 leakage). The candidate uses the current splits, so its node count is not a pure effect of the metadata.
- Fuzzy name matching has false resolutions (seen: 'Mahidul Sheikh v. State of Haryana' -> 'ABDUL SHEIKH Vs STATE OF JHARKHAND'; 'Ridhm Rana' -> 'NIDHI RANA'; truncated names match long titles). Pre-existing thresholds; accuracy is T9's job and was not re-tuned or measured here.
- The "before" SCR count is 0 because the old extractor did not extract SCR at all.
- Open idea, not built: link 'Name, (2014) 8 SCC 273' by resolving the SCC citation through the case name just before it, checked against the year. SCC is a third of all occurrences.
