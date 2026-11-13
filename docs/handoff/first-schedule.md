# First Schedules (CrPC 1973 and BNSS 2023, Part I) and NDPS sections: handoff, 13 Nov 2026

Shravani's "missing statutes" item (`docs/handoff/team-todo-2026-11-02.md`), done on the owner's behalf. Everything is produced by
`scripts/extract_gap_statutes.py` from official PDFs. Nothing was typed by hand. No store was rebuilt.

## What was done

1. **First Schedule table, committed:** `configs/first_schedule_crpc_ipc.jsonl` has one row per IPC section in Part I of the CrPC First
   Schedule. Each row has `code`, `section`, `offence`, `punishment`, `max_punishment`, `cognisable`, `bailable`, `triable_by`, the
   `subrows` as printed (with `cognisable_text` and `bailable_text`) and `source` (`url` and `sha256` of the PDF). The sidecar
   `configs/first_schedule_crpc_ipc.meta.json` records the source, the PDF pages, the date, the script, the coverage and every
   unresolved cell (`notes`).
   - `max_punishment` takes one of these forms: `death`, `life imprisonment`, `N years`, `N months`, `N hours`, or `fine`. With several
     sub-rows it is the heaviest. It is null when a sub-row is relative ("Same as for offence abetted").
   - The statute store's IPC rows write life imprisonment as `life`, so map `life imprisonment` to `life` if you compare the two.
2. **Parser fixes:** the flags the first parser wrote (commit 5f6fb71, 26 Oct) were wrong for 43 sections. That parser's output is in
   `data/gaps/statutes/first_schedule_ipc.jsonl` and in the current `data/stores/law/statutes.sqlite`.
   - **27 sections had `bailable` the wrong way round:** 194, 195, 195A, 363A, 364, 364A, 365, 366, 366A, 366B, 367, 368, 369, 388,
     389, 452 to 461, 489E and 505. For example, the live store answers IPC 364 (kidnapping in order to murder) and IPC 457 as
     bailable. The schedule prints them non-bailable.
   - **19 sections had `cognisable` the wrong way round:** 176, 177, 190, 193, 194, 195, 212, 213, 225A, 228A, 475 to 477A, 482 to 485
     and 489E.
   - **Causes:**
     - cell words were sorted alphabetically within a line;
     - "Ditto" was matched anywhere in a cell;
     - sub-rows printed 11 pt apart were merged;
     - the bail column edge was fixed for every page;
     - the Part II table and a heading word ("Punishment") were read as cells.
   - **Now set to null rather than guessed:**
     - 118, 354C, 354D and 451, where the sub-rows differ;
     - 467, 474 and 505, where cognisable differs by sub-row;
     - 498A, where the cell reads "Cognizable if information ... is given by the person aggrieved";
     - 355 to 358 and 363, where a "Ditto" falls under the 2013 entries for ss.354A to 354D. Read as printed, that Ditto would make
       s.355 non-bailable with a 5-year maximum.
   - **Newly set:** 172, 174A, 175, 189, 202, 203, 227, 229A, 500 to 502 and 510.
3. **NDPS:** `get_statute('NDPS', '22')` failed because the extraction took only 6 sections (19, 24, 27A, 31A, 36A, 37).
   - The script now takes every section of the DoR text: 126 rows.
   - Flags come from the parsed s.37 text. The 26 sections that say "shall be punishable"/"shall be punished" or that s.37 names get
     `cognisable: true`. The 24 penal sections also get `max_punishment`, null where the text is relative. For example, ss.15 and 17
     to 24 are 20 years and s.27 is 1 year.
   - `bailable: false` goes only to 19, 24, 27A and 37. These are the sections s.37(1)(b) names, so it is not applied by quantity.
   - s.37 (the twin conditions) is extracted from the official text, 989 characters.
   - `StatuteStore.get` matches exactly, so callers must pass `22`, not `22(c)`. Stripping the clause is the lookup's job.
4. **BNSS 2023 First Schedule, Part I (BNS offences):** `configs/first_schedule_bnss_bns.jsonl` (+ `.meta.json`) has the same fields as
   the IPC table, with `code: "BNS"`. The source is the pinned Gazette PDF (`BNSS_URL`, `BNSS_SHA256`), PDF pages 158 to 189, read by
   `parse_bnss_schedule`.
   - It has 288 sections and 465 sub-rows.
   - An entry printed "318(4)" is a sub-row of section `318` with `subsection: "(4)"`, because the store keys BNS rows by the bare
     number. A lookup for BNS 318(4) should take the section-318 row and pick the sub-row by `subsection`. The section-level flag is
     null when sub-sections differ: 318 is bailable for (2) and (3) and non-bailable for (4).
   - Coverage: bailable 256/288 (88.9%), cognisable 259/288, max_punishment 256/288, triable_by 288/288.
   - Spot check:
     - 103 non-bailable (death);
     - 115(2) bailable and non-cognizable (1 year);
     - 318(2) and 318(3) bailable, 318(4) non-bailable and cognizable (7 years);
     - 351 bailable;
     - 85 non-bailable with cognisable null ("Cognizable if information ...");
     - 74 non-bailable.
   - Flags-only rows for the store go to `data/gaps/statutes/first_schedule_bns.jsonl`.
   - The Gazette prints neighbouring cells as one PDF span ("Imprisonment for 7 years According as offence"), so this table is read
     word by word in fixed columns.

## Coverage (398 IPC sections)

| field | non-null |
|---|---|
| bailable | 373 / 398 (93.7%) |
| cognisable | 377 / 398 (94.7%) |
| max_punishment | 369 / 398 (92.7%) |
| triable_by | 398 / 398 |

There are 25 null `bailable` values:
- conditional cells ("According as the offence abetted is ..."): abetment and conspiracy sections 109 to 120B, 149, 150, 196 and 511;
- sub-rows that differ: 118, 119, 120, 222, 225, 354C, 354D and 451;
- the unresolved Ditto rows: 355 to 358 and 363.

The 29 null `max_punishment` values are relative punishments such as "Same as for offence abetted" or "a quarter of the longest term".

Spot check against the printed cells: 302 non-bailable (death), 323 bailable and non-cognizable (1 year), 420 non-bailable (7 years),
143 and 341 bailable, 332 non-bailable, 353 non-bailable, 498A non-bailable with cognisable null. All agree with the PDF lines read
independently of the parser.

## Sources

- **CrPC 1973 (India Code consolidated file A1974-02):**
  - URL: `https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf`
  - SHA-256 `8ddde136…7c1e1`, now pinned as `CRPC_SHA256`. Schedule on PDF pages 195 to 222.
- **NDPS Act 1985 (Department of Revenue):**
  - URL: `https://dor.gov.in/files/acts_files/NDPS_1985.pdf`
  - SHA-256 `8cd8e71f…eac2`, pinned as `NDPS_SHA256`.
- **India Code was unreachable on 13 Nov 2026.** These bitstreams answered HTTP 504, and the handle page timed out:
  - `https://www.indiacode.nic.in/bitstream/123456789/13624/1/the_code_of_criminal_procedure%2c_1973.pdf`
  - `https://indiacode.nic.in/bitstream/123456789/15381/1/ccp1973.pdf`
  - `https://www.indiacode.nic.in/bitstream/123456789/1791/5/a1985-61.pdf`
- **BNSS Gazette:** `egazette.gov.in/WriteReadData/2023/250884.pdf` was reachable. Use `--cafile` with the Let's Encrypt YR1
  intermediate from `http://yr1.i.lencr.org/`, appended to the system bundle. The file matches the pinned `BNSS_SHA256`. Its First
  Schedule starts on PDF page 158.

## For Satvik's store rebuild (one rebuild)

0. **Protect the frozen runs first.** The frozen run worktree's `data/stores/law` is a symlink to the main checkout's `data/stores/law`
   (`ls -la .claude/worktrees/agent-a8400ab774cc73e44/data/stores/`). Replace the symlink with a copy of the current store
   (`rm <frozen>/data/stores/law && cp -a data/stores/law <frozen>/data/stores/law`) before rebuilding, so the scored runs keep the
   store they were made with. Rebuild only after the D12 scoring has finished (it has, if `var-pool/autoscore.log` ends in AUTOSCORE_DONE).
   The product reads `configs/first_schedule_*.jsonl` before the store already (Peshkar, 7b3945a), so the rebuild fixes the store,
   not the briefs.

1. Regenerate the gap files first. The copies in `data/gaps/statutes/` hold the old, wrong flags and only 5 NDPS rows:

   ```
   curl -s http://yr1.i.lencr.org/ | openssl x509 -inform der > /tmp/yr1.pem; cat /etc/ssl/certs/ca-certificates.crt /tmp/yr1.pem > /tmp/bundle.pem
   PYTHONPATH=src .venv/bin/python scripts/extract_gap_statutes.py --only crpc,ndps,bnss --fetch --cafile /tmp/bundle.pem
   ```

   PDFs land in `data/gaps/raw/` and are checked against the pinned SHA-256. This rewrites `crpc.jsonl`, `ndps.jsonl`, `bnss.jsonl`,
   `first_schedule_ipc.jsonl`, `first_schedule_bns.jsonl` and the committed `configs/first_schedule_*`. The configs copies must
   come out byte-identical except for `generated`.
2. Rebuild the store as usual (`StatuteStore().build('data/interim', 'data/stores/law')`).
3. **How the fields reach the store:**
   - `_merge_gap_rows` adds `bailable` and `cognisable` from the empty-text rows of `first_schedule_ipc.jsonl` and
     `first_schedule_bns.jsonl` to the IPC and BNS rows. It only adds non-null flags. Today no BNS row in the store has a flag.
   - NDPS gap rows replace or add whole rows, including `bailable`, `cognisable` and `max_punishment`.
   - IPC `max_punishment` in the store still comes from the IPC text (`oil_ingest.max_punishment`).
   - If you want the schedule's maximum instead, read `max_punishment` from `configs/first_schedule_crpc_ipc.jsonl` and map
     `life imprisonment` to `life`. No builder reads the configs file today. The owner's statutory-position lookup can read it directly.

## Not done (left open)

- **Part II** of the CrPC and BNSS First Schedules (offences against other laws).
- **BNS cell text:** a very long conditional cognizable cell can still leave a stray word in the neighbouring cell's text. The flags
  are not affected; they are read from the start of the cell.
- **NDPS `bailable`:** set only where s.37 names the section. The commercial-quantity bar depends on the quantity, so it is not a
  section flag.
- **NDPS s.29 and s.31A:** s.29 (abetment, conspiracy) gets no flag because its wording splits "shall ... be punishable". s.31A's
  "punishable with death" is not caught by the store's `max_punishment` rule.

## How to check

```
PYTHONPATH=src .venv/bin/pytest tests/unit/stores/test_extract_gap_statutes.py -q   # 39 passed, offline (synthetic PDFs)
```

Run the tests with `PYTHONPATH=src` from a worktree: the venv's editable install points at the main checkout's `src`.
