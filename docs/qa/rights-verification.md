# Rights Radar: rule texts checked against the bare acts (HA-03)

Status: **checked 2026-10-27.** Three rules have a `last_verified` date in `configs/rights_rules.yaml` (`notice_of_appearance`,
`production_24h`, `grounds_of_arrest`): the act and the judgments support the rule as written. The other four keep `null`, each with
an open question in the table at the end (split.md HA-03: "each of the 7 rules has a source and date, or an open question"); most of
those questions are code or data fixes for Vishak.

## How the check was done

- **Rules:** the `rule` text in `configs/rights_rules.yaml` and the code that applies it, `src/vakeel_sahayak/rights/rules/*.py`
  (with `rights/engine.py`, `punishment.py`, `day_count.py`).
- **Bare acts:** the statute store built from the team data bundle (`data/stores/law/statutes.sqlite`).
  - CrPC 1973 (s.41A, 50, 57, 167, 436A): consolidated text from
    <https://cdnbbsr.s3waas.gov.in/s3ec044a11654ad1e1e48352252859ff30/uploads/2023/11/2023110156.pdf>, retrieved 2026-10-26
    (`data/gaps/statutes/crpc.jsonl`).
  - NDPS Act 1985 (s.36A, 37): <https://dor.gov.in/files/acts_files/NDPS_1985.pdf> (s.37 in `data/gaps/statutes/ndps.jsonl`; s.36A read
    from the same PDF, `data/gaps/raw/ndps_dor_clean.pdf`).
  - BNSS 2023 (s.35, 47, 57, 58, 187, 479), UAPA (s.43D), PMLA (s.45): Open India Law `v2026.08.1` legislation file.
- **Judgments:** read from the official Supreme Court PDFs where linked, otherwise from law reports (LiveLaw, Verdictum, SC Observer)
  as noted. Kapil Wadhawan, M. Ravindran, Rakesh Kumar Paul and the Delhi High Court on s.479(2) were checked by Harshita.

## Summary

| Rule | Act and case law support the rule? | Problems found | `last_verified` |
|---|---|---|---|
| `default_bail` | Yes for IPC/BNS cases | **Ignores special-act time limits** (UAPA s.43D(2), NDPS s.36A(4)): says ELIGIBLE too early | `null` (open 1) |
| `undertrial_limit` | Yes for BNSS s.479(1) | **Ignores s.479(2)** (other pending cases); the life-imprisonment exclusion for pre-BNSS cases is unsettled | `null` (open 2, 3) |
| `notice_of_appearance` | Yes (BNSS s.35, CrPC s.41A, Arnesh Kumar) | Minor: BNSS s.35(7) not modelled | **2026-10-27** |
| `grounds_of_arrest` | Yes (Art. 22(1), BNSS s.47, Vihaan Kumar, Mihir Rajesh Shah) | Minor: the rule text promises CHECK for earlier arrests, the code never returns it | **2026-10-27** |
| `production_24h` | Yes (Art. 22(2), CrPC s.57, BNSS s.58) | The statute store holds the wrong text for BNSS s.58 (data, not the rule) | **2026-10-27** |
| `antil_category` | Categories match Antil word for word | **Any non-IPC/BNS act gives C**; Antil's categories are for accused **not arrested** during investigation | `null` (open 5, 6) |
| `statutory_bar` | Partly | **Over-broad**: NDPS s.37 and UAPA s.43D(5) bar only some offences; "twin conditions" does not describe UAPA | `null` (open 7) |

Three of the problems can produce a wrong **ELIGIBLE** (the safety number in the evaluation plan is the false-ELIGIBLE rate):
`default_bail` for UAPA and NDPS cases and `undertrial_limit` for a person with several pending cases (there the court may still
grant bail, so the right answer is CHECK, not ELIGIBLE).

Reproduced by calling the rules directly with `RuleInputs` (2026-10-27):

| Input | Rule says | The act says |
|---|---|---|
| UAPA, maximum 5 years, no charge sheet, day 62 from first remand | `default_bail`: ELIGIBLE | Limit is 90 days (s.43D(2)): not yet |
| NDPS s.21(c), maximum 20 years, no charge sheet, day 100 | `default_bail`: ELIGIBLE | Limit is 180 days (s.36A(4)): not yet |
| BNS 303, maximum 3 years, 600 days in custody, not a first-time offender | `undertrial_limit`: ELIGIBLE | If other cases are pending, s.479(2) restricts release and bail is the court's discretion: CHECK; `RuleInputs` has no field for them |
| Arms Act s.25, maximum 3 years | `antil_category`: C | Not an act with stringent bail provisions: A |
| NDPS s.20(b)(ii)(A) (small quantity) | `statutory_bar`: BAR_APPLIES | s.37(1)(b) does not reach it |

## Rule by rule

### 1. `default_bail`: BNSS s.187(3), CrPC s.167(2)

**Rule:** release if no charge sheet within 90 days (death, life or 10 years and above) or 60 days (other offences); day 1 is the
first remand; the right lapses if the charge sheet is filed before an application; "may extend to ten years" gives CHECK.

**Act:** BNSS s.187(3): "ninety days, where the investigation relates to an offence punishable with death, imprisonment for life or
imprisonment for a term of ten years or more; (ii) sixty days, where the investigation relates to any other offence". CrPC s.167(2)(a)
said "a term of not less than ten years". The 60/90 split matches the act.

The rule rests on three questions the act does not answer. Kapil Wadhawan, M. Ravindran and Rakesh Kumar Paul **interpret the former
CrPC s.167(2)**; BNSS s.187(3) keeps the same structure ("on the expiry of the said period ... shall be released on bail if he is
prepared to and does furnish bail"), and the BNSS-era rulings found so far are listed under question 3.

1. **When does the period begin?** ED v. Kapil Wadhawan (2023): the remand date is included in the 60/90 days. The code counts the
   first remand as day 1 (`day_count.count_days`, `INCLUSIVE_DAY_1`), which matches.
2. **Does a charge sheet extinguish the right?** Not invariably. M. Ravindran v. DRI (2020): if the accused applied for default bail
   after the right accrued, a later charge sheet does not defeat it; the timing of the application decides. The code matches: an
   application made after the limit and before the charge sheet gives ELIGIBLE, and a charge sheet filed after the limit with no
   recorded application gives WINDOW_CLOSED with "check whether an application was made". The rule text "the right lapses if the
   charge sheet is filed before an application" should say "before the accused applies for default bail after the right accrued",
   so it is not read as "any charge sheet ends the right".
3. **Is a ten-year maximum a 60-day or a 90-day case?** Rakesh Kumar Paul v. State of Assam (2017) read "not less than ten years"
   in the CrPC as a minimum of ten years; the distinction between a maximum and a minimum of ten years matters. Under the BNSS wording
   "ten years or more" the High Courts are split:
   - **60 days:** Kerala High Court, Mohammed Sajjid v. State of Kerala, BA 910 of 2025 (2025 LiveLaw (Ker) 119, P V Kunhikrishnan J):
     an NDPS s.22(b) offence with a ten-year maximum takes 60 days; relies on Rakesh Kumar Paul and on the Karnataka High Court in
     State of Karnataka v. Kalandar Shafi (2024), which read "ten years or more" as a minimum.
     <https://www.livelaw.in/high-court/kerala-high-court/kerala-high-court-bnss-statutory-bail-60-days-imprisonment-of-10-days-284349>
   - **90 days:** the Orissa High Court is reported to have taken the 90-day view
     (<https://www.livelaw.in/high-court/orissa-high-court/orissa-high-court-ruling-chargesheet-time-limit-and-state-government-amendment-311486>;
     report only, the judgment was not read).
   - No Supreme Court ruling on the BNSS wording was found. CHECK for a ten-year maximum is therefore the right output, and the
     detail could name the split (60 days in Kerala and Karnataka).
- **Problem: special acts change the limits, and the rule does not know.**
  - UAPA s.43D(2)(a): "the references to 'fifteen days', 'ninety days' and 'sixty days' ... shall be construed as references to
    'thirty days', 'ninety days' and 'ninety days' respectively", and the proviso lets the court extend to 180 days on the Public
    Prosecutor's report. Every UAPA offence takes 90 days.
  - NDPS s.36A(4) (official PDF): "In respect of persons accused of an offence punishable under section 19 or section 24 or section
    27A or for offences involving commercial quantity the references in sub-section (2) of section 167 ... to 'ninety days' ...
    shall be construed as reference to 'one hundred and eighty days'"; the proviso lets the Special Court extend to one year.
  - Both provisions refer to CrPC s.167; whether they now modify BNSS s.187 is a further question, but no reading found treats them
    as lapsed.
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
- **How the courts read s.479(2):** not as an absolute bar. The Delhi High Court (BAIL APPLN. 4657/2024, judgment of 5 May 2026) held
  that s.479(2) does not remove the court's discretion to grant bail once the s.479(1) threshold is crossed; multiple pending cases
  remain a significant factor. Other courts may read it differently, and the outcome depends on the facts.
- Proposed fix: return **CHECK** (not ELIGIBLE, and not NOT_APPLICABLE) when antecedents show another pending case, with a detail
  that names the s.479(2) restriction and says bail is then at the court's discretion. Also do not treat "no antecedents on record"
  as proof of a first-time offender (the proviso is about previous convictions).
- **Cases begun before 1 July 2024:** in In Re Inhuman Conditions in 1382 Prisons (order of 23 August 2024) the Supreme Court held
  that s.479 applies to all undertrials in pending cases, whether the case was registered before or after 1 July 2024, and directed
  jail superintendents to apply for release once the fraction is served; the Ministry of Home Affairs then directed the States to
  implement it (reports: <https://www.livelaw.in/amp/top-stories/take-proactive-steps-to-release-deserving-undertrial-prisoners-under-s479-bnss-supreme-court-to-statesuts-273246>,
  <https://sabrangindia.in/under-trial-prisoners-mha-directs-states-uts-to-implement-section-479-of-bnss>; the order text was not
  read). So the one-third rule reaches old cases. **Still open:** CrPC s.436A covered life-imprisonment offences and s.479 does not;
  no reading was found on whether an old life-imprisonment case keeps the s.436A benefit. Until then the rule's NOT_APPLICABLE for
  life imprisonment may be too strict for pre-1 July 2024 cases; CHECK would be safer there.
- The rule does not say that the second proviso lets the court order continued detention after hearing the Public Prosecutor, or
  that delay caused by the accused is excluded (Explanation). Suggest adding both to the rule text shown to counsel.
- Wording: the rule says "on bond" for both thresholds; the act says "on bail" at one-half and "on bond" at one-third.

### 3. `notice_of_appearance`: BNSS s.35(3), CrPC s.41A (**verified 2026-10-27**)

**Rule:** for offences punishable up to 7 years a notice of appearance is the norm and arrest needs recorded reasons.

**Act:** BNSS s.35(1)(b): arrest without warrant for an offence punishable "for a term which may be less than seven years or which
may extend to seven years" only if the listed conditions are met, and "the police officer shall record while making such arrest,
his reasons in writing". CrPC s.41A (the text of BNSS s.35(3) to (6)): notice of appearance where arrest is not required.

- The rule matches the act. Arnesh Kumar v. State of Bihar (2014): for offences punishable up to seven years the police must not
  arrest merely because the offence is alleged, must record reasons for arrest and for not arresting (a checklist forwarded to the
  Magistrate), and should serve the s.41A notice where arrest is not necessary; Antil (2022) repeats these directions
  (<https://digiscr.sci.gov.in/admin/judgement_file/judgement_pdf/2014/volume%208/Part%20I/2014_8_128-143_1703243046.pdf>).
- Not modelled (optional): BNSS s.35(7), no arrest without the permission of an officer not below Deputy Superintendent for an
  offence punishable with less than 3 years if the person is infirm or over 60.
- The rule returns OK when any arrest memo is in the file and asks counsel to confirm it records reasons; that is a fair limit for
  a rule that cannot read the memo.

### 4. `grounds_of_arrest`: Art. 22(1), BNSS s.47, CrPC s.50 (**verified 2026-10-27**)

**Rule:** grounds must be communicated; since Mihir Rajesh Shah, in writing, in a language the arrested person understands, at
least 2 hours before production; application to earlier arrests is contested, so CHECK.

**Act:** BNSS s.47(1) (same as CrPC s.50(1)): every person arresting without warrant "shall forthwith communicate to him full
particulars of the offence for which he is arrested or other grounds for such arrest".

- **Vihaan Kumar v. State of Haryana** (7 February 2025, 2025 INSC 162; official PDF
  <https://api.sci.gov.in/supremecourt/2024/43293/43293_2024_4_1501_59316_Judgement_07-Feb-2025.pdf>): informing the arrested person
  of the grounds is a mandatory requirement of Art. 22(1), not a formality; the grounds must be conveyed effectively, in a language
  the person understands; mere information of the arrest is not enough; the burden of proving compliance is on the police; non-
  compliance vitiates the arrest.
- **Mihir Rajesh Shah v. State of Maharashtra** (6 November 2025): grounds must be given in writing, in a language the arrested person
  understands; where that is not possible at the time of arrest, they must be communicated orally soon after, and the arrest is not
  vitiated if written grounds are supplied at least two hours before production for remand (SC Observer,
  <https://www.scobserver.in/supreme-court-observer-law-reports-scolr/communication-of-grounds-of-arrest/>; restated in a Supreme
  Court order of 1 April 2026, <https://api.sci.gov.in/supremecourt/2025/73877/73877_2025_2_54_69599_FinalOrder_01-Apr-2026.pdf>).
- **Earlier arrests:** the judgment says "henceforth", and the Delhi High Court (Division Bench, Karan Singh v. State (NCT of Delhi),
  2026:DHC:570-DB) and others read the written-grounds requirement as prospective from 6 November 2025; the Orissa High Court held
  the duty flows from Art. 22 itself and is not excused by prospectivity
  (<https://www.livelaw.in/high-court/orissa-high-court/written-arrest-grounds-article-22-right-mihir-rajesh-shah-judgment-prospective-effect-548058>).
  So "contested" in the rule text is accurate.
- The code matches the law: FLAG only when the record says the grounds were not communicated at all (required for every arrest,
  Vihaan Kumar), OK with a prompt to check writing, language and the two hours, and UNKNOWN when there is no record. **Minor:** the
  rule text ends "so CHECK", but the code never returns CHECK; either drop that phrase or return CHECK for an arrest before
  6 November 2025 with only oral grounds on record.
- Not modelled (optional): BNSS s.47(2), the duty to tell a person arrested for a bailable offence that they are entitled to bail.
- The rule's statuses never claim eligibility for anything, so it cannot produce a false ELIGIBLE.

### 5. `production_24h`: Art. 22(2), BNSS s.58, CrPC s.57 (**verified 2026-10-27**)

**Rule:** produce before a magistrate within 24 hours of arrest, excluding travel time.

**Act:** CrPC s.57: detention "shall not ... exceed twenty-four hours exclusive of the time necessary for the journey from the place
of arrest to the Magistrate's Court". The rule matches.

- **Data problem (not the rule):** the store's BNSS s.58 row has the right heading ("Person arrested not to be detained more than
  twenty-four hours") but the body of s.59 ("Officers in charge of police stations shall report to the District Magistrate ...").
  The rule cites BNSS s.58 correctly; the stored text is wrong, so any tool that shows it to counsel shows the wrong section. For
  Vishak: fix the row or add a gap row in `data/gaps/statutes/` from an official BNSS copy.
- Code: with no times on record, production on the next calendar day gives CHECK and two or more days later gives FLAG; that is
  the right conservative split. Note that `production_date` is taken from the first remand date (`engine.py`), which is a stand-in.

### 6. `antil_category`: Satender Kumar Antil v. CBI (2022)

**Rule:** A: up to 7 years (not B or D); B: death, life or more than 7 years; C: special acts with strict bail conditions; D:
economic offences not under special acts.

**Judgment** (11 July 2022, official PDF
<https://api.sci.gov.in/supremecourt/2021/27955/27955_2021_5_1505_36261_Judgement_11-Jul-2022.pdf>):
"A) Offences punishable with imprisonment of 7 years or less not falling in category B & D. B) Offences punishable with death,
imprisonment for life, or imprisonment for more than 7 years. C) Offences punishable under Special Acts containing stringent
provisions for bail like NDPS (S.37), PMLA (S.45), UAPA (S.43D(5), Companies Act, 212(6), etc. D) Economic offences not covered by
Special Acts." The rule matches the four categories.

- **Problem:** `engine.py` sets `special_act` to any code other than IPC, BNS, CrPC or BNSS, and the rule then returns category C.
  Antil's C is only for special acts "containing stringent provisions for bail"; an Arms Act, Excise Act or IT Act charge is not.
  Proposed fix: C only for acts with such a provision (at least NDPS s.37, PMLA s.45, UAPA s.43D(5), Companies Act s.212(6); the
  judgment's list ends "etc.", so a short reviewed list), else fall through to A, B or D.
- **Scope:** the same passage sets "REQUISITE CONDITIONS: 1) Not arrested during investigation. 2) Cooperated throughout in the
  investigation". The categories decide how an accused who was **not** arrested is treated after the charge sheet. Most Radar users
  have a client in custody, so the category should be shown as context ("Antil category B"), not as a bail entitlement. Worth a line
  in the detail text.
- The economic-offence list (`ECONOMIC_SECTIONS`: IPC 406, 409, 420, 467, 468, 471; BNS 316, 318, 336, 338, 340) is the team's
  reading; Antil gives no list. It returns CHECK, not D, which is safe.

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
- Related: Vihaan Kumar is reported as holding that an arrest made in breach of Art. 22(1) entitles the accused to bail despite
  statutory restrictions such as these; the detail could point counsel to `grounds_of_arrest` when the bar applies.

## Open questions

| # | Question | Who |
|---|---|---|
| 1 | `default_bail`: apply or flag the special-act limits (UAPA s.43D(2): 90 days, extendable to 180; NDPS s.36A(4): 180 days, extendable to one year); reword "lapses if the charge sheet is filed before an application" (M. Ravindran) | Vishak (code) |
| 2 | `undertrial_limit`: CHECK when other cases are pending (s.479(2), court's discretion per the Delhi High Court); "no antecedents" is not "first-time offender"; add `RuleInputs` field for pending cases | Vishak (code) |
| 3 | `undertrial_limit`: does a pre-1 July 2024 life-imprisonment case keep the CrPC s.436A benefit? No reading found; CHECK instead of NOT_APPLICABLE for such cases until one is | Harshita (law), Vishak (code) |
| 4 | `grounds_of_arrest`: drop "so CHECK" from the rule text, or return CHECK for pre-6 November 2025 arrests with only oral grounds (minor; date already set) | Vishak |
| 5 | `antil_category`: C only for acts with stringent bail provisions | Vishak (code) |
| 6 | `antil_category`: show the category as context for arrested clients (Antil's conditions are "not arrested during investigation") | Vishak, Satvik (wording in the UI) |
| 7 | `statutory_bar`: section- and quantity-aware, add CHECK, UAPA test wording | Vishak (code) |
| 8 | Wrong BNSS s.58 text in the statute store | Vishak (data) |

When a row closes, set `last_verified` for that rule in `configs/rights_rules.yaml` (the engine reads it from there; the `None` in
each rule module is only the default) and note the date here.
