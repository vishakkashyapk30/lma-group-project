# Rights Radar fixes after the bare-act check (HA-03)

Date: 2026-10-27. Spec: `docs/qa/rights-verification.md`. Everything below uses only that document and the statute store (`data/stores/law/statutes.sqlite`,
`data/gaps/statutes/*`); no statute text or limit was added from memory. Where the document leaves a point open the rule returns CHECK, never ELIGIBLE.

## What changed, per rule

| Rule | Change | Files |
|---|---|---|
| `default_bail` | Act-aware limit. UAPA s.43D(2): 90 days, extendable by the Court to 180. NDPS s.36A(4) for s.19, 24, 27A and commercial quantity: 180 days, extendable to one year. Day <= base: NOT_YET. Between base and the extended maximum: CHECK ("was the period extended?"), never ELIGIBLE. After the extended maximum: ELIGIBLE. An NDPS section whose quantity is not on record: NOT_YET up to the ordinary 60/90 days, CHECK up to one year. NDPS small or intermediate quantity keeps 60/90. An application made inside the extendable period gives CHECK. IPC/BNS behaviour is byte-identical. The ten-year CHECK detail now names the Kerala/Karnataka (60) and Orissa (90) split. Rule text says "before the accused applies for default bail after the right accrued (M. Ravindran)". | `rights/rules/default_bail.py`, `rights/acts.py` (new) |
| `undertrial_limit` | New `RuleInputs.other_pending_cases` (None = not on record). Pending case: CHECK instead of ELIGIBLE (NOT_YET is kept when the threshold is not reached). Unknown antecedents past one-half: ELIGIBLE only if the file says no other case is pending, else CHECK (the old "both thresholds met, so eligible whatever the antecedents" no longer holds because s.479(2) is unknown too). Death: NOT_APPLICABLE. Life: NOT_APPLICABLE only for a case clearly begun on or after 1 July 2024 (BNS/BNSS section or FIR/arrest/remand dates all on or after it; no IPC/CrPC section), else CHECK (CrPC s.436A covered life; no reading found). New `RuleInputs.fir_date`. Wording: "on bail" at one-half, "on bond" at one-third. Rule text adds the second proviso (continued detention after hearing the Public Prosecutor) and the Explanation (delay by the accused). | `rights/rules/undertrial_limit.py`, `rights/inputs.py`, `rights/acts.py` |
| `antil_category` | C only for NDPS, PMLA, UAPA and the Companies Act (the judgment's list as the document names it). Any other special act falls through to A or B by punishment, and the detail says the judgment's list ends "etc.". Every detail carries the scope note: Antil's categories are for an accused not arrested during investigation, so they are context for a client in custody. | `rights/rules/antil_category.py` |
| `statutory_bar` | Narrowed and given CHECK. NDPS: s.19, 24, 27A and clause (c) (commercial) BAR_APPLIES; clause (A) NOT_APPLICABLE; anything else CHECK. UAPA s.43D(5): Chapters IV and VI only, test is "prima facie true", not twin conditions; the store holds only s.43D, so the sections of those chapters come from the new empty parameter `uapa_chapter_iv_vi_sections` in `configs/rights_rules.yaml` and every UAPA charge is CHECK until a person fills it. PMLA: BAR_APPLIES with the proviso named. BAR_APPLIES points counsel to `grounds_of_arrest` (Vihaan Kumar). `plan.md` §7.3 and Appendix C updated; `statuses` in the yaml gets CHECK. | `rights/rules/statutory_bar.py`, `configs/rights_rules.yaml`, `docs/plan.md` |
| `grounds_of_arrest` | The CHECK the rule text promises: grounds communicated but only orally (`RuleInputs.grounds_in_writing` is False) returns CHECK, with a detail that names the 6 November 2025 date and the contested reach (Delhi vs Orissa High Court). Other outcomes unchanged. The rule text is unchanged, so its `last_verified` stays. | `rights/rules/grounds_of_arrest.py` |
| `notice_of_appearance` | No change. BNSS s.35(7) and s.47(2) are marked "optional" in the document, so they are not modelled. | none |
| `production_24h` | No code change. The BNSS s.58 data problem is below. | none |

The engine fills `other_pending_cases` (from antecedent entries that say pending / under investigation / under trial, only when antecedents are on record) and `fir_date`. It does
not fill `grounds_in_writing` (no source in the dossier yet).

`first_time_offender` is still "antecedents on record and the list is empty"; a non-empty list gives False (the higher threshold, the safe direction), even when the entries are only pending
cases and not convictions.

## Before and after on the five reproduced inputs

| Input | Before | After |
|---|---|---|
| UAPA, maximum 5 years, no charge sheet, day 62 | `default_bail` ELIGIBLE | NOT_YET (90-day UAPA limit; detail names s.43D(2) and the 180-day extension) |
| NDPS s.21(c), maximum 20 years, no charge sheet, day 100 | `default_bail` ELIGIBLE | NOT_YET (180-day limit, s.36A(4)) |
| BNS 303, 3 years, 600 days, not first-time, other case pending | `undertrial_limit` ELIGIBLE | CHECK (s.479(2); bail at the court's discretion) |
| Arms Act s.25, 3 years | `antil_category` C | A (with the scope note) |
| NDPS s.20(b)(ii)(A) | `statutory_bar` BAR_APPLIES | NOT_APPLICABLE |

## Verification state (item 9)

`last_verified` stays `null` (shown as `unverified` in every `RightsCheckResult`, and in `RightsReport.unverified_checks`) for `default_bail`, `undertrial_limit`, `antil_category`
and `statutory_bar`. The three dated rules keep 2026-10-27. After these fixes the owner should ask Harshita to re-verify the four corrected rules (`tests/unit/rights/test_ha03_fixes.py`
pins the verification state).

## T4 (rights scenarios)

| | Old | New |
|---|---|---|
| Scenarios | 500 | 627 |
| default_bail | 200 | 254 |
| undertrial_limit | 200 | 232 |
| notice_of_appearance | 50 | 50 |
| production_24h | 50 | 50 |
| antil_category | 0 | 19 |
| statutory_bar | 0 | 22 |

* The original 500 keep their ids and inputs (checked against `git HEAD`). Their designed answers change on 18: 10 undertrial scenarios with unknown antecedents at or past one-half
  (ELIGIBLE to CHECK) and 8 life-imprisonment scenarios whose arrest is before 1 July 2024 (NOT_APPLICABLE to CHECK).
* New ids: `dbs-` (special-act default bail, incl. UAPA day 62 and NDPS s.21(c) day 100), `uts-` (pending cases, unknown antecedents, old life cases, death; includes the BNS 303 input), `ac-` (includes Arms Act
  s.25), `sb-` (includes NDPS s.20(b)(ii)(A)). The five reproduced inputs are marked "reproduced wrong input" in their note.
* The spec writer (`testsets/rights_spec_writer.py`) still does not import `rights/`; it carries its own small reading of the document (section parts, quantity clause, special limits, era).
* Regenerated with `SETS=t4 scripts/build_testsets.sh` (spec hash and counts are in `data/testsets/t4/manifest.json`; `data/` is gitignored, so this is local; teammates rebuild with the same command
  or reinstall the bundle). The Radar agrees with the spec on all 127 new scenarios and the overall disagreement stays under the 2% the cross-check allows
  (`tests/unit/testsets/test_t4_radar_crosscheck.py`). The sealed blind data was not touched.
* T5 is built from the original 500 only (`t5_batch._ha03_scenario` filters the additions out); rebuilt into a scratch directory it is identical to the existing `data/testsets/t5`.
* F3 (`eval/features/f3_rights_radar.py`) passes `sections`, `other_pending` and `fir_date` to the Radar and handles the two new rules. The F3 job size in `configs/eval/runs.yaml`
  (`f3_baselines: scenarios: 1000`) is now 2 x 627 = 1254; it was left alone because `tests/unit/eval/test_features.py` pins 1000 and that file is shared. The owner decides.

## Person tasks

1. **BNSS s.58 text in the statute store is wrong (data problem, not fabricated here).** The `BNSS` row for section 58 has the heading "Person arrested not to be detained more than twenty-four
   hours" but the body of s.59 ("Officers in charge of police stations shall report to the District Magistrate ..."). Needed: the official BNSS 2023 text of s.58, from the Gazette of India
   copy of the Bharatiya Nagarik Suraksha Sanhita, 2023 (Act 46 of 2023; India Code or egazette.gov.in PDF), read by a person; add it as a row in `data/gaps/statutes/` (a new `bnss.jsonl` in the same
   format as `crpc.jsonl`) or fix the Open India Law row, then rebuild the statute store. The rule cites s.58 correctly; only the displayed text is wrong.
2. **UAPA Chapters IV and VI.** List the section numbers of those chapters from the bare act into `uapa_chapter_iv_vi_sections` in `configs/rights_rules.yaml` (the store holds only s.43D). Until then every UAPA
   charge is CHECK.
3. **NDPS quantity clause mapping.** The code reads the last clause of a charged NDPS section: (c) commercial, (A) small, (b) intermediate (from the document's examples NDPS s.21(c) and s.20(b)(ii)(A), and its Kerala
   s.22(b) reference). Harshita to confirm for ss.20 to 23 and any other quantity-based section; also that s.19, 24 and 27A are the only quantity-independent ones in s.36A(4) and s.37.
4. **Decisions for the owner or Harshita:** (a) `other_pending_cases` None with known antecedents still gives ELIGIBLE with a "confirm no other case is pending" line (the document says CHECK "when
   antecedents show another pending case"); making None give CHECK is one line in `undertrial_limit.py` but would send almost every real case to CHECK. (b) Past the extended maximum
   (UAPA 180, NDPS 365) the rule says ELIGIBLE; an extension order is not modelled. (c) Oral-only grounds give CHECK in every period (before and after 6 November 2025), because the document only
   settles the earlier period. (d) Whether the UAPA and NDPS limits still apply to BNSS s.187 (the document: "no reading found that treats them as lapsed").
5. **Re-verification** of the four rules (item 9 above) and the optional BNSS s.35(7) and s.47(2) (not modelled).

## Tests

New: `tests/unit/rights/test_ha03_fixes.py` (per rule), T4 cross-check additions. `# RECONCILED` edits: `tests/unit/config/test_config_files.py` (statutory_bar statuses gain CHECK), `tests/unit/rights/test_other_rules.py`
(NDPS 1 and UAPA 1 no longer BAR_APPLIES), `tests/unit/rights/test_undertrial_limit.py` (unknown antecedents past one-half: CHECK), `tests/unit/testsets/test_t4_rights_scenarios.py` (500 original plus additions).
Goldens re-captured: `tests/unit/agents/sutradhar/golden_default_run.json` (`events` and `packs` digests of both case-0007 worlds; a diff of the full canonical runs before and after showed only Radar rule_text, detail and the antil label text changed, no status) and `tests/unit/agents/peshkar/golden_default_run.json` `events` digest (the rights tool result carries the rule text and detail, which changed; case-0007 statuses are identical; dossier, dates and
prompt digests did not move).

Run results (offline): rights, testsets, config, features, agents, orchestration, batch unit tests pass (about 1,465 tests); the integration and system tests matching rights, radar, sutradhar, flow, munshi_to_peshkar and t7 pass (339).
`ruff check` is clean on the files touched (two pre-existing errors remain in `tests/unit/testsets/test_t2_messy_bundles.py`).
