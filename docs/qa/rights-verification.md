# Rights Radar: rule texts checked against the bare acts (HA-03)

Status: **draft for review, 2026-10-27.** No `last_verified` date is set yet. A date goes into `configs/rights_rules.yaml` only after
Harshita has read the rule against the act and agrees with the verdict below; a rule with an open question keeps `null` and the
question stays in the table at the end (split.md HA-03: "each of the 7 rules has a source and date, or an open question").

## How the check was done

- **Rules:** the `rule` text in `configs/rights_rules.yaml` and the code that applies it, `src/vakeel_sahayak/rights/rules/*.py`
  (with `rights/engine.py`, `punishment.py`, `day_count.py`).
- **Bare acts:** the statute store built from the team data bundle (`data/stores/law/statutes.sqlite`).
  - CrPC 1973 (s.41A, 50, 57, 167, 436A): consolidated text from
    <https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf>, retrieved 2026-10-26
    (`data/gaps/statutes/crpc.jsonl`).
  - NDPS Act 1985 (s.37): <https://dor.gov.in/files/acts_files/NDPS_1985.pdf> (`data/gaps/statutes/ndps.jsonl`).
  - BNSS 2023 (s.35, 47, 57, 58, 187, 479), UAPA (s.43D), PMLA (s.45): Open India Law `v2026.08.1` legislation file.
- **Case law is not checked here.** None of the judgments the rules cite (Kapil Wadhawan, M. Ravindran, In Re 1382 Prisons, Arnesh
  Kumar, Antil, Vihaan Kumar, Mihir Rajesh Shah) is in our data. Where a rule rests on a judgment rather than the act, the verdict
  says so and the judgment is listed as still to read.

## Summary

| Rule | Act text supports the rule? | Problems found | Suggested `last_verified` |
|---|---|---|---|
| `default_bail` | Yes for the IPC/BNS case | **Ignores special-act time limits** (UAPA s.43D(2), NDPS s.36A(4)): can say ELIGIBLE too early | `null` until fixed |
| `undertrial_limit` | Yes for BNSS s.479(1) | **Ignores s.479(2)** (several pending cases restrict bail under the section; read by the Delhi High Court as a factor, not an absolute bar); CrPC s.436A covered life-imprisonment offences | `null` until fixed |
| `notice_of_appearance` | Yes | Minor: BNSS s.35(7) (age 60+ / infirm, offences under 3 years) not modelled | date after review |
| `grounds_of_arrest` | Communication: yes. Writing and 2 hours: from case law, not the act | Judgments not read | `null` until judgments are read |
| `production_24h` | Yes (CrPC s.57) | **Store holds the wrong text for BNSS s.58** (body of s.59) | date after review; data bug to Vishak |
| `antil_category` | Judgment only (no act) | **Any non-IPC/BNS act gives category C**, not only acts with strict bail conditions | `null` until fixed |
| `statutory_bar` | Partly | **Over-broad**: NDPS s.37 and UAPA s.43D(5) bar only some offences; "twin conditions" does not describe UAPA | `null` until fixed |

Three of the problems can produce a wrong **ELIGIBLE** (the safety number in the evaluation plan is the false-ELIGIBLE rate):
`default_bail` for UAPA and NDPS cases and `undertrial_limit` for a person with several pending cases (there the court may still
grant bail, so the right answer is CHECK, not ELIGIBLE).

Reproduced by calling the rules directly with `RuleInputs` (2026-10-27):

| Input | Rule says | The act says |
|---|---|---|
| UAPA, maximum 5 years, no charge sheet, day 62 from first remand | `default_bail`: ELIGIBLE | Limit is 90 days (s.43D(2)): not yet |
| NDPS s.21(c), maximum 20 years, no charge sheet, day 100 | `default_bail`: ELIGIBLE | Limit is 180 days (s.36A(4)): not yet |
| BNS 303, maximum 3 years, 600 days in custody, not a first-time offender | `undertrial_limit`: ELIGIBLE | If other cases are pending, s.479(2) restricts release and bail is the court's discretion: CHECK; `RuleInputs` has no field for them |
| Arms Act s.25, maximum 3 years | `antil_category`: C | Not an act with a bail bar: A |
| NDPS s.20(b)(ii)(A) (small quantity) | `statutory_bar`: BAR_APPLIES | s.37(1)(b) does not reach it |

## Rule by rule

### 1. `default_bail`: BNSS s.187(3), CrPC s.167(2)

**Rule:** release if no charge sheet within 90 days (death, life or 10 years and above) or 60 days (other offences); day 1 is the
first remand; the right lapses if the charge sheet is filed before an application; "may extend to ten years" gives CHECK.

**Act:** BNSS s.187(3): "ninety days, where the investigation relates to an offence punishable with death, imprisonment for life or
imprisonment for a term of ten years or more; (ii) sixty days, where the investigation relates to any other offence". CrPC s.167(2)(a)
said "a term of not less than ten years".

- The 60/90 split matches the act.

The rule also rests on three separate questions that the act does not answer. The judgments below were read by Harshita
(2026-10-27). **All three interpret the former CrPC s.167(2)**; for proceedings governed by the BNSS, s.187(3) has to be checked
separately (its text keeps the same structure, "on the expiry of the said period ... shall be released on bail if he is prepared to
and does furnish bail", but no BNSS ruling has been read yet).

1. **When does the period begin?** ED v. Kapil Wadhawan (2023): the remand date is included in the 60/90 days. The code counts the
   first remand as day 1 (`day_count.count_days`, `INCLUSIVE_DAY_1`), which matches.
2. **Does a charge sheet extinguish the right?** Not invariably. M. Ravindran v. DRI (2020): if the accused applied for default bail
   after the right accrued, a later charge sheet does not defeat it; the timing of the application decides. The code matches: an
   application made after the limit and before the charge sheet gives ELIGIBLE, and a charge sheet filed after the limit with no
   recorded application gives WINDOW_CLOSED with "check whether an application was made". The rule text "the right lapses if the
   charge sheet is filed before an application" should say "before the accused applies for default bail after the right accrued",
   so it is not read as "any charge sheet ends the right".
3. **Is a ten-year maximum a 60-day or a 90-day case?** Rakesh Kumar Paul v. State of Assam (2017) interpreted "not less than ten
   years" in the CrPC; the distinction between a maximum of ten years and a minimum of ten years matters. The applicable period must
   come from the statutory punishment and the binding interpretation, not from the phrase "may extend to ten years" on its own. The
   code returns CHECK for a ten-year maximum and 90 days for a minimum of ten years or more. CHECK is the safe answer while the BNSS
   wording "ten years or more" has no reading of its own; for CrPC-governed cases Rakesh Kumar Paul should decide it.
- **Problem: special acts change the limits, and the rule does not know.** UAPA s.43D(2) (in the store) makes the limits "ninety
  days" for every UAPA offence (60 becomes 90) and lets the court extend to 180 days. NDPS s.36A(4) (not in our store; check the
  bare act) extends the limit to 180 days for offences under s.19, 24, 27A and commercial-quantity offences. Today a UAPA case on
  day 61 or an NDPS commercial-quantity case on day 91 can be reported **ELIGIBLE** when it is not.
- **Proposed fix (Vishak):** when a UAPA or NDPS section is charged, return CHECK with the special-act limit named, or apply the
  special limits.

### 2. `undertrial_limit`: BNSS s.479, CrPC s.436A

**Rule:** release on bond after half the maximum sentence, or one-third for a first-time offender; not for death or life.

**Act:** BNSS s.479(1) excludes offences "for which the punishment of death or life imprisonment has been specified"; half the
maximum gives release "on bail"; the first proviso gives a first-time offender ("who has never been convicted of any offence in the
past") release "on bond" after one-third. CrPC s.436A excluded only death.

- Half, one-third and the death/life exclusion match BNSS s.479(1).
- **Problem: s.479(2)** says that where "an investigation, inquiry or trial in more than one offence or in multiple cases are
  pending against a person, he shall not be released on bail by the Court." The rule never looks at other pending cases, so a person
  with two pending cases past the threshold is reported **ELIGIBLE**.
- **How the courts read s.479(2) (checked by Harshita, 2026-10-27):** not as an absolute bar. The Delhi High Court (BAIL APPLN.
  4657/2024, judgment of 5 May 2026) held that s.479(2) does not remove the court's discretion to grant bail once the s.479(1)
  threshold is crossed; multiple pending cases remain a significant factor. Other courts may read it differently, and the outcome
  depends on the facts.
- Proposed fix: return **CHECK** (not ELIGIBLE, and not NOT_APPLICABLE) when antecedents show another pending case, with a detail
  that names the s.479(2) restriction and says bail is then at the court's discretion. Also do not treat "no antecedents on record"
  as proof of a first-time offender (the proviso is about previous convictions).
- **CrPC-era cases:** s.436A did not exclude life imprisonment. For a case governed by the CrPC, "not for life" is stricter than the
  act. Which regime applies to an undertrial whose case began before 1 July 2024 is what In Re Inhuman Conditions in 1382 Prisons
  (2024) is cited for; to read before setting a date.
- The rule does not say that the second proviso lets the court order continued detention after hearing the Public Prosecutor, or
  that delay caused by the accused is excluded (Explanation). Suggest adding both to the rule text shown to counsel.
- Wording: the rule says "on bond" for both thresholds; the act says "on bail" at one-half and "on bond" at one-third.

### 3. `notice_of_appearance`: BNSS s.35(3), CrPC s.41A

**Rule:** for offences punishable up to 7 years a notice of appearance is the norm and arrest needs recorded reasons.

**Act:** BNSS s.35(1)(b): arrest without warrant for an offence punishable "for a term which may be less than seven years or which
may extend to seven years" only if the listed conditions are met, and "the police officer shall record while making such arrest,
his reasons in writing". CrPC s.41A (the text of BNSS s.35(3) to (6)): notice of appearance where arrest is not required.

- The rule matches the act. Arnesh Kumar and Antil are cited for the "norm"; to read, but the act alone supports the rule text.
- Not modelled (optional): BNSS s.35(7), no arrest without the permission of an officer not below Deputy Superintendent for an
  offence punishable with less than 3 years if the person is infirm or over 60.
- The rule returns OK when any arrest memo is in the file and asks counsel to confirm it records reasons; that is a fair limit for
  a rule that cannot read the memo.

### 4. `grounds_of_arrest`: Art. 22(1), BNSS s.47, CrPC s.50

**Rule:** grounds must be communicated; since Mihir Rajesh Shah, in writing, in a language the arrested person understands, at
least 2 hours before production; application to earlier arrests is contested, so CHECK.

**Act:** BNSS s.47(1) (same as CrPC s.50(1)): every person arresting without warrant "shall forthwith communicate to him full
particulars of the offence for which he is arrested or other grounds for such arrest".

- "Communicated" matches the act. "In writing", "a language he understands" and "2 hours before production" are not in the act;
  they come from Vihaan Kumar (2025) and Mihir Rajesh Shah (2025). **To read both judgments**, including from which date the
  written-grounds requirement applies, before setting a date.
- Not modelled (optional): BNSS s.47(2), the duty to tell a person arrested for a bailable offence that they are entitled to bail.
- The rule's statuses never claim eligibility for anything, so it cannot produce a false ELIGIBLE.

### 5. `production_24h`: Art. 22(2), BNSS s.58, CrPC s.57

**Rule:** produce before a magistrate within 24 hours of arrest, excluding travel time.

**Act:** CrPC s.57: detention "shall not ... exceed twenty-four hours exclusive of the time necessary for the journey from the place
of arrest to the Magistrate's Court". The rule matches.

- **Data problem:** the store's BNSS s.58 row has the right heading ("Person arrested not to be detained more than twenty-four
  hours") but the body of s.59 ("Officers in charge of police stations shall report to the District Magistrate ..."). The rule cites
  BNSS s.58 correctly; the stored text is wrong, so any tool that shows it to counsel shows the wrong section. For Vishak: fix the
  row or add a gap row in `data/gaps/statutes/` from an official BNSS copy.
- Code: with no times on record, production on the next calendar day gives CHECK and two or more days later gives FLAG; that is
  the right conservative split. Note that `production_date` is taken from the first remand date (`engine.py`), which is a stand-in.

### 6. `antil_category`: Satender Kumar Antil v. CBI (2022)

**Rule:** A: up to 7 years (not B or D); B: death, life or more than 7 years; C: special acts with strict bail conditions; D:
economic offences not under special acts.

- No act to check against; the categories come from the judgment. **To read** the categorisation paragraph of Antil.
- **Problem:** `engine.py` sets `special_act` to any code other than IPC, BNS, CrPC or BNSS, and the rule then returns category C.
  An Arms Act, Excise Act or IT Act charge is not an act "with strict bail conditions", so it is put in C wrongly. Proposed fix:
  C only for acts with a bail bar (at least NDPS, UAPA, PMLA, and others Antil names), else fall through to A/B/D.
- The economic-offence list (`ECONOMIC_SECTIONS`: IPC 406, 409, 420, 467, 468, 471; BNS 316, 318, 336, 338, 340) is marked in the
  code as "our reading"; it returns CHECK, not D, which is safe. To confirm against Antil.

### 7. `statutory_bar`: NDPS s.37, UAPA s.43D(5), PMLA s.45

**Rule:** the twin conditions apply.

**Act:**
- NDPS s.37(1)(b): the twin conditions (Public Prosecutor heard; reasonable grounds to believe not guilty and not likely to offend
  on bail) apply to "offences under section 19 or section 24 or section 27A and also for offences involving commercial quantity",
  **not to every NDPS offence**.
- UAPA s.43D(5): applies to "an offence punishable under Chapters IV and VI" only, and the test is different: no bail if the
  accusation is "prima facie true". It is not the twin-conditions test.
- PMLA s.45(1): twin conditions for "an offence under this Act"; the proviso exempts a person under sixteen, a woman, the sick or
  infirm, and money-laundering of less than one crore rupees, "if the Special Court so directs".

- **Problem:** the rule returns BAR_APPLIES for any NDPS, UAPA or PMLA charge. A small-quantity NDPS case or a UAPA charge outside
  Chapters IV and VI is told the bar applies when it does not. This errs against the accused rather than towards a false ELIGIBLE,
  but it is still wrong. The detail text does say "check that the specific section charged attracts the bar".
- Proposed fix: add CHECK to the allowed statuses and return it when quantity (NDPS) or chapter (UAPA) is not known; describe the
  UAPA test correctly; mention the PMLA proviso.

## Open questions and next steps

| # | Question | Who |
|---|---|---|
| 1 | Special-act limits in `default_bail` (UAPA s.43D(2), NDPS s.36A(4)) | Vishak (code), Harshita (NDPS s.36A text) |
| 2 | BNSS s.479(2): CHECK when other cases are pending (statutory restriction, court's discretion per Delhi HC, BAIL APPLN. 4657/2024); first-time-offender test in `undertrial_limit` | Vishak (code) |
| 3 | Which regime (CrPC s.436A or BNSS s.479) applies to pre-1 July 2024 cases: read In Re 1382 Prisons (2024) | Harshita |
| 4 | Read Vihaan Kumar (2025) and Mihir Rajesh Shah (2025): written grounds, language, 2 hours, from which date | Harshita |
| 5 | Category C only for acts with a bail bar, in `engine.py` / `antil_category` | Vishak (code) |
| 6 | `statutory_bar`: section- and quantity-aware, add CHECK, UAPA test wording | Vishak (code) |
| 7 | Wrong BNSS s.58 text in the statute store | Vishak (data) |
| 8a | `default_bail`, counting from the remand date (Kapil Wadhawan): read; the code matches. Closed for CrPC cases | Harshita (done) |
| 8b | `default_bail`, preserving a right exercised before the charge sheet (M. Ravindran): read; the code matches; reword the rule text | Harshita (done), Vishak (rule text) |
| 8c | `default_bail`, a ten-year maximum (Rakesh Kumar Paul, CrPC): read; for BNSS cases the s.187(3) wording "ten years or more" still needs a reading of its own | Harshita |
| 8d | The same three questions under BNSS s.187: find a BNSS-era ruling, or record that none is known | Harshita |
| 9 | Read Arnesh Kumar and Antil for the parts of the rules they support | Harshita |

When a row is closed, set `last_verified` for that rule in `configs/rights_rules.yaml` (and the matching `last_verified` in the
rule module, which is still `None` in code) and note the date here.
